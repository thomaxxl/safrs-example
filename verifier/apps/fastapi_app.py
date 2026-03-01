#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

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

    session = create_session(db_path=db_path)
    wrapper = SAFRSDBWrapper(session, Base)
    setattr(safrs, "DB", wrapper)
    seed_data(session)

    app = FastAPI(
        title="SAFRS verifier FastAPI demo",
        description=DESCRIPTION,
        docs_url="/docs",
        redoc_url=None,
    )

    @app.middleware("http")
    async def remove_session_middleware(request: Any, call_next: Any) -> Any:
        try:
            return await call_next(request)
        finally:
            session.remove()

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


if __name__ == "__main__":
    import uvicorn

    bind_host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    bind_port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    uvicorn.run(create_app(port=bind_port), host=bind_host, port=bind_port)
