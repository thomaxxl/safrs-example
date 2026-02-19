import json
import sys
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from safrs.fastapi.openapi import diff_openapi_documents
from safrs.fastapi.openapi.normalize import InternalSpec, canonical_path, load_openapi3_as_internal, load_swagger2_as_internal

JSONAPI_MEDIA_TYPE = "application/vnd.api+json"


TMP_DIR = Path(__file__).resolve().parents[1] / "safrs" / "tmp"
if str(TMP_DIR) not in sys.path:
    sys.path.insert(0, str(TMP_DIR))

from export_specs import export_specs


@pytest.fixture(scope="module")
def specs() -> tuple[dict[str, Any], dict[str, Any]]:
    flask_path, fastapi_path = export_specs()
    flask_spec = json.loads(flask_path.read_text(encoding="utf-8"))
    fastapi_spec = json.loads(fastapi_path.read_text(encoding="utf-8"))
    return flask_spec, fastapi_spec


def _operation_query_names(spec: InternalSpec, path: str, method: str) -> set[str]:
    op = spec["operations"][(canonical_path(path), method)]
    return {param["name"] for param in op["parameters"] if param["in_"] == "query"}


def test_spec_parity_level1_operations_status_and_media(specs: tuple[dict[str, Any], dict[str, Any]]) -> None:
    flask_spec, fastapi_spec = specs
    report = diff_openapi_documents(flask_spec, fastapi_spec)
    fastapi_internal = load_openapi3_as_internal(fastapi_spec)

    assert report["missing_operations"] == []
    assert report["missing_tags"] == []
    assert report["missing_request_body"] == []

    create_op = fastapi_internal["operations"][(canonical_path("/api/People"), "post")]
    delete_op = fastapi_internal["operations"][(canonical_path("/api/People/{}"), "delete")]
    assert "201" in create_op["responses"]
    assert "204" in delete_op["responses"]

    collection_get = fastapi_internal["operations"][(canonical_path("/api/People"), "get")]
    for status_code in ("400", "403", "404", "409", "500"):
        assert status_code in collection_get["responses"]
        assert JSONAPI_MEDIA_TYPE in collection_get["responses"][status_code]


def test_spec_parity_level2_core_query_parameters(specs: tuple[dict[str, Any], dict[str, Any]]) -> None:
    flask_spec, fastapi_spec = specs
    report = diff_openapi_documents(flask_spec, fastapi_spec)
    flask_internal = load_swagger2_as_internal(flask_spec)
    fastapi_internal = load_openapi3_as_internal(fastapi_spec)

    assert report["missing_parameters"] == []

    core_operations = [
        ("/api/People", "get"),
        ("/api/People/{}", "get"),
        ("/api/People", "post"),
        ("/api/People/{}", "patch"),
        ("/api/People/{}/books_read", "get"),
    ]
    for path, method in core_operations:
        flask_query = _operation_query_names(flask_internal, path, method)
        fastapi_query = _operation_query_names(fastapi_internal, path, method)
        assert flask_query <= fastapi_query
