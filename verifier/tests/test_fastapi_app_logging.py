from __future__ import annotations

import logging

import fastapi_app
import nw_fastapi_app


def test_fastapi_app_resolve_log_level_debug_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("DEBUG", "1")
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    assert fastapi_app._resolve_log_level() <= logging.DEBUG
    assert nw_fastapi_app._resolve_log_level() <= logging.DEBUG


def test_fastapi_app_resolve_log_level_from_flask_debug(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("DEBUG", raising=False)
    monkeypatch.setenv("FLASK_DEBUG", "1")
    assert fastapi_app._resolve_log_level() <= logging.DEBUG
    assert nw_fastapi_app._resolve_log_level() <= logging.DEBUG


def test_fastapi_app_resolve_log_level_default_info(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("DEBUG", raising=False)
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    assert fastapi_app._resolve_log_level() == logging.INFO
    assert nw_fastapi_app._resolve_log_level() == logging.INFO
