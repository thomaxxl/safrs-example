from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import ContractTarget
from .db import BackendUnavailable, DBBackend
from .runner import AppRunner
from .schemathesis_run import SchemathesisResult, run_schemathesis
from .seed_patch import prepare_spec_for_run
from .spec import discover_spec_with_effective_url, join_base_url, write_temp_spec


@dataclass(frozen=True)
class ContractRunOptions:
    host: str = "127.0.0.1"
    port: int = 0
    startup_timeout_s: float = 15.0
    request_timeout_s: float = 10.0
    max_examples: int = 25
    phases: str = "examples,fuzzing"
    auth_header: str = ""
    content_type: str = "application/vnd.api+json"
    app_log_lines: int = 200
    tee_app_logs: bool = False
    app_log_file: Path | None = None
    force_base_path: str = ""
    keep_failed_artifacts: bool = True


@dataclass(frozen=True)
class ContractRunResult:
    target_name: str
    backend_name: str
    returncode: int
    command: tuple[str, ...]
    schemathesis_output: str
    base_url: str
    effective_url: str
    spec_endpoint: str
    app_log_tail: tuple[str, ...]
    runtime_spec_path: Path


class ContractRunError(RuntimeError):
    pass


def run_contract_target(
    target: ContractTarget,
    backend: DBBackend,
    *,
    options: ContractRunOptions | None = None,
    extra_env: dict[str, str] | None = None,
) -> ContractRunResult:
    opts = options if options is not None else ContractRunOptions()
    run_id = uuid.uuid4().hex[:12]

    try:
        db_env = backend.provision(run_id)
    except BackendUnavailable:
        raise
    except Exception as exc:
        raise ContractRunError(f"Failed to provision backend {backend.name}: {exc}") from exc

    merged_env = dict(target.env)
    merged_env.update(db_env)
    if extra_env:
        merged_env.update(extra_env)

    runner = AppRunner(
        app_path=target.app_path,
        host=opts.host,
        port=opts.port,
        startup_timeout=opts.startup_timeout_s,
        health_path=target.health_path,
        app_args=target.app_args,
        env=merged_env,
        app_log_lines=opts.app_log_lines,
        tee_app_logs=opts.tee_app_logs,
        app_log_file=opts.app_log_file,
    )

    spec_path = Path()
    runtime_spec_path = Path()
    remove_spec_path = False
    remove_runtime_path = False
    discovered_endpoint = ""
    base_url = ""
    effective_url = ""
    st_result: SchemathesisResult | None = None
    try:
        base_url = runner.start()
        discovery = discover_spec_with_effective_url(
            base_url=base_url,
            candidates=target.spec_candidates,
            request_timeout_s=opts.request_timeout_s,
        )
        discovered_endpoint = discovery.fetched.endpoint
        effective_url = discovery.effective_url
        if opts.force_base_path.strip():
            effective_url = join_base_url(base_url, opts.force_base_path.strip())

        spec_path = write_temp_spec(discovery.fetched.spec)
        remove_spec_path = True
        runtime_spec_path, remove_runtime_path = prepare_spec_for_run(
            spec_path=spec_path,
            base_url=base_url,
            request_timeout_s=opts.request_timeout_s,
            seed_path=target.seed_path,
            collection_id_key_overrides=target.collection_id_keys,
        )

        auth_header = opts.auth_header or os.environ.get("API_AUTHORIZATION", "")
        st_result = run_schemathesis(
            spec_path=runtime_spec_path,
            effective_url=effective_url,
            max_examples=opts.max_examples,
            request_timeout_s=opts.request_timeout_s,
            phases=opts.phases,
            auth_header=auth_header,
            content_type=opts.content_type,
        )

        return ContractRunResult(
            target_name=target.name,
            backend_name=backend.name,
            returncode=st_result.returncode,
            command=st_result.command,
            schemathesis_output=st_result.output,
            base_url=base_url,
            effective_url=effective_url,
            spec_endpoint=discovered_endpoint,
            app_log_tail=tuple(runner.log_tail()),
            runtime_spec_path=runtime_spec_path,
        )
    finally:
        runner.stop()
        try:
            keep_runtime = (
                opts.keep_failed_artifacts
                and st_result is not None
                and st_result.returncode != 0
            )
            if remove_runtime_path and runtime_spec_path.exists() and not keep_runtime:
                runtime_spec_path.unlink(missing_ok=True)
            if remove_spec_path and spec_path.exists():
                spec_path.unlink(missing_ok=True)
        finally:
            backend.cleanup(run_id)
