from __future__ import annotations

import logging

import safrs
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


def test_fastapi_app_debug_enabled_from_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("DEBUG", "1")
    assert fastapi_app._debug_enabled() is True
    assert nw_fastapi_app._debug_enabled() is True


def test_fastapi_app_debug_disabled_by_default(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("DEBUG", raising=False)
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    assert fastapi_app._debug_enabled() is False
    assert nw_fastapi_app._debug_enabled() is False


def test_fastapi_app_configure_runtime_logging_sets_console_loggers() -> None:
    fastapi_app._configure_runtime_logging(logging.DEBUG)
    assert safrs.log.getEffectiveLevel() <= logging.DEBUG
    assert logging.getLogger("uvicorn").getEffectiveLevel() <= logging.DEBUG
    assert logging.getLogger("uvicorn.error").getEffectiveLevel() <= logging.DEBUG
    assert logging.getLogger("uvicorn.access").getEffectiveLevel() <= logging.DEBUG
    assert len(safrs.log.handlers) > 0


def test_nw_fastapi_app_configure_runtime_logging_sets_console_loggers() -> None:
    nw_fastapi_app._configure_runtime_logging(logging.DEBUG)
    assert safrs.log.getEffectiveLevel() <= logging.DEBUG
    assert logging.getLogger("uvicorn").getEffectiveLevel() <= logging.DEBUG
    assert logging.getLogger("uvicorn.error").getEffectiveLevel() <= logging.DEBUG
    assert logging.getLogger("uvicorn.access").getEffectiveLevel() <= logging.DEBUG
    assert len(safrs.log.handlers) > 0
