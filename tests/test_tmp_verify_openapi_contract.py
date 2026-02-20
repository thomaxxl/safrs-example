import sys
import json
from http import HTTPStatus
from pathlib import Path

import pytest
import safrs

TMP_DIR = Path(__file__).resolve().parents[1] / "safrs" / "tmp"
if str(TMP_DIR) not in sys.path:
    sys.path.insert(0, str(TMP_DIR))

import verify_openapi_contract as contract_verifier
from verify_openapi_contract import _patch_spec_with_seed


def test_patch_spec_with_seed_sets_path_and_body_enums() -> None:
    spec = {
        "swagger": "2.0",
        "paths": {
            "/api/Books/{BookId}/author": {
                "patch": {
                    "parameters": [
                        {"name": "BookId", "in": "path", "type": "string"},
                        {
                            "name": "body",
                            "in": "body",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "data": {
                                        "type": "object",
                                        "properties": {
                                            "type": {"type": "string", "enum": ["Person"]},
                                            "id": {"type": "string"},
                                        },
                                    }
                                },
                            },
                        },
                    ]
                }
            },
            "/api/Reviews/": {
                "post": {
                    "parameters": [
                        {
                            "name": "POST body",
                            "in": "body",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "data": {
                                        "type": "object",
                                        "properties": {
                                            "attributes": {
                                                "type": "object",
                                                "properties": {
                                                    "book_id": {"type": "string"},
                                                    "reader_id": {"type": "integer"},
                                                },
                                            }
                                        },
                                    }
                                },
                            },
                        }
                    ]
                }
            },
        },
        "definitions": {},
    }
    seed = {
        "BookId": "book-uuid-1",
        "PersonId": "1",
        "FriendId": "2",
        "relationships": {"Books.author": {"data": {"type": "Person", "id": "1"}}},
    }
    patched = _patch_spec_with_seed(spec, seed)

    author_patch_params = patched["paths"]["/api/Books/{BookId}/author"]["patch"]["parameters"]
    book_id_param = next(param for param in author_patch_params if param.get("name") == "BookId")
    assert book_id_param["enum"] == ["book-uuid-1"]
    assert book_id_param["default"] == "book-uuid-1"

    relationship_body = next(param for param in author_patch_params if param.get("in") == "body")["schema"]
    assert relationship_body["properties"]["data"]["properties"]["id"]["enum"] == ["1"]
    assert relationship_body["properties"]["data"]["properties"]["id"]["default"] == "1"

    review_body = patched["paths"]["/api/Reviews/"]["post"]["parameters"][0]["schema"]
    attrs = review_body["properties"]["data"]["properties"]["attributes"]["properties"]
    assert attrs["book_id"]["enum"] == ["book-uuid-1"]
    assert attrs["reader_id"]["enum"] == [1, 2]


def test_patch_spec_with_seed_relationship_to_many_uses_seed_linkage() -> None:
    spec = {
        "swagger": "2.0",
        "paths": {
            "/api/Books/{BookId}/reviews": {
                "patch": {
                    "summary": "Update Book.reviews",
                    "description": "Update the Book reviews relationship",
                    "parameters": [
                        {"name": "BookId", "in": "path", "type": "string"},
                        {
                            "name": "body",
                            "in": "body",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "data": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "type": {"type": "string", "enum": ["Review"]},
                                                "id": {"type": "string"},
                                            },
                                        },
                                    }
                                },
                            },
                        },
                    ],
                }
            }
        },
    }
    seed = {
        "BookId": "book-1",
        "relationships": {
            "Books.reviews": {
                "data": [
                    {"type": "Review", "id": "book-1_1"},
                    {"type": "Review", "id": "book-1_2"},
                ]
            }
        },
    }

    patched = _patch_spec_with_seed(spec, seed)
    op = patched["paths"]["/api/Books/{BookId}/reviews"]["patch"]
    body_schema = next(param for param in op["parameters"] if param.get("in") == "body")["schema"]
    data_schema = body_schema["properties"]["data"]
    assert data_schema["minItems"] == 2
    assert data_schema["maxItems"] == 2
    assert data_schema["items"]["properties"]["id"]["enum"] == ["book-1_1", "book-1_2"]
    assert data_schema["items"]["properties"]["id"]["default"] == "book-1_1"
    assert data_schema["items"]["properties"]["type"]["enum"] == ["Review"]
    assert data_schema["items"]["properties"]["type"]["default"] == "Review"


