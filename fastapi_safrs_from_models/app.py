#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import inspect
import os
import sys
import types
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SAFRS_REPO_ROOT = WORKSPACE_ROOT / "safrs"
if str(SAFRS_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SAFRS_REPO_ROOT))

import safrs
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from safrs.fastapi.api import RelationshipItemMode, SafrsFastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

DEFAULT_MODELS_FILE = Path("/tmp/models.py")
DEFAULT_MODELS_PROJECT_ROOT = Path("/home/t/lab/ALS/ApiLogicProject")
DEFAULT_DB_PATH = Path("database/db.sqlite")
DEFAULT_API_PREFIX = "/api"


class SAFRSDBWrapper:
    def __init__(self, session: Any, model: Any) -> None:
        self.session = session
        self.Model = model


def _ensure_compat_modules() -> None:
    try:
        import flask_login  # noqa: F401
    except ModuleNotFoundError:
        module = types.ModuleType("flask_login")

        class UserMixin:  # pragma: no cover - fallback shim
            pass

        module.UserMixin = UserMixin
        sys.modules["flask_login"] = module

    try:
        import flask_sqlalchemy  # noqa: F401
    except ModuleNotFoundError:
        module = types.ModuleType("flask_sqlalchemy")
        default_meta = type("DefaultMeta", (type,), {})

        class SQLAlchemy:  # pragma: no cover - fallback shim
            model = types.SimpleNamespace(DefaultMeta=default_meta)

            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self.Model = object

        module.model = types.SimpleNamespace(DefaultMeta=default_meta)
        module.SQLAlchemy = SQLAlchemy
        sys.modules["flask_sqlalchemy"] = module


def _resolve_models_file(explicit: str | None = None) -> Path:
    value = explicit or os.environ.get("SAFRS_MODELS_FILE", str(DEFAULT_MODELS_FILE))
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (WORKSPACE_ROOT / path).resolve()


def _resolve_models_project_root(models_file: Path, explicit: str | None = None) -> Path:
    value = explicit or os.environ.get("SAFRS_MODELS_PROJECT_ROOT", "")
    if value.strip():
        path = Path(value).expanduser()
        if path.is_absolute():
            return path
        return (WORKSPACE_ROOT / path).resolve()

    if (DEFAULT_MODELS_PROJECT_ROOT / "database" / "system").exists():
        return DEFAULT_MODELS_PROJECT_ROOT

    db_dir = models_file.parent / "database"
    if db_dir.exists():
        return models_file.parent
    return models_file.parent


def _resolve_db_path(project_root: Path, explicit: str | None = None) -> Path:
    value = explicit or os.environ.get("SAFRS_SQLITE_PATH", "")
    if value.strip():
        path = Path(value).expanduser()
        if path.is_absolute():
            return path
        return (project_root / path).resolve()
    return (project_root / DEFAULT_DB_PATH).resolve()


def _load_models_module(models_file: Path, models_project_root: Path) -> Any:
    if str(models_project_root) not in sys.path:
        sys.path.insert(0, str(models_project_root))

    _ensure_compat_modules()
    spec = importlib.util.spec_from_file_location("external_models", str(models_file))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module spec from {models_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _collect_exposed_models(models_module: Any) -> list[type[Any]]:
    base = getattr(models_module, "Base", None)
    models: list[type[Any]] = []
    for value in vars(models_module).values():
        if not inspect.isclass(value):
            continue
        if getattr(value, "__module__", "") != models_module.__name__:
            continue
        if not getattr(value, "__tablename__", None):
            continue
        # Some generated SAFRS models inherit __abstract__ from a common base.
        # Treat a model as abstract only when it explicitly defines the flag.
        if bool(value.__dict__.get("__abstract__", False)):
            continue
        if inspect.isclass(base) and not issubclass(value, base):
            continue
        models.append(value)
    return sorted(models, key=lambda model: model.__name__)


def _create_session(db_path: Path) -> Any:
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return scoped_session(session_factory)


def create_app(
    models_file: str | None = None,
    models_project_root: str | None = None,
    db_path: str | None = None,
) -> FastAPI:
    resolved_models_file = _resolve_models_file(explicit=models_file)
    if not resolved_models_file.exists():
        raise FileNotFoundError(f"Models file does not exist: {resolved_models_file}")

    resolved_models_project_root = _resolve_models_project_root(
        models_file=resolved_models_file,
        explicit=models_project_root,
    )
    resolved_db_path = _resolve_db_path(project_root=resolved_models_project_root, explicit=db_path)

    models_module = _load_models_module(resolved_models_file, resolved_models_project_root)
    exposed_models = _collect_exposed_models(models_module)
    if not exposed_models:
        raise RuntimeError(f"No SAFRS/SQLAlchemy models discovered in {resolved_models_file}")

    Session = _create_session(resolved_db_path)
    wrapper = SAFRSDBWrapper(Session, getattr(models_module, "Base"))
    setattr(safrs, "DB", wrapper)

    api_prefix = os.environ.get("SAFRS_API_PREFIX", DEFAULT_API_PREFIX).strip() or DEFAULT_API_PREFIX
    app = FastAPI(
        title="External Models SAFRS FastAPI",
        description=f"SAFRS FastAPI exposing models from {resolved_models_file}",
        docs_url="/docs",
        redoc_url=None,
    )

    @app.middleware("http")
    async def remove_session_middleware(request: Any, call_next: Any) -> Any:
        try:
            return await call_next(request)
        finally:
            Session.remove()

    api = SafrsFastAPI(app, prefix=api_prefix, relationship_item_mode=RelationshipItemMode.HIDDEN)
    app.state.safrs_api = api
    for model in exposed_models:
        api.expose_object(model)

    @app.get("/", include_in_schema=False)
    def root() -> Any:
        return RedirectResponse(url=api_prefix)

    @app.get("/health", include_in_schema=False)
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "models_file": str(resolved_models_file),
            "models_project_root": str(resolved_models_project_root),
            "db": str(resolved_db_path),
            "api_prefix": api_prefix,
            "exposed_models": [model.__name__ for model in exposed_models],
        }

    return app


if __name__ == "__main__":
    import uvicorn

    bind_host = os.environ.get("HOST", "127.0.0.1")
    bind_port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(create_app(), host=bind_host, port=bind_port)
