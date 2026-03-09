from __future__ import annotations

import logging

import safrs
import flask_app
import nw_flask_app


def test_flask_app_resolve_log_level_debug_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("LOGLEVEL", raising=False)
    monkeypatch.setenv("DEBUG", "1")
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    assert flask_app._resolve_log_level() <= logging.DEBUG
    assert nw_flask_app._resolve_log_level() <= logging.DEBUG


def test_flask_app_resolve_log_level_from_flask_debug(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("LOGLEVEL", raising=False)
    monkeypatch.delenv("DEBUG", raising=False)
    monkeypatch.setenv("FLASK_DEBUG", "1")
    assert flask_app._resolve_log_level() <= logging.DEBUG
    assert nw_flask_app._resolve_log_level() <= logging.DEBUG


def test_flask_app_resolve_log_level_default_info(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("LOGLEVEL", raising=False)
    monkeypatch.delenv("DEBUG", raising=False)
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    assert flask_app._resolve_log_level() == logging.INFO
    assert nw_flask_app._resolve_log_level() == logging.INFO


def test_flask_app_debug_enabled_from_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("LOGLEVEL", raising=False)
    monkeypatch.setenv("DEBUG", "1")
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    assert flask_app._debug_enabled() is True
    assert nw_flask_app._debug_enabled() is True


def test_flask_app_reload_enabled_when_debug_enabled(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("SAFRS_DISABLE_RELOAD", raising=False)
    monkeypatch.delenv("LOGLEVEL", raising=False)
    monkeypatch.setenv("DEBUG", "1")
    assert flask_app._reload_enabled() is True
    assert nw_flask_app._reload_enabled() is True


def test_flask_app_reload_disabled_when_env_override_set(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("SAFRS_DISABLE_RELOAD", "1")
    monkeypatch.delenv("LOGLEVEL", raising=False)
    monkeypatch.setenv("DEBUG", "1")
    assert flask_app._reload_enabled() is False
    assert nw_flask_app._reload_enabled() is False


def test_flask_app_resolve_log_level_prefers_loglevel_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("LOGLEVEL", "40")
    monkeypatch.setenv("DEBUG", "1")
    monkeypatch.setenv("FLASK_DEBUG", "1")
    assert flask_app._resolve_log_level() == logging.ERROR
    assert nw_flask_app._resolve_log_level() == logging.ERROR


def test_flask_app_configure_runtime_logging_sets_console_loggers() -> None:
    flask_app._configure_runtime_logging(logging.DEBUG)
    assert safrs.log.getEffectiveLevel() <= logging.DEBUG
    assert logging.getLogger("werkzeug").getEffectiveLevel() <= logging.DEBUG
    assert len(safrs.log.handlers) > 0


def test_nw_flask_app_configure_runtime_logging_sets_console_loggers() -> None:
    nw_flask_app._configure_runtime_logging(logging.DEBUG)
    assert safrs.log.getEffectiveLevel() <= logging.DEBUG
    assert logging.getLogger("werkzeug").getEffectiveLevel() <= logging.DEBUG
    assert len(safrs.log.handlers) > 0
