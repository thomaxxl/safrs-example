from __future__ import annotations

from pathlib import Path

from safrs_verify.schemathesis_run import build_schemathesis_command


def test_build_schemathesis_command_suppresses_filter_too_much_by_default() -> None:
    cmd = build_schemathesis_command(
        spec_path=Path("/tmp/spec.json"),
        effective_url="http://127.0.0.1:12345/api",
    )
    assert "--suppress-health-check" in cmd
    flag_index = cmd.index("--suppress-health-check")
    assert cmd[flag_index + 1] == "filter_too_much"


def test_build_schemathesis_command_can_disable_suppressed_health_check() -> None:
    cmd = build_schemathesis_command(
        spec_path=Path("/tmp/spec.json"),
        effective_url="http://127.0.0.1:12345/api",
        suppress_health_check="",
    )
    assert "--suppress-health-check" not in cmd
