from __future__ import annotations

from pathlib import Path

import pytest

from safrs_verify.config import ContractTarget, default_contract_targets
from safrs_verify.contract import ContractRunOptions, options_from_env, run_contract_target


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_TARGETS: tuple[ContractTarget, ...] = default_contract_targets(PROJECT_ROOT)


@pytest.mark.contract
@pytest.mark.slow
@pytest.mark.parametrize("target", CONTRACT_TARGETS, ids=lambda t: t.name)
def test_contract_target_runs_with_runtime_spec_discovery(target: ContractTarget) -> None:
    options_env = options_from_env()
    options = ContractRunOptions(
        startup_timeout_s=20.0,
        request_timeout_s=options_env.request_timeout_s,
        max_examples=options_env.max_examples,
        phases=options_env.phases,
        app_log_lines=options_env.app_log_lines,
        keep_failed_artifacts=True,
    )

    result = run_contract_target(target, options=options)
    assert result.returncode == 0, "\n".join(
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


def test_contract_target_list_is_expected() -> None:
    assert {target.name for target in CONTRACT_TARGETS} == {"flask", "fastapi"}
