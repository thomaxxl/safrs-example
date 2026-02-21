from __future__ import annotations

import types
from pathlib import Path

from fastapi_safrs_from_models import app as app_module


def test_collect_exposed_models_filters_non_model_entries() -> None:
    module = types.ModuleType("dummy_models")

    class Base:
        __abstract__ = True

    class Visible(Base):
        __tablename__ = "visible"
        __module__ = "dummy_models"

    class Abstract(Base):
        __tablename__ = "abstract"
        __module__ = "dummy_models"
        __abstract__ = True

    class Imported(Base):
        __tablename__ = "imported"
        __module__ = "not_dummy_models"

    module.Base = Base
    module.Visible = Visible
    module.Abstract = Abstract
    module.Imported = Imported
    module.not_a_class = object()

    assert [model.__name__ for model in app_module._collect_exposed_models(module)] == ["Visible"]


def test_resolve_db_path_with_relative_override() -> None:
    project_root = Path("/tmp/example_project")
    resolved = app_module._resolve_db_path(project_root=project_root, explicit="db/custom.sqlite")
    assert resolved == Path("/tmp/example_project/db/custom.sqlite")


def test_resolve_models_file_relative_to_workspace() -> None:
    resolved = app_module._resolve_models_file(explicit="tmp/models.py")
    assert resolved == (app_module.WORKSPACE_ROOT / "tmp/models.py").resolve()
