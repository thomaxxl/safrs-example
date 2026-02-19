import re
from typing import Any

import pytest
from safrs.swagger_doc import schema_from_object, update_response_schema


def test_schema_from_object_types_dict_and_array(app):
    with app.app_context():
        schema = schema_from_object(
            "swagger_fix_schema_obj_arr",
            {
                "data": {"id": "1", "type": "Thing"},
                "items": [{"id": "1"}],
            },
        )

    assert schema.properties["data"]["type"] == "object"
    assert schema.properties["data"]["additionalProperties"] == {}
    assert schema.properties["data"]["example"]["id"] == "1"

    assert schema.properties["items"]["type"] == "array"
    assert schema.properties["items"]["items"]["type"] == "object"
    assert schema.properties["items"]["items"]["additionalProperties"] == {}
    assert schema.properties["items"]["example"][0]["id"] == "1"


def test_schema_from_object_type_boolean(app):
    with app.app_context():
        schema = schema_from_object("swagger_fix_schema_bool", {"active": True})

    assert schema.properties["active"]["type"] == "boolean"
    assert schema.properties["active"]["example"] is True


def test_update_response_schema_error_document_uses_array_for_errors(app):
    responses = {"404": {"description": "Not Found"}}

    with app.app_context():
        update_response_schema(responses)

    error_schema = responses["404"]["schema"]
    assert error_schema.properties["errors"]["type"] == "array"


def _canonical_path(path: str) -> str:
    normalized = path.rstrip("/") or "/"
    return re.sub(r"\{[^}]+\}", "{}", normalized)


def test_swagger_default_bad_request_response_is_documented(client):
    spec = client.get("/swagger.json").get_json()
    if spec.get("swagger") != "2.0":
        pytest.skip("Swagger 2.0 contract checks apply to Flask swagger output only")

    paths = spec["paths"]
    by_canonical = {_canonical_path(path): ops for path, ops in paths.items()}

    people_collection = by_canonical["/People"]
    people_instance = by_canonical["/People/{}"]
    book_author_relationship = by_canonical["/Books/{}/author"]

    for method in ("get", "post"):
        assert "400" in people_collection[method]["responses"]

    for method in ("get", "patch", "delete"):
        assert "400" in people_instance[method]["responses"]
        assert "400" in book_author_relationship[method]["responses"]


def _resolve_schema_ref(schema: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/definitions/"):
        return schema
    return spec["definitions"][ref.rsplit("/", 1)[1]]


def _body_schema(op: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    for parameter in op.get("parameters", []):
        if parameter.get("in") == "body":
            schema = parameter.get("schema", {})
            if isinstance(schema, dict):
                return _resolve_schema_ref(schema, spec)
    raise AssertionError("operation has no body schema")


def test_swagger_request_schemas_are_jsonapi_objects(client):
    spec = client.get("/swagger.json").get_json()
    if spec.get("swagger") != "2.0":
        pytest.skip("Swagger 2.0 contract checks apply to Flask swagger output only")

    paths = spec["paths"]
    by_canonical = {_canonical_path(path): ops for path, ops in paths.items()}

    people_post = by_canonical["/People"]["post"]
    people_patch = by_canonical["/People/{}"]["patch"]

    post_schema = _body_schema(people_post, spec)
    patch_schema = _body_schema(people_patch, spec)

    assert post_schema["type"] == "object"
    assert "data" in post_schema["required"]
    post_data_schema = _resolve_schema_ref(post_schema["properties"]["data"], spec)
    assert "type" in post_data_schema["required"]
    assert post_data_schema["properties"]["type"]["enum"] == ["Person"]
    assert "consumes" in people_post
    assert "application/vnd.api+json" in people_post["consumes"]

    assert patch_schema["type"] == "object"
    assert "data" in patch_schema["required"]
    patch_data_schema = _resolve_schema_ref(patch_schema["properties"]["data"], spec)
    assert {"id", "type"} <= set(patch_data_schema["required"])
    assert "consumes" in people_patch
    assert "application/vnd.api+json" in people_patch["consumes"]


def test_swagger_relationship_and_rpc_body_schemas_are_strict(client):
    spec = client.get("/swagger.json").get_json()
    if spec.get("swagger") != "2.0":
        pytest.skip("Swagger 2.0 contract checks apply to Flask swagger output only")

    paths = spec["paths"]
    by_canonical = {_canonical_path(path): ops for path, ops in paths.items()}

    books_author_patch = by_canonical["/Books/{}/author"]["patch"]
    author_patch_schema = _body_schema(books_author_patch, spec)
    author_data_schema = _resolve_schema_ref(author_patch_schema["properties"]["data"], spec)
    assert author_data_schema["type"] == "object"
    assert {"type", "id"} <= set(author_data_schema["required"])
    assert "consumes" in books_author_patch

    publishers_books_patch = by_canonical["/Publishers/{}/books"]["patch"]
    publisher_patch_schema = _body_schema(publishers_books_patch, spec)
    publisher_data_schema = _resolve_schema_ref(publisher_patch_schema["properties"]["data"], spec)
    assert publisher_data_schema["type"] == "array"
    items_schema = _resolve_schema_ref(publisher_data_schema["items"], spec)
    assert items_schema["type"] == "object"
    assert {"type", "id"} <= set(items_schema["required"])
    assert "consumes" in publishers_books_patch

    rpc_posts = [ops["post"] for path, ops in by_canonical.items() if path.endswith("/my_rpc") and "post" in ops]
    assert rpc_posts
    rpc_schema = _body_schema(rpc_posts[0], spec)
    assert rpc_schema["type"] == "object"
    assert "meta" in rpc_schema["required"]
    meta_schema = _resolve_schema_ref(rpc_schema["properties"]["meta"], spec)
    assert meta_schema["type"] == "object"
    assert "args" in meta_schema["required"]
    args_schema = _resolve_schema_ref(meta_schema["properties"]["args"], spec)
    assert args_schema["type"] == "object"


def test_swagger_paging_parameters_are_bounded(client):
    spec = client.get("/swagger.json").get_json()
    if spec.get("swagger") != "2.0":
        pytest.skip("Swagger 2.0 contract checks apply to Flask swagger output only")

    paths = spec["paths"]
    by_canonical = {_canonical_path(path): ops for path, ops in paths.items()}
    people_get = by_canonical["/People"]["get"]
    params = {param["name"]: param for param in people_get["parameters"]}
    assert params["page[offset]"]["minimum"] == 0
    assert params["page[offset]"]["maximum"] == 100000
    assert params["page[limit]"]["minimum"] == 1
    assert params["page[limit]"]["maximum"] == 100
