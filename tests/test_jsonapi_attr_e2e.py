import hashlib
import re
from typing import Any

import pytest
import safrs
from flask import Flask
from werkzeug.datastructures import Headers

from app.base_model import db
from app.models import UserWithJsonapiAttr
from safrs import SAFRSAPI


class _SafrsClientMixin:
    @staticmethod
    def _headers(headers: Headers | None = None) -> Headers:
        merged = Headers()
        if headers:
            merged.extend(headers)
        merged.extend(Headers({"Content-Type": "application/vnd.api+json; ext=bulk"}))
        return merged


class JsonapiAttrClient(_SafrsClientMixin):
    def __init__(self, client: Any) -> None:
        self._client = client

    def open(self, *args: Any, **kwargs: Any) -> Any:
        kwargs["headers"] = self._headers(kwargs.pop("headers", None))
        return self._client.open(*args, **kwargs)

    def get(self, *args: Any, **kwargs: Any) -> Any:
        return self.open(*args, method="GET", **kwargs)

    def post(self, *args: Any, **kwargs: Any) -> Any:
        return self.open(*args, method="POST", **kwargs)

    def patch(self, *args: Any, **kwargs: Any) -> Any:
        return self.open(*args, method="PATCH", **kwargs)


@pytest.fixture(scope="session")
def app(tmp_path_factory: pytest.TempPathFactory) -> Any:
    sqlite_path = tmp_path_factory.mktemp("jsonapi_attr_e2e") / "jsonapi_attr.sqlite"
    app = Flask("jsonapi-attr-e2e")
    app.config.update(
        TESTING=True,
        DEBUG=True,
        SERVER_NAME="localhost",
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{sqlite_path}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)

    previous_db = safrs.DB
    safrs.DB = db

    with app.app_context():
        UserWithJsonapiAttr.__table__.create(bind=db.engine, checkfirst=True)
        yield app

    safrs.DB = previous_db


@pytest.fixture(scope="session")
def database(app: Any) -> None:
    return None


@pytest.fixture(scope="session")
def connection(app: Any, database: None) -> Any:
    connection = db.engine.connect()
    yield connection
    connection.close()


@pytest.fixture(scope="session", autouse=True)
def api(app: Any, database: None) -> Any:
    original_rpc_methods = UserWithJsonapiAttr._s_get_jsonapi_rpc_methods
    original_sample_id = UserWithJsonapiAttr._s_sample_id
    UserWithJsonapiAttr._s_get_jsonapi_rpc_methods = classmethod(lambda cls: [])
    UserWithJsonapiAttr._s_sample_id = classmethod(lambda cls: "jsonapi_id_string")
    with app.app_context():
        api = SAFRSAPI(app, app_db=db, host="localhost", port=5000)
        api.expose_object(UserWithJsonapiAttr)
        yield api
    UserWithJsonapiAttr._s_get_jsonapi_rpc_methods = original_rpc_methods
    UserWithJsonapiAttr._s_sample_id = original_sample_id


@pytest.fixture(scope="session")
def client(app: Any, api: Any) -> JsonapiAttrClient:
    with app.test_client() as flask_client:
        yield JsonapiAttrClient(flask_client)


def _secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_path(path: str) -> str:
    normalized = path.rstrip("/") or "/"
    return re.sub(r"\{[^}]+\}", "{}", normalized)


