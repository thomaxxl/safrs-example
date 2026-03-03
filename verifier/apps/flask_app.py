#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_SAFRS_PATH = REPO_ROOT / "safrs"
if str(LOCAL_SAFRS_PATH) not in sys.path:
    sys.path.insert(0, str(LOCAL_SAFRS_PATH))

import safrs
from flask import Flask, jsonify, redirect
from flask_cors import CORS
from safrs import SAFRSAPI

from models import (
    API_PREFIX,
    Base,
    DESCRIPTION,
    EXPOSED_MODELS,
    SAFRSDBWrapper,
    build_seed_payload,
    create_session,
    seed_data,
)


HERE = Path(__file__).resolve().parent


def _is_truthy_env(value: str | None) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_log_level_value(value: str | None) -> int | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    try:
        return int(normalized)
    except ValueError:
        upper = normalized.upper()
        if upper in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            return int(getattr(logging, upper))
    return None


def _resolve_log_level() -> int:
    loglevel_env = os.environ.get("LOGLEVEL")
    parsed_loglevel = _parse_log_level_value(loglevel_env)
    if parsed_loglevel is not None:
        return parsed_loglevel

    debug_env = os.environ.get("DEBUG")
    if debug_env is not None:
        parsed_debug = _parse_log_level_value(debug_env)
        if parsed_debug is not None:
            return parsed_debug
        if _is_truthy_env(debug_env):
            return int(logging.DEBUG)
        return int(logging.INFO)

    if _is_truthy_env(os.environ.get("FLASK_DEBUG")):
        return int(logging.DEBUG)
    return int(logging.INFO)


def _configure_runtime_logging(level: int) -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=level, format="[%(asctime)s] %(levelname)s: %(message)s")

    safrs.log.setLevel(level)
    if not safrs.log.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))
        safrs.log.addHandler(handler)
    safrs.log.propagate = False

    logging.getLogger("werkzeug").setLevel(level)


def _should_reset_db() -> bool:
    value = os.environ.get("SAFRS_EXAMPLE_RESET_DB", "1").strip().lower()
    return value not in ("0", "false", "no")


def _resolve_db_path(port: int) -> Path:
    env_path = os.environ.get("SAFRS_EXAMPLE_DB_PATH", "").strip()
    if env_path:
        path = Path(env_path).expanduser()
        if not path.is_absolute():
            path = (HERE / path).resolve()
        return path
    return HERE / f"flask_{port}.db"


def create_app(host: str = "127.0.0.1", port: int = 5000) -> Flask:
    db_path = _resolve_db_path(port)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if _should_reset_db() and db_path.exists():
        db_path.unlink()

    session = create_session(db_path=db_path)
    wrapper = SAFRSDBWrapper(session, Base)
    setattr(safrs, "DB", wrapper)
    seed_data(session)

    app = Flask("safrs-verifier-flask")
    app.secret_key = os.environ.get("SAFRS_EXAMPLE_SECRET_KEY", os.urandom(16).hex())
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    with app.app_context():
        api = SAFRSAPI(
            app,
            app_db=wrapper,
            host=host,
            port=port,
            prefix=API_PREFIX,
            description=DESCRIPTION,
            custom_swagger={"info": {"title": "SAFRS verifier Flask demo"}},
        )
        for model in EXPOSED_MODELS:
            api.expose_object(model)

    @app.teardown_appcontext
    def remove_session(_exc: Any) -> None:
        session.remove()

    @app.route("/", methods=["GET"])
    def root() -> Any:
        return redirect(API_PREFIX)

    @app.route("/health", methods=["GET"])
    def health() -> Any:
        return jsonify({"ok": True, "framework": "flask", "db": str(db_path), "api_prefix": API_PREFIX})

    @app.route("/seed", methods=["GET"])
    def seed() -> Any:
        return jsonify(build_seed_payload(session))

    return app


if __name__ == "__main__":
    bind_host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    bind_port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    _configure_runtime_logging(_resolve_log_level())
    flask_app = create_app(host=bind_host, port=bind_port)
    flask_app.run(host=bind_host, port=bind_port, threaded=False)
