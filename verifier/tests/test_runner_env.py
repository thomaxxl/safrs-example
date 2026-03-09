from __future__ import annotations

from pathlib import Path

import pytest

from safrs_verify import runner as runner_mod


class _DummyProc:
    def __init__(self) -> None:
        self.stdout: list[str] = []

    def poll(self) -> int:
        return 0


class _DummyThread:
    def join(self, timeout: float | None = None) -> None:
        _ = timeout


def test_app_runner_forces_debug_env(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_popen(*_args, **kwargs):
        captured["env"] = kwargs["env"]
        return _DummyProc()

    monkeypatch.setattr(runner_mod, "find_free_port", lambda _host: 34567)
    monkeypatch.setattr(runner_mod, "wait_http_ok", lambda _url, _timeout: None)
    monkeypatch.setattr(runner_mod, "start_app_log_drain", lambda *_args, **_kwargs: _DummyThread())
    monkeypatch.setattr(runner_mod.subprocess, "Popen", fake_popen)

    app_runner = runner_mod.AppRunner(app_path=Path("/tmp/fake_app.py"), env={"DEBUG": "0", "FLASK_DEBUG": "0"})
    app_runner.start()
    app_runner.stop()

    env = captured["env"]
    assert isinstance(env, dict)
    assert env["DEBUG"] == "1"
    assert env["FLASK_DEBUG"] == "1"
    assert env["SAFRS_DISABLE_RELOAD"] == "1"