def _resolve_schema_ref(schema: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/definitions/"):
        return schema
    return spec["definitions"][ref.rsplit("/", 1)[1]]


def _body_schema(operation: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    for parameter in operation.get("parameters", []):
        if parameter.get("in") == "body":
            schema = parameter.get("schema", {})
            if isinstance(schema, dict):
                return _resolve_schema_ref(schema, spec)
    raise AssertionError("operation has no body schema")


def _response_schema(operation: dict[str, Any], spec: dict[str, Any], status_code: str = "200") -> dict[str, Any]:
    schema = operation["responses"][status_code].get("schema", {})
    if not isinstance(schema, dict):
        raise AssertionError("operation has no response schema")
    return _resolve_schema_ref(schema, spec)


def test_jsonapi_attr_post_and_patch_update_backing_storage(client: JsonapiAttrClient, db_session: Any) -> None:
    create_payload = {
        "data": {
            "type": "UserWithJsonapiAttr",
            "attributes": {
                "email": "jsonapi-create@example.com",
                "some_attr": "created-name",
                "secret": "initial-secret",
            },
        }
    }

    create_res = client.post("/UsersWithJsonapiAttr", json=create_payload)
    assert create_res.status_code == 201

    created_doc = create_res.get_json()["data"]
    created_id = created_doc["id"]
    created_attrs = created_doc["attributes"]

    assert created_attrs["some_attr"] == "some_value"
    assert created_attrs["readonly_value"] == "summary:created-name"
    assert "secret" not in created_attrs

    created_user = db_session.query(UserWithJsonapiAttr).filter_by(id=created_id).one()
    assert created_user.name == "created-name"
    assert created_user.email == "jsonapi-create@example.com"
    assert created_user.secret_store == _secret_hash("initial-secret")

    patch_payload = {
        "data": {
            "id": created_id,
            "type": "UserWithJsonapiAttr",
            "attributes": {
                "some_attr": "updated-name",
                "secret": "updated-secret",
            },
        }
    }

    patch_res = client.patch(f"/UsersWithJsonapiAttr/{created_id}", json=patch_payload)
    assert patch_res.status_code == 200

    patched_attrs = patch_res.get_json()["data"]["attributes"]
    assert patched_attrs["some_attr"] == "some_value"
    assert patched_attrs["readonly_value"] == "summary:updated-name"
    assert "secret" not in patched_attrs

    db_session.expire_all()
    patched_user = db_session.query(UserWithJsonapiAttr).filter_by(id=created_id).one()
    assert patched_user.name == "updated-name"
    assert patched_user.secret_store == _secret_hash("updated-secret")

    get_res = client.get(f"/UsersWithJsonapiAttr/{created_id}")
    assert get_res.status_code == 200
    get_attrs = get_res.get_json()["data"]["attributes"]
    assert get_attrs["readonly_value"] == "summary:updated-name"
    assert "secret" not in get_attrs


def test_jsonapi_attr_read_only_request_writes_are_rejected(client: JsonapiAttrClient, db_session: Any) -> None:
    invalid_email = "readonly-create@example.com"
    invalid_create_payload = {
        "data": {
            "type": "UserWithJsonapiAttr",
            "attributes": {
                "email": invalid_email,
                "some_attr": "created-name",
                "readonly_value": "summary:override",
            },
        }
    }

    create_res = client.post("/UsersWithJsonapiAttr", json=invalid_create_payload)
    assert create_res.status_code == 400
    create_errors = create_res.get_json()["errors"]
    assert any("readonly_value" in error.get("detail", "") for error in create_errors)
    assert any("read-only" in error.get("detail", "") for error in create_errors)
    assert db_session.query(UserWithJsonapiAttr).filter_by(email=invalid_email).one_or_none() is None

    valid_create_payload = {
        "data": {
            "type": "UserWithJsonapiAttr",
            "attributes": {
                "email": "readonly-patch@example.com",
                "some_attr": "stable-name",
            },
        }
    }
    valid_res = client.post("/UsersWithJsonapiAttr", json=valid_create_payload)
    assert valid_res.status_code == 201
    created_id = valid_res.get_json()["data"]["id"]

    invalid_patch_payload = {
        "data": {
            "id": created_id,
            "type": "UserWithJsonapiAttr",
            "attributes": {"readonly_value": "summary:override"},
        }
    }
    patch_res = client.patch(f"/UsersWithJsonapiAttr/{created_id}", json=invalid_patch_payload)
    assert patch_res.status_code == 400
    patch_errors = patch_res.get_json()["errors"]
    assert any("readonly_value" in error.get("detail", "") for error in patch_errors)
    assert any("read-only" in error.get("detail", "") for error in patch_errors)

    persisted_user = db_session.query(UserWithJsonapiAttr).filter_by(id=created_id).one()
    assert persisted_user.name == "stable-name"


def test_jsonapi_attr_flask_swagger_documents_request_and_response_fields(client: JsonapiAttrClient) -> None:
    spec = client.get("/swagger.json").get_json()
    assert spec.get("swagger") == "2.0"

    by_canonical = {_canonical_path(path): ops for path, ops in spec["paths"].items()}
    collection_post = by_canonical["/UsersWithJsonapiAttr"]["post"]
    instance_get = by_canonical["/UsersWithJsonapiAttr/{}"]["get"]

    post_schema = _body_schema(collection_post, spec)
    post_data_schema = _resolve_schema_ref(post_schema["properties"]["data"], spec)
    post_attrs_schema = _resolve_schema_ref(post_data_schema["properties"]["attributes"], spec)

    request_attrs = post_attrs_schema["properties"]
    response_example = _response_schema(instance_get, spec)["properties"]["data"]["example"]["attributes"]

    assert "some_attr" in request_attrs
    assert "secret" in request_attrs
    assert request_attrs["secret"]["format"] == "password"
    assert request_attrs["secret"]["default"] == "example-secret"
    assert "readonly_value" not in request_attrs
    assert "secret_store" not in request_attrs

    assert response_example["some_attr"] == "via-jsonapi-attr"
    assert response_example["readonly_value"] == "summary:jsonapi-attr-name"
    assert "secret" not in response_example
    assert "secret_store" not in response_example


def test_jsonapi_attr_fastapi_openapi_documents_examples_and_visibility(app: Any) -> None:
    pytest.importorskip("fastapi")
    from fastapi import FastAPI
    from safrs.fastapi import SafrsFastAPI

    with app.app_context():
        fastapi_app = FastAPI(openapi_url="/swagger.json", docs_url="/docs", redoc_url=None)
        api = SafrsFastAPI(fastapi_app)
        api.expose_object(UserWithJsonapiAttr)
        spec = fastapi_app.openapi()

    assert "openapi" in spec

    request_content = spec["paths"]["/UsersWithJsonapiAttr"]["post"]["requestBody"]["content"]["application/vnd.api+json"]
    request_example = request_content["example"]["data"]["attributes"]
    request_attr_schema = spec["components"]["schemas"]["UserWithJsonapiAttrRequestAttributes"]
    response_attr_schema = spec["components"]["schemas"]["UserWithJsonapiAttrAttributes"]
    response_example = response_attr_schema["examples"][0]

    assert request_example["secret"] == "example-secret"
    assert "readonly_value" not in request_example
    assert response_example["readonly_value"] == "summary:jsonapi-attr-name"
    assert "secret" not in response_example

    assert "secret" in request_attr_schema["properties"]
    assert request_attr_schema["properties"]["secret"]["format"] == "password"
    assert "readonly_value" not in request_attr_schema["properties"]
    assert "secret_store" not in request_attr_schema["properties"]

    assert "readonly_value" in response_attr_schema["properties"]
    assert "secret" not in response_attr_schema["properties"]
    assert "secret_store" not in response_attr_schema["properties"]