def test_patch_spec_with_seed_relationship_missing_seed_entry_raises() -> None:
    spec = {
        "swagger": "2.0",
        "paths": {
            "/api/Books/{BookId}/reviews": {
                "patch": {
                    "description": "Update the Book reviews relationship",
                    "parameters": [
                        {
                            "name": "body",
                            "in": "body",
                            "schema": {
                                "type": "object",
                                "properties": {"data": {"type": "array", "items": {"type": "object"}}},
                            },
                        }
                    ],
                }
            }
        },
    }
    seed = {"BookId": "book-1", "relationships": {}}

    with pytest.raises(RuntimeError, match="Missing seed relationship payload for Books.reviews"):
        _patch_spec_with_seed(spec, seed)


def test_patch_spec_with_seed_relationship_cardinality_mismatch_raises() -> None:
    spec = {
        "swagger": "2.0",
        "paths": {
            "/api/Books/{BookId}/reviews": {
                "patch": {
                    "description": "Update the Book reviews relationship",
                    "parameters": [
                        {
                            "name": "body",
                            "in": "body",
                            "schema": {
                                "type": "object",
                                "properties": {"data": {"type": "array", "items": {"type": "object"}}},
                            },
                        }
                    ],
                }
            }
        },
    }
    seed = {"relationships": {"Books.reviews": {"data": {"type": "Review", "id": "book-1_1"}}}}

    with pytest.raises(RuntimeError, match="must use array data"):
        _patch_spec_with_seed(spec, seed)


def test_patch_spec_with_seed_relationship_type_mismatch_raises() -> None:
    spec = {
        "swagger": "2.0",
        "paths": {
            "/api/Books/{BookId}/reviews": {
                "patch": {
                    "description": "Update the Book reviews relationship",
                    "parameters": [
                        {
                            "name": "body",
                            "in": "body",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "data": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {"type": {"type": "string", "enum": ["Review"]}},
                                        },
                                    }
                                },
                            },
                        }
                    ],
                }
            }
        },
    }
    seed = {"relationships": {"Books.reviews": {"data": [{"type": "Person", "id": "1"}]}}}

    with pytest.raises(RuntimeError, match="incompatible types"):
        _patch_spec_with_seed(spec, seed)


def test_patch_spec_with_seed_ignores_rpc_paths_for_relationship_strictness() -> None:
    spec = {
        "swagger": "2.0",
        "paths": {
            "/api/People/{PersonId}/send_mail": {
                "post": {
                    "summary": "Invoke Person.send_mail",
                    "parameters": [
                        {"name": "PersonId", "in": "path", "type": "string"},
                        {
                            "name": "body",
                            "in": "body",
                            "schema": {
                                "type": "object",
                                "properties": {"meta": {"type": "object", "properties": {"args": {"type": "object"}}}},
                            },
                        },
                    ],
                }
            }
        },
    }
    seed = {"PersonId": "1", "relationships": {}}

    patched = _patch_spec_with_seed(spec, seed)
    params = patched["paths"]["/api/People/{PersonId}/send_mail"]["post"]["parameters"]
    person_param = next(param for param in params if param.get("name") == "PersonId")
    assert person_param["enum"] == ["1"]
    assert person_param["default"] == "1"


def test_tmp_flask_seed_endpoint_returns_stable_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    from flask_app import create_app as create_tmp_flask_app

    monkeypatch.setenv("SAFRS_TMP_RESET_DB", "1")
    original_db = getattr(safrs, "DB", None)
    try:
        app = create_tmp_flask_app(db_name="tmp_flask_seed_contract_test.db")
        with app.test_client() as client:
            response = client.get("/seed")
    finally:
        setattr(safrs, "DB", original_db)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["BookId"]
    assert payload["PersonId"]
    assert payload["PublisherId"]
    assert payload["ReviewId"]
    assert "People.friends" in payload["relationships"]
    assert "People.books_read" in payload["relationships"]
    assert "People.books_written" in payload["relationships"]
    assert "People.reviews" in payload["relationships"]
    assert "Books.author" in payload["relationships"]
    assert "Books.reader" in payload["relationships"]
    assert "Books.publisher" in payload["relationships"]
    assert "Books.reviews" in payload["relationships"]
    assert "Publishers.books" in payload["relationships"]


