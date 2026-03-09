#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import contextvars
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_SAFRS_PATH = REPO_ROOT / "safrs"
if str(LOCAL_SAFRS_PATH) not in sys.path:
    sys.path.insert(0, str(LOCAL_SAFRS_PATH))

import safrs
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from safrs.fastapi.api import SafrsFastAPI

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
REQUEST_SCOPE: contextvars.ContextVar[str] = contextvars.ContextVar("safrs_request_scope", default="startup")


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


def _debug_enabled() -> bool:
    return _resolve_log_level() <= int(logging.DEBUG)


def _reload_enabled() -> bool:
    if _is_truthy_env(os.environ.get("SAFRS_DISABLE_RELOAD")):
        return False
    return _debug_enabled()


def _configure_runtime_logging(level: int) -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=level, format="[%(asctime)s] %(levelname)s: %(message)s")

    safrs.log.setLevel(level)
    if not safrs.log.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))
        safrs.log.addHandler(handler)
    safrs.log.propagate = False
    logging.getLogger("uvicorn").setLevel(level)
    logging.getLogger("uvicorn.error").setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(level)


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
    return HERE / f"fastapi_{port}.db"


def create_app(port: int = 8000) -> FastAPI:
    db_path = _resolve_db_path(port)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if _should_reset_db() and db_path.exists():
        db_path.unlink()

    session = create_session(db_path=db_path, scopefunc=lambda: REQUEST_SCOPE.get())
    wrapper = SAFRSDBWrapper(session, Base)
    setattr(safrs, "DB", wrapper)
    seed_data(session)
    session.remove()

    app = FastAPI(
        title="SAFRS verifier FastAPI demo",
        description=DESCRIPTION,
        docs_url="/docs",
        redoc_url=None,
        debug=_debug_enabled(),
    )

    @app.middleware("http")
    async def remove_session_middleware(request: Any, call_next: Any) -> Any:
        scope_token = REQUEST_SCOPE.set(uuid.uuid4().hex)
        try:
            return await call_next(request)
        finally:
            try:
                session.rollback()
            except Exception:
                pass
            try:
                session.remove()
            finally:
                REQUEST_SCOPE.reset(scope_token)

    api = SafrsFastAPI(app, prefix=API_PREFIX)
    app.state.safrs_api = api
    for model in EXPOSED_MODELS:
        api.expose_object(model)

    @app.get("/", include_in_schema=False)
    def root() -> Any:
        return RedirectResponse(url=API_PREFIX)

    @app.get("/health", include_in_schema=False)
    def health() -> dict[str, Any]:
        return {"ok": True, "framework": "fastapi", "db": str(db_path), "api_prefix": API_PREFIX}

    @app.get("/seed", include_in_schema=False)
    def seed() -> dict[str, Any]:
        return build_seed_payload(session)

    return app


def _create_app_from_env() -> FastAPI:
    try:
        port = int(str(os.environ.get("SAFRS_APP_PORT", "8000")))
    except ValueError:
        port = 8000
    return create_app(port=port)


if __name__ == "__main__":
    import uvicorn

    bind_host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    bind_port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    log_level = _resolve_log_level()
    reload_enabled = _reload_enabled()
    os.environ["SAFRS_APP_PORT"] = str(bind_port)
    _configure_runtime_logging(log_level)
    uvicorn.run(
        f"{Path(__file__).stem}:_create_app_from_env",
        factory=True,
        host=bind_host,
        port=bind_port,
        log_level="debug" if log_level <= logging.DEBUG else "info",
        access_log=True,
        reload=reload_enabled,
        reload_dirs=[str(HERE)] if reload_enabled else None,
    )
