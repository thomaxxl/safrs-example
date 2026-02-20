import sys
import json
from pathlib import Path

import pytest
import safrs

TMP_DIR = Path(__file__).resolve().parents[1] / "safrs" / "tmp"
if str(TMP_DIR) not in sys.path:
    sys.path.insert(0, str(TMP_DIR))

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
    seed = {"BookId": "book-uuid-1", "PersonId": "1", "FriendId": "2"}
    patched = _patch_spec_with_seed(spec, seed)

    author_patch_params = patched["paths"]["/api/Books/{BookId}/author"]["patch"]["parameters"]
    book_id_param = next(param for param in author_patch_params if param.get("name") == "BookId")
    assert book_id_param["enum"] == ["book-uuid-1"]
    assert book_id_param["default"] == "book-uuid-1"

    relationship_body = next(param for param in author_patch_params if param.get("in") == "body")["schema"]
    assert relationship_body["properties"]["data"]["properties"]["id"]["enum"] == ["1", "2"]

    review_body = patched["paths"]["/api/Reviews/"]["post"]["parameters"][0]["schema"]
    attrs = review_body["properties"]["data"]["properties"]["attributes"]["properties"]
    assert attrs["book_id"]["enum"] == ["book-uuid-1"]
    assert attrs["reader_id"]["enum"] == [1, 2]


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
    assert "Books.author" in payload["relationships"]
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
