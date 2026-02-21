from __future__ import annotations

from pathlib import Path

from fastapi_safrs_from_models import app as app_module
from fastapi_safrs_from_models import models as models_module


def test_exposed_models_are_declared() -> None:
    model_names = {model.__name__ for model in models_module.EXPOSED_MODELS}
    assert "Customer" in model_names
    assert "Order" in model_names
    assert len(models_module.EXPOSED_MODELS) >= 10


def test_resolve_db_path_defaults_to_models_default() -> None:
    assert app_module._resolve_db_path() == models_module.DEFAULT_DB_PATH


def test_resolve_db_path_with_relative_override() -> None:
    resolved = app_module._resolve_db_path(explicit_db_path="db/custom.sqlite")
    assert resolved == (app_module.PROJECT_ROOT / "db/custom.sqlite").resolve()


def test_create_app_smoke(tmp_path: Path) -> None:
    app = app_module.create_app(db_path=str(tmp_path / "smoke.sqlite"))
    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/health" in paths
