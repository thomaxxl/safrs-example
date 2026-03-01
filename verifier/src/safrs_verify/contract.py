from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from .artifacts import (
    ArtifactBundle,
    ArtifactPolicy,
    cleanup_artifacts,
    create_artifact_bundle,
    should_keep_artifacts,
    write_json,
    write_text,
)
from .config import ContractTarget
from .runner import AppRunner
from .schemathesis_run import SchemathesisResult, run_schemathesis
from .seed_patch import fetch_seed_payload, patch_spec_with_seed
from .spec import discover_spec_with_effective_url, join_base_url
from .sqlite_db import prepare_sqlite_env


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
    force_base_path: str = ""
    keep_failed_artifacts: bool = True


@dataclass(frozen=True)
class ContractRunResult:
    target_name: str
    returncode: int
    command: tuple[str, ...]
    schemathesis_output: str
    base_url: str
    effective_url: str
    spec_endpoint: str
    app_log_tail: tuple[str, ...]
    artifact_dir: Path
    runtime_spec_path: Path
    patched_spec_path: Path


class ContractRunError(RuntimeError):
    pass


def options_from_env() -> ContractRunOptions:
    return ContractRunOptions(
        max_examples=int(os.environ.get("SAFRS_CONTRACT_MAX_EXAMPLES", "25")),
        phases=os.environ.get("SAFRS_CONTRACT_PHASES", "examples,fuzzing"),
        request_timeout_s=float(os.environ.get("SAFRS_CONTRACT_REQUEST_TIMEOUT", "10")),
        app_log_lines=int(os.environ.get("SAFRS_VERIFY_APP_LOG_LINES", "200")),
    )


def _write_metadata(
    artifacts: ArtifactBundle,
    *,
    target: ContractTarget,
    base_url: str,
    effective_url: str,
    spec_endpoint: str,
    command: tuple[str, ...],
) -> None:
    write_json(
        artifacts.directory / "metadata.json",
        {
            "target": target.name,
            "base_url": base_url,
            "effective_url": effective_url,
            "spec_endpoint": spec_endpoint,
            "command": list(command),
        },
    )


def run_contract_target(
    target: ContractTarget,
    *,
    options: ContractRunOptions | None = None,
    extra_env: dict[str, str] | None = None,
) -> ContractRunResult:
    opts = options if options is not None else options_from_env()
    run_id = uuid.uuid4().hex[:12]

    artifacts = create_artifact_bundle(run_id)
    sqlite_run = prepare_sqlite_env(artifacts)

    merged_env = dict(target.env)
    merged_env.update(sqlite_run.env)
    if extra_env:
        merged_env.update(extra_env)

    app_log_file = artifacts.directory / "app.log"
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
        app_log_file=app_log_file,
    )

    base_url = ""
    effective_url = ""
    spec_endpoint = ""
    runtime_spec_path = artifacts.directory / "runtime_spec.json"
    patched_spec_path = artifacts.directory / "patched_spec.json"
    st_result: SchemathesisResult | None = None
    failed = False

    try:
        base_url = runner.start()
        discovery = discover_spec_with_effective_url(
            base_url=base_url,
            candidates=target.spec_candidates,
            request_timeout_s=opts.request_timeout_s,
        )
        spec_endpoint = discovery.fetched.endpoint
        effective_url = discovery.effective_url
        if opts.force_base_path.strip():
            effective_url = join_base_url(base_url, opts.force_base_path.strip())

        write_json(runtime_spec_path, discovery.fetched.spec)

        seed = fetch_seed_payload(base_url, opts.request_timeout_s, seed_path=target.seed_path)
        if seed:
            patched_spec = patch_spec_with_seed(
                discovery.fetched.spec,
                seed,
                collection_id_key_overrides=target.collection_id_keys,
            )
            write_json(patched_spec_path, patched_spec)
            spec_for_run = patched_spec_path
        else:
            spec_for_run = runtime_spec_path
            if patched_spec_path.exists():
                patched_spec_path.unlink(missing_ok=True)

        auth_header = opts.auth_header or os.environ.get("API_AUTHORIZATION", "")
        st_result = run_schemathesis(
            spec_path=spec_for_run,
            effective_url=effective_url,
            max_examples=opts.max_examples,
            request_timeout_s=opts.request_timeout_s,
            phases=opts.phases,
            auth_header=auth_header,
            content_type=opts.content_type,
        )

        write_text(artifacts.directory / "schemathesis.out.txt", st_result.output)
        write_text(artifacts.directory / "app.tail.txt", "\n".join(runner.log_tail()))
        _write_metadata(
            artifacts,
            target=target,
            base_url=base_url,
            effective_url=effective_url,
            spec_endpoint=spec_endpoint,
            command=st_result.command,
        )

        failed = st_result.returncode != 0
        return ContractRunResult(
            target_name=target.name,
            returncode=st_result.returncode,
            command=st_result.command,
            schemathesis_output=st_result.output,
            base_url=base_url,
            effective_url=effective_url,
            spec_endpoint=spec_endpoint,
            app_log_tail=tuple(runner.log_tail()),
            artifact_dir=artifacts.directory,
            runtime_spec_path=runtime_spec_path,
            patched_spec_path=patched_spec_path,
        )
    except Exception as exc:
        failed = True
        write_text(artifacts.directory / "error.txt", repr(exc))
        raise
    finally:
        runner.stop()
        policy = ArtifactPolicy(keep_failed_artifacts=opts.keep_failed_artifacts)
        if not should_keep_artifacts(failed=failed, policy=policy):
            cleanup_artifacts(artifacts)
