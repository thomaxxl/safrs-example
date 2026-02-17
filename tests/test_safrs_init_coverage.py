import logging
from types import SimpleNamespace

from flask import Flask

import safrs.safrs_init as safrs_init


def test_is_truthy_env_and_resolve_loglevel_debug_env_branches(monkeypatch, capsys):
    # line 19: truthy env normalization
    assert safrs_init._is_truthy_env(" YES ") is True
    assert safrs_init._is_truthy_env(None) is False

    monkeypatch.delenv("FLASK_DEBUG", raising=False)

    # lines 25-26: DEBUG integer
    monkeypatch.setenv("DEBUG", "15")
    assert safrs_init._resolve_loglevel() == 15

    # lines 27-30: named level
    monkeypatch.setenv("DEBUG", "info")
    assert safrs_init._resolve_loglevel() == logging.INFO

    # lines 31-32: truthy DEBUG keyword
    monkeypatch.setenv("DEBUG", "on")
    assert safrs_init._resolve_loglevel() == logging.DEBUG

    # lines 33-34: invalid DEBUG value warning path
    monkeypatch.setenv("DEBUG", "not_a_level")
    assert safrs_init._resolve_loglevel() == logging.INFO
    captured = capsys.readouterr()
    assert "Invalid LogLevel in DEBUG Environment Variable" in captured.out


def test_resolve_loglevel_uses_flask_debug_env(monkeypatch):
    # line 37: FLASK_DEBUG fallback when DEBUG is not set
    monkeypatch.delenv("DEBUG", raising=False)
    monkeypatch.setenv("FLASK_DEBUG", "1")
    assert safrs_init._resolve_loglevel() == logging.DEBUG


def test_init_app_uses_sqlalchemy_extension_when_app_db_missing():
    # line 89: app_db defaults to app.extensions["sqlalchemy"]
    app = Flask("safrs-init-cov")
    dummy_db = SimpleNamespace(session=SimpleNamespace(remove=lambda: None))
    app.extensions["sqlalchemy"] = dummy_db

    old_db = safrs_init.safrs.DB
    try:
        api = safrs_init.SAFRS.__new__(safrs_init.SAFRS)
        api.init_app(app, app_db=None, swaggerui_blueprint=False)
        assert api.db is dummy_db
        assert safrs_init.safrs.DB is dummy_db
    finally:
        safrs_init.safrs.DB = old_db