def test_tmp_fastapi_seed_endpoint_returns_stable_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from fastapi_app import create_app as create_tmp_fastapi_app

    monkeypatch.setenv("SAFRS_TMP_RESET_DB", "1")
    original_db = getattr(safrs, "DB", None)
    try:
        app = create_tmp_fastapi_app(db_name="tmp_fastapi_seed_contract_test.db")
        with TestClient(app) as client:
            response = client.get("/seed")
    finally:
        setattr(safrs, "DB", original_db)
    assert response.status_code == 200
    payload = response.json()
    assert payload["BookId"]
    assert payload["PersonId"]
    assert payload["PublisherId"]
    assert payload["ReviewId"]
    assert payload["relationships"]["People.friends"]["data"]
    assert payload["relationships"]["People.books_read"]["data"]
    assert payload["relationships"]["People.books_written"]["data"]
    assert payload["relationships"]["People.reviews"]["data"]
    assert payload["relationships"]["Books.author"]["data"]["id"]
    assert payload["relationships"]["Books.reader"]["data"]["id"]
    assert payload["relationships"]["Books.publisher"]["data"]["id"]
    assert payload["relationships"]["Books.reviews"]["data"]
    assert payload["relationships"]["Publishers.books"]["data"]


def test_tmp_flask_spec_seed_patch_requires_relationship_seed_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    from flask_app import create_app as create_tmp_flask_app

    monkeypatch.setenv("SAFRS_TMP_RESET_DB", "1")
    original_db = getattr(safrs, "DB", None)
    try:
        app = create_tmp_flask_app(db_name="tmp_flask_seed_relationship_strictness.db")
        with app.test_client() as client:
            spec = client.get("/api/swagger.json").get_json()
            seed = client.get("/seed").get_json()
    finally:
        setattr(safrs, "DB", original_db)

    _patch_spec_with_seed(spec, seed)
    broken_seed = json.loads(json.dumps(seed))
    broken_seed["relationships"].pop("Books.reviews", None)
    with pytest.raises(RuntimeError, match="Missing seed relationship payload for Books.reviews"):
        _patch_spec_with_seed(spec, broken_seed)


def test_tmp_flask_relationship_clear_returns_controlled_client_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from flask_app import create_app as create_tmp_flask_app

    monkeypatch.setenv("SAFRS_TMP_RESET_DB", "1")
    original_db = getattr(safrs, "DB", None)
    try:
        app = create_tmp_flask_app(db_name="tmp_flask_relationship_clear_guard.db")
        with app.test_client() as client:
            seed = client.get("/seed").get_json()
            book_response = client.patch(f"/api/Books/{seed['BookId']}/reviews", json={"data": []})
            person_response = client.patch(f"/api/People/{seed['PersonId']}/reviews", json={"data": []})
    finally:
        setattr(safrs, "DB", original_db)

    for response in (book_response, person_response):
        assert response.status_code in {HTTPStatus.FORBIDDEN, HTTPStatus.CONFLICT}
        payload = response.get_json()
        assert isinstance(payload, dict)
        assert "errors" in payload
        assert response.status_code != HTTPStatus.INTERNAL_SERVER_ERROR


def test_tmp_flask_publishers_filter_returns_collection_document(monkeypatch: pytest.MonkeyPatch) -> None:
    from flask_app import create_app as create_tmp_flask_app

    monkeypatch.setenv("SAFRS_TMP_RESET_DB", "1")
    original_db = getattr(safrs, "DB", None)
    try:
        app = create_tmp_flask_app(db_name="tmp_flask_publishers_filter_contract_test.db")
        with app.test_client() as client:
            response = client.get(
                "/api/Publishers/",
                query_string={"filter": json.dumps([{"name": "name", "op": "ilike", "val": "publisher%"}])},
            )
    finally:
        setattr(safrs, "DB", original_db)

    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, dict)
    assert isinstance(payload.get("data"), list)


