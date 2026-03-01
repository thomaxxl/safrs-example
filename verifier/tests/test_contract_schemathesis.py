from __future__ import annotations

from pathlib import Path

import pytest

from safrs_verify.config import default_contract_targets
from safrs_verify.contract import ContractRunOptions, options_from_env, run_contract_target


@pytest.mark.contract
@pytest.mark.slow
def test_contract_targets_run_with_runtime_spec_discovery() -> None:
    options_env = options_from_env()
    options = ContractRunOptions(
        startup_timeout_s=20.0,
        request_timeout_s=options_env.request_timeout_s,
        max_examples=options_env.max_examples,
        phases=options_env.phases,
        app_log_lines=options_env.app_log_lines,
        keep_failed_artifacts=True,
    )

    failures: list[str] = []
    for target in default_contract_targets(Path(__file__).resolve().parents[1]):
        result = run_contract_target(target, options=options)

        if result.returncode != 0:
            failures.append(
                "\n".join(
                    [
                        f"target={target.name}",
                        f"spec_endpoint={result.spec_endpoint}",
                        f"base_url={result.base_url}",
                        f"effective_url={result.effective_url}",
                        f"artifact_dir={result.artifact_dir}",
                        "command=" + " ".join(result.command),
                        "app_tail:\n" + "\n".join(result.app_log_tail),
                        "schemathesis:\n" + result.schemathesis_output[-8000:],
                    ]
                )
            )

    assert failures == [], "\n\n".join(failures)
