from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from safrs_verify.config import default_contract_targets
from safrs_verify.contract import ContractRunOptions, run_contract_target
from safrs_verify.db import BackendUnavailable, resolve_db_backends


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.contract
@pytest.mark.slow
def test_contract_targets_run_with_runtime_spec_discovery() -> None:
    if shutil.which("schemathesis") is None:
        pytest.skip("schemathesis CLI is not installed")

    targets = default_contract_targets(PROJECT_ROOT)
    backend = resolve_db_backends("sqlite")[0]

    max_examples = int(os.environ.get("SAFRS_CONTRACT_MAX_EXAMPLES", "5"))
    phases = os.environ.get("SAFRS_CONTRACT_PHASES", "examples,fuzzing")

    failures: list[str] = []

    for target in targets:
        options = ContractRunOptions(
            startup_timeout_s=20.0,
            request_timeout_s=10.0,
            max_examples=max_examples,
            phases=phases,
            app_log_lines=200,
            keep_failed_artifacts=True,
        )
        try:
            result = run_contract_target(target, backend, options=options)
        except BackendUnavailable as exc:
            pytest.skip(f"sqlite backend unavailable: {exc}")
        except PermissionError as exc:
            pytest.skip(f"local socket binding not permitted in this environment: {exc}")

        if result.returncode != 0:
            failures.append(
                "\n".join(
                    [
                        f"target={target.name} backend={backend.name}",
                        f"spec_endpoint={result.spec_endpoint}",
                        f"base_url={result.base_url}",
                        f"effective_url={result.effective_url}",
                        f"runtime_spec_path={result.runtime_spec_path}",
                        "command=" + " ".join(result.command),
                        "app_tail:\n" + "\n".join(result.app_log_tail),
                        "schemathesis:\n" + result.schemathesis_output[-8000:],
                    ]
                )
            )

    assert failures == [], "\n\n".join(failures)
