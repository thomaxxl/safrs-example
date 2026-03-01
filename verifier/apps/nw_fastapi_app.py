#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import contextvars
import os
import shutil
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

from nw_models import (
    API_PREFIX,
    Base,
    COLLECTION_ID_KEYS,
    DESCRIPTION,
    EXPOSED_MODELS,
    SAFRSDBWrapper,
    build_seed_payload,
    create_session,
    seed_data,
)


HERE = Path(__file__).resolve().parent
REQUEST_SCOPE: contextvars.ContextVar[str] = contextvars.ContextVar("safrs_request_scope_nw", default="startup")


def _should_reset_db() -> bool:
    value = os.environ.get("SAFRS_NW_RESET_DB", "1").strip().lower()
    return value not in ("0", "false", "no")


def _resolve_source_db_path() -> Path:
    env_path = os.environ.get("SAFRS_NW_DB_SOURCE", "").strip()
    if env_path:
        path = Path(env_path).expanduser()
        if not path.is_absolute():
            path = (HERE.parent / path).resolve()
        return path
    return HERE.parent / "nw-db.sqlite"


def _resolve_work_db_path(port: int) -> Path:
    env_path = os.environ.get("SAFRS_NW_DB_PATH", "").strip()
    if env_path:
        path = Path(env_path).expanduser()
        if not path.is_absolute():
            path = (HERE / path).resolve()
        return path
    return HERE / f"nw_fastapi_{port}.sqlite"


def _prepare_work_db(port: int) -> Path:
    source_path = _resolve_source_db_path()
    work_path = _resolve_work_db_path(port)
    if not source_path.exists():
        raise RuntimeError(f"SAFRS NW source database not found: {source_path}")
    work_path.parent.mkdir(parents=True, exist_ok=True)
    if _should_reset_db() or not work_path.exists():
        shutil.copy2(source_path, work_path)
    return work_path


def create_app(port: int = 8000) -> FastAPI:
    db_path = _prepare_work_db(port)
    session = create_session(db_path=db_path, scopefunc=lambda: REQUEST_SCOPE.get())
    wrapper = SAFRSDBWrapper(session, Base)
    setattr(safrs, "DB", wrapper)
    seed_data(session)
    session.remove()

    app = FastAPI(
        title="SAFRS verifier NW FastAPI app",
        description=DESCRIPTION,
        docs_url="/docs",
        redoc_url=None,
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
        return {
            "ok": True,
            "framework": "fastapi",
            "api_prefix": API_PREFIX,
            "db": str(db_path),
            "source_db": str(_resolve_source_db_path()),
            "collections": sorted(COLLECTION_ID_KEYS),
        }

    @app.get("/seed", include_in_schema=False)
    def seed() -> dict[str, Any]:
        return build_seed_payload(session)

    return app


if __name__ == "__main__":
    import uvicorn

    bind_host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    bind_port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    uvicorn.run(create_app(port=bind_port), host=bind_host, port=bind_port)
