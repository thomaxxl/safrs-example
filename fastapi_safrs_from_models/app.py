#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAFRS_REPO_ROOT = PROJECT_ROOT / "safrs"
if str(SAFRS_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SAFRS_REPO_ROOT))

import safrs
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from safrs.fastapi.api import RelationshipItemMode, SafrsFastAPI

if __package__:
    from .models import API_PREFIX, Base, DEFAULT_DB_PATH, DESCRIPTION, EXPOSED_MODELS, SAFRSDBWrapper, create_session
else:
    from models import API_PREFIX, Base, DEFAULT_DB_PATH, DESCRIPTION, EXPOSED_MODELS, SAFRSDBWrapper, create_session


def _should_reset_db() -> bool:
    value = os.environ.get("SAFRS_RESET_DB", "0").strip().lower()
    return value in ("1", "true", "yes")


def _resolve_db_path(explicit_db_path: str | None = None) -> Path:
    if explicit_db_path:
        path = Path(explicit_db_path).expanduser()
    else:
        env_db_path = os.environ.get("SAFRS_SQLITE_PATH", "").strip()
        if env_db_path:
            path = Path(env_db_path).expanduser()
        else:
            return DEFAULT_DB_PATH

    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def create_app(db_path: str | None = None) -> FastAPI:
    resolved_db_path = _resolve_db_path(explicit_db_path=db_path)
    resolved_db_path.parent.mkdir(parents=True, exist_ok=True)
    if _should_reset_db() and resolved_db_path.exists():
        resolved_db_path.unlink()

    Session = create_session(resolved_db_path)
    wrapper = SAFRSDBWrapper(Session, Base)
    setattr(safrs, "DB", wrapper)

    app = FastAPI(
        title="SAFRS FastAPI Models Demo",
        description=DESCRIPTION,
        docs_url="/docs",
        redoc_url=None,
    )

    @app.middleware("http")
    async def remove_session_middleware(request: Any, call_next: Any) -> Any:
        try:
            return await call_next(request)
        finally:
            Session.remove()

    api = SafrsFastAPI(app, prefix=API_PREFIX, relationship_item_mode=RelationshipItemMode.HIDDEN)
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
            "db": str(resolved_db_path),
            "api_prefix": API_PREFIX,
            "models": [model.__name__ for model in EXPOSED_MODELS],
        }

    return app


if __name__ == "__main__":
    import uvicorn

    bind_host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    bind_port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    uvicorn.run(create_app(), host=bind_host, port=bind_port)
