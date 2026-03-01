from __future__ import annotations

from safrs_verify.artifacts import ArtifactPolicy, should_keep_artifacts
from safrs_verify.contract import options_from_env


def test_default_contract_options_match_expected(monkeypatch) -> None:
    monkeypatch.delenv("SAFRS_CONTRACT_MAX_EXAMPLES", raising=False)
    monkeypatch.delenv("SAFRS_CONTRACT_PHASES", raising=False)
    monkeypatch.delenv("SAFRS_CONTRACT_REQUEST_TIMEOUT", raising=False)
    monkeypatch.delenv("SAFRS_VERIFY_APP_LOG_LINES", raising=False)

    opts = options_from_env()
    assert opts.max_examples == 25
    assert opts.phases == "examples,fuzzing"
    assert opts.request_timeout_s == 10.0
    assert opts.app_log_lines == 200


def test_keep_artifacts_default_is_enabled(monkeypatch) -> None:
    monkeypatch.delenv("SAFRS_VERIFY_KEEP_ARTIFACTS", raising=False)
    policy = ArtifactPolicy(keep_failed_artifacts=False)
    assert should_keep_artifacts(failed=False, policy=policy) is True
