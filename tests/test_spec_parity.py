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


def test_spec_parity_respects_model_http_methods(specs: tuple[dict[str, Any], dict[str, Any]]) -> None:
    flask_spec, fastapi_spec = specs
    flask_internal = load_swagger2_as_internal(flask_spec)
    fastapi_internal = load_openapi3_as_internal(fastapi_spec)
    review_get = (canonical_path("/api/Reviews/{}"), "get")
    review_patch = (canonical_path("/api/Reviews/{}"), "patch")
    review_delete = (canonical_path("/api/Reviews/{}"), "delete")

    assert review_patch not in flask_internal["operations"]
    assert review_delete not in flask_internal["operations"]
    assert review_patch not in fastapi_internal["operations"]
    assert review_delete not in fastapi_internal["operations"]
    assert review_get in flask_internal["operations"]
    assert review_get in fastapi_internal["operations"]

    for rel_path in ("/api/Reviews/{}/book", "/api/Reviews/{}/reader"):
        review_rel_get = (canonical_path(rel_path), "get")
        review_rel_patch = (canonical_path(rel_path), "patch")
        review_rel_post = (canonical_path(rel_path), "post")
        review_rel_delete = (canonical_path(rel_path), "delete")
        assert review_rel_get in flask_internal["operations"]
        assert review_rel_patch not in flask_internal["operations"]
        assert review_rel_post not in flask_internal["operations"]
        assert review_rel_delete not in flask_internal["operations"]
        assert review_rel_get in fastapi_internal["operations"]
        assert review_rel_patch not in fastapi_internal["operations"]
        assert review_rel_post not in fastapi_internal["operations"]
        assert review_rel_delete not in fastapi_internal["operations"]


def test_spec_parity_to_one_relationships_do_not_expose_post(specs: tuple[dict[str, Any], dict[str, Any]]) -> None:
    flask_spec, fastapi_spec = specs
    flask_internal = load_swagger2_as_internal(flask_spec)
    fastapi_internal = load_openapi3_as_internal(fastapi_spec)

    for rel_path in ("/api/Books/{}/author", "/api/Books/{}/publisher"):
        rel_get = (canonical_path(rel_path), "get")
        rel_patch = (canonical_path(rel_path), "patch")
        rel_delete = (canonical_path(rel_path), "delete")
        rel_post = (canonical_path(rel_path), "post")
        assert rel_get in flask_internal["operations"]
        assert rel_patch in flask_internal["operations"]
        assert rel_delete in flask_internal["operations"]
        assert rel_post not in flask_internal["operations"]
        assert rel_get in fastapi_internal["operations"]
        assert rel_patch in fastapi_internal["operations"]
        assert rel_delete in fastapi_internal["operations"]
        assert rel_post not in fastapi_internal["operations"]


def test_spec_parity_relationship_item_paths_not_documented(specs: tuple[dict[str, Any], dict[str, Any]]) -> None:
    _flask_spec, fastapi_spec = specs
    paths = fastapi_spec.get("paths", {})

    assert "/api/Books/{object_id}/author/{target_id}" not in paths
    assert "/api/Books/{object_id}/publisher/{target_id}" not in paths
    assert "/api/People/{object_id}/books_read/{target_id}" not in paths
    assert "/api/People/{object_id}/friends/{target_id}" not in paths
    assert "/api/Publishers/{object_id}/books/{target_id}" not in paths
    assert "/api/Reviews/{object_id}/reader/{target_id}" not in paths


def test_spec_parity_openapi_request_body_examples_present(specs: tuple[dict[str, Any], dict[str, Any]]) -> None:
    _flask_spec, fastapi_spec = specs
    paths = fastapi_spec.get("paths", {})

    people_post = paths["/api/People"]["post"]["requestBody"]["content"][JSONAPI_MEDIA_TYPE]
    people_patch = paths["/api/People/{object_id}"]["patch"]["requestBody"]["content"][JSONAPI_MEDIA_TYPE]
    books_read_patch = paths["/api/People/{object_id}/books_read"]["patch"]["requestBody"]["content"][JSONAPI_MEDIA_TYPE]
    author_patch = paths["/api/Books/{object_id}/author"]["patch"]["requestBody"]["content"][JSONAPI_MEDIA_TYPE]

    people_post_example = people_post.get("example")
    people_patch_example = people_patch.get("example")
    books_read_patch_example = books_read_patch.get("example")
    author_patch_example = author_patch.get("example")

    assert isinstance(people_post_example, dict)
    assert people_post_example["data"]["type"] == "Person"
    assert "attributes" in people_post_example["data"]

    assert isinstance(people_patch_example, dict)
    assert people_patch_example["data"]["type"] == "Person"
    assert "id" in people_patch_example["data"]
    assert "attributes" in people_patch_example["data"]

    assert isinstance(books_read_patch_example, dict)
    assert isinstance(books_read_patch_example["data"], list)
    assert books_read_patch_example["data"][0]["type"] == "Book"
    assert "id" in books_read_patch_example["data"][0]

    assert isinstance(author_patch_example, dict)
    assert author_patch_example["data"]["type"] == "Person"
    assert "id" in author_patch_example["data"]


def test_spec_parity_hidden_relationships_not_documented(specs: tuple[dict[str, Any], dict[str, Any]]) -> None:
    _flask_spec, fastapi_spec = specs
    paths = fastapi_spec.get("paths", {})

    assert "/api/People/{object_id}/employer" not in paths
    assert "/api/People/{object_id}/employer/{target_id}" not in paths
    assert "/api/Publishers/{object_id}/employees" not in paths
    assert "/api/Publishers/{object_id}/employees/{target_id}" not in paths

    schemas = fastapi_spec.get("components", {}).get("schemas", {})
    person_relationships = schemas.get("PersonRelationships", {})
    publisher_relationships = schemas.get("PublisherRelationships", {})
    person_props = person_relationships.get("properties", {})
    publisher_props = publisher_relationships.get("properties", {})

    assert "employer" not in person_props
    assert "employees" not in publisher_props