def test_tmp_flask_books_post_oversized_integer_returns_client_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from flask_app import create_app as create_tmp_flask_app

    monkeypatch.setenv("SAFRS_TMP_RESET_DB", "1")
    original_db = getattr(safrs, "DB", None)
    try:
        app = create_tmp_flask_app(db_name="tmp_flask_books_post_overflow_test.db")
        with app.test_client() as client:
            response = client.post(
                "/api/Books/",
                json={
                    "data": {
                        "type": "Book",
                        "attributes": {"reader_id": 9223372036854775808},
                    }
                },
            )
    finally:
        setattr(safrs, "DB", original_db)

    assert response.status_code == 400
    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "errors" in payload


def test_tmp_flask_books_patch_oversized_integer_returns_client_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from flask_app import create_app as create_tmp_flask_app

    monkeypatch.setenv("SAFRS_TMP_RESET_DB", "1")
    original_db = getattr(safrs, "DB", None)
    try:
        app = create_tmp_flask_app(db_name="tmp_flask_books_patch_overflow_test.db")
        with app.test_client() as client:
            seed = client.get("/seed").get_json()
            response = client.patch(
                f"/api/Books/{seed['BookId']}/",
                json={
                    "data": {
                        "type": "Book",
                        "id": seed["BookId"],
                        "attributes": {"reader_id": 9223372036854775808},
                    }
                },
            )
    finally:
        setattr(safrs, "DB", original_db)

    assert response.status_code == 400
    payload = response.get_json()
    assert isinstance(payload, dict)
    assert "errors" in payload


def test_tmp_flask_swagger_rpc_instance_method_documents_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    from flask_app import create_app as create_tmp_flask_app

    monkeypatch.setenv("SAFRS_TMP_RESET_DB", "1")
    original_db = getattr(safrs, "DB", None)
    try:
        app = create_tmp_flask_app(db_name="tmp_flask_rpc_404_swagger_test.db")
        with app.test_client() as client:
            spec = client.get("/api/swagger.json").get_json()
    finally:
        setattr(safrs, "DB", original_db)

    send_mail_post = spec["paths"]["/People/{PersonId}/send_mail"]["post"]
    assert "404" in send_mail_post["responses"]


def test_prepare_spec_for_run_applies_seed_patch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec_path = tmp_path / "swagger.json"
    spec_path.write_text(
        json.dumps(
            {
                "swagger": "2.0",
                "paths": {
                    "/api/Books/{BookId}/": {
                        "get": {
                            "parameters": [{"name": "BookId", "in": "path", "type": "string"}],
                            "responses": {"200": {"description": "ok"}},
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(contract_verifier, "_fetch_seed_payload", lambda *_a, **_k: {"BookId": "book-seed-1"})
    prepared_path, should_cleanup = contract_verifier._prepare_spec_for_run(spec_path, "http://127.0.0.1:1", 1.0)
    try:
        assert should_cleanup is True
        assert prepared_path != spec_path
        patched = json.loads(prepared_path.read_text(encoding="utf-8"))
        param = patched["paths"]["/api/Books/{BookId}/"]["get"]["parameters"][0]
        assert param["enum"] == ["book-seed-1"]
        assert param["default"] == "book-seed-1"
    finally:
        if should_cleanup and prepared_path.exists():
            prepared_path.unlink()


def test_prepare_spec_for_run_without_seed_uses_original(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec_path = tmp_path / "swagger.json"
    spec_path.write_text(json.dumps({"swagger": "2.0", "paths": {}}), encoding="utf-8")

    monkeypatch.setattr(contract_verifier, "_fetch_seed_payload", lambda *_a, **_k: {})
    prepared_path, should_cleanup = contract_verifier._prepare_spec_for_run(spec_path, "http://127.0.0.1:1", 1.0)
    assert should_cleanup is False
    assert prepared_path == spec_path
