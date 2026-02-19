import json
from types import SimpleNamespace
from typing import Any, Generator

import pytest

import safrs
from safrs.api_methods import duplicate
from safrs import SAFRSBase
from safrs.errors import JsonapiError, SystemValidationError, ValidationError
from safrs.swagger_doc import jsonapi_rpc
from sqlalchemy import Column, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, relationship, scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

pytest.importorskip("fastapi")
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel
from safrs.fastapi.api import JSONAPIHTTPError, JSONAPI_MEDIA_TYPE, SafrsFastAPI, install_jsonapi_exception_handlers
from safrs.fastapi.responses import JSONAPIResponse


Base = declarative_base()


class _SAFRSDBWrapper:
    def __init__(self, session: Any, model: Any) -> None:
        self.session = session
        self.Model = model


class FastAuthor(SAFRSBase, Base):
    __tablename__ = "FastAuthors"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    duplicate = duplicate

    @classmethod
    @jsonapi_rpc(http_methods=["POST"])
    def lookup_by_name(cls, name: str = "") -> dict[str, Any]:
        return {"meta": {"name": name, "count": cls.query.filter_by(name=name).count()}}


class FastBook(SAFRSBase, Base):
    __tablename__ = "FastBooks"
    _s_allow_add_rels = True

    id = Column(Integer, primary_key=True)
    title = Column(String)
    author_id = Column(Integer, ForeignKey("FastAuthors.id"))
    author = relationship("FastAuthor", backref="books")


class FastThing(SAFRSBase, Base):
    __tablename__ = "FastThings"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)

    @jsonapi_rpc(http_methods=["POST"])
    def prefix_name(self, prefix: str = "") -> dict[str, Any]:
        return {"meta": {"value": f"{prefix}{self.name}"}}


class FastLimitedThing(SAFRSBase, Base):
    __tablename__ = "FastLimitedThings"
    http_methods = {"GET", "POST"}

    id = Column(Integer, primary_key=True)
    name = Column(String)


class FastLimitedThingCSV(SAFRSBase, Base):
    __tablename__ = "FastLimitedThingsCSV"
    http_methods = "GET,POST"

    id = Column(Integer, primary_key=True)
    name = Column(String)


def _request(query: str = "") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": query.encode(),
        }
    )


def _response_schema_ref(operation: dict[str, Any], status_code: str) -> str:
    response = operation["responses"][status_code]
    content = response.get("content", {})
    if JSONAPI_MEDIA_TYPE in content:
        return content[JSONAPI_MEDIA_TYPE]["schema"]["$ref"]
    if "application/json" in content:
        return content["application/json"]["schema"]["$ref"]
    first_media = next(iter(content.values()))
    return first_media["schema"]["$ref"]


def _query_param_names(operation: dict[str, Any]) -> set[str]:
    return {
        str(parameter.get("name"))
        for parameter in operation.get("parameters", [])
        if parameter.get("in") == "query"
    }


def _json_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, JSONAPIResponse):
        return json.loads(value.body.decode())
    return value


@pytest.fixture()
def fastapi_client() -> Generator[TestClient, None, None]:
    original_db = safrs.DB
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))
    safrs.DB = _SAFRSDBWrapper(Session, Base)
    Base.metadata.create_all(engine)

    try:
        author = FastAuthor(name="author-1")
        author2 = FastAuthor(name="author-2")
        book = FastBook(title="book-1", author=author)
        book2 = FastBook(title="book-3", author=author)
        book3 = FastBook(title="book-2", author=author)
        book4 = FastBook(title="book-0", author=author2)
        thing_a = FastThing(name="alpha", description="A")
        thing_b = FastThing(name="beta", description="B")
        Session.add_all([author, author2, book, book2, book3, book4, thing_a, thing_b])
        Session.commit()

        app = FastAPI()

        @app.middleware("http")
        async def remove_session_middleware(request: Request, call_next):
            try:
                return await call_next(request)
            finally:
                Session.remove()

        api = SafrsFastAPI(app)
        app.state.safrs_api = api
        api.expose_object(FastThing)
        api.expose_object(FastAuthor)
        api.expose_object(FastBook)

        with TestClient(app) as client:
            yield client
    finally:
        Session.remove()
        Base.metadata.drop_all(engine)
        safrs.DB = original_db


def test_fastapi_expose_object_rejects_s_expose_false() -> None:
    class Hidden:
        _s_expose = False

    api = SafrsFastAPI(FastAPI())
    with pytest.raises(SystemValidationError):
        api.expose_object(Hidden)


def test_fastapi_expose_object_rejects_method_decorators() -> None:
    class Visible:
        _s_expose = True

    api = SafrsFastAPI(FastAPI())
    with pytest.raises(NotImplementedError):
        api.expose_object(Visible, method_decorators=[lambda f: f])


def test_fastapi_expose_object_relationship_routes_use_resolved_relationships(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    api = SafrsFastAPI(app)
    monkeypatch.setattr(api, "_resolve_relationships", lambda _model: {})
    api.expose_object(FastBook)

    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/FastBooks/{object_id}/author" not in paths
    assert "/FastBooks/{object_id}/author/{target_id}" not in paths
    assert "/FastBooks" in paths


def test_fastapi_swagger_alias_and_slash_parity(fastapi_client: TestClient) -> None:
    response = fastapi_client.get("/swagger.json")
    assert response.status_code == 200
    assert "openapi" in response.json()

    no_slash = fastapi_client.get("/FastThings")
    assert no_slash.status_code == 200

    with_slash = fastapi_client.get("/FastThings/")
    assert with_slash.status_code == 200


def test_fastapi_openapi_documents_generated_models(fastapi_client: TestClient) -> None:
    response = fastapi_client.get("/openapi.json")
    assert response.status_code == 200
    openapi = response.json()

    schemas = openapi["components"]["schemas"]
    assert "FastThingAttributes" in schemas
    assert "FastThingResource" in schemas
    assert "FastThingDocumentSingle" in schemas
    assert "FastThingDocumentCollection" in schemas
    assert "FastBookRelationships" in schemas
    assert "JsonApiErrorDocument" in schemas

    paths = openapi["paths"]
    things_get = paths["/FastThings"]["get"]
    things_post = paths["/FastThings"]["post"]
    thing_patch = paths["/FastThings/{object_id}"]["patch"]

    assert _response_schema_ref(things_get, "200").endswith("/FastThingDocumentCollection")
    assert _response_schema_ref(things_post, "201").endswith("/FastThingDocumentSingle")
    assert _response_schema_ref(thing_patch, "200").endswith("/FastThingDocumentSingle")
    assert _response_schema_ref(things_get, "400").endswith("/JsonApiErrorDocument")

    post_request_ref = things_post["requestBody"]["content"][JSONAPI_MEDIA_TYPE]["schema"]["$ref"]
    patch_request_ref = thing_patch["requestBody"]["content"][JSONAPI_MEDIA_TYPE]["schema"]["$ref"]
    assert post_request_ref.endswith("/FastThingDocumentCreate")
    assert patch_request_ref.endswith("/FastThingDocumentPatch")
    assert "204" in paths["/FastThings/{object_id}"]["delete"]["responses"]
    assert JSONAPI_MEDIA_TYPE in things_post["responses"]["422"]["content"]
    assert things_post["responses"]["422"]["content"][JSONAPI_MEDIA_TYPE]["schema"]["$ref"].endswith("/JsonApiErrorDocument")


def test_fastapi_crud_route_registration_respects_model_http_methods() -> None:
    original_db = safrs.DB
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))
    safrs.DB = _SAFRSDBWrapper(Session, Base)
    Base.metadata.create_all(engine)

    try:
        Session.add(FastLimitedThing(name="limited"))
        Session.commit()

        app = FastAPI()
        api = SafrsFastAPI(app)
        api.expose_object(FastLimitedThing)

        with TestClient(app) as client:
            paths = client.get("/openapi.json").json()["paths"]
            collection_path = "/FastLimitedThings"
            instance_path = "/FastLimitedThings/{object_id}"

            assert "get" in paths[collection_path]
            assert "post" in paths[collection_path]
            assert "get" in paths[instance_path]
            assert "patch" not in paths[instance_path]
            assert "delete" not in paths[instance_path]

            patch_response = client.patch(
                "/FastLimitedThings/1",
                json={"data": {"id": "1", "type": "FastLimitedThing", "attributes": {"name": "x"}}},
            )
            assert patch_response.status_code == 405
            payload = patch_response.json()
            assert "errors" in payload
            assert payload["errors"][0]["status"] == "405"
    finally:
        Session.remove()
        Base.metadata.drop_all(engine)
        safrs.DB = original_db


def test_fastapi_crud_route_registration_respects_csv_model_http_methods() -> None:
    original_db = safrs.DB
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))
    safrs.DB = _SAFRSDBWrapper(Session, Base)
    Base.metadata.create_all(engine)

    try:
        Session.add(FastLimitedThingCSV(name="limited-csv"))
        Session.commit()

        app = FastAPI()
        api = SafrsFastAPI(app)
        api.expose_object(FastLimitedThingCSV)

        with TestClient(app) as client:
            paths = client.get("/openapi.json").json()["paths"]
            collection_path = "/FastLimitedThingsCSV"
            instance_path = "/FastLimitedThingsCSV/{object_id}"

            assert "get" in paths[collection_path]
            assert "post" in paths[collection_path]
            assert "get" in paths[instance_path]
            assert "patch" not in paths[instance_path]
            assert "delete" not in paths[instance_path]

            patch_response = client.patch(
                "/FastLimitedThingsCSV/1",
                json={"data": {"id": "1", "type": "FastLimitedThingCSV", "attributes": {"name": "x"}}},
            )
            assert patch_response.status_code == 405
    finally:
        Session.remove()
        Base.metadata.drop_all(engine)
        safrs.DB = original_db


def test_fastapi_openapi_relationship_docs_use_resource_docs_for_get_and_linkage_for_mutations(
    fastapi_client: TestClient,
) -> None:
    response = fastapi_client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]

    author_rel = paths["/FastBooks/{object_id}/author"]
    books_rel = paths["/FastAuthors/{object_id}/books"]
    books_rel_item = paths["/FastAuthors/{object_id}/books/{target_id}"]

    assert _response_schema_ref(author_rel["get"], "200").endswith("/FastAuthorDocumentSingle")
    assert _response_schema_ref(books_rel["get"], "200").endswith("/FastBookDocumentCollection")
    assert _response_schema_ref(books_rel_item["get"], "200").endswith("/FastBookDocumentSingle")

    author_patch_ref = author_rel["patch"]["requestBody"]["content"][JSONAPI_MEDIA_TYPE]["schema"]["$ref"]
    author_post_ref = author_rel["post"]["requestBody"]["content"][JSONAPI_MEDIA_TYPE]["schema"]["$ref"]
    books_patch_ref = books_rel["patch"]["requestBody"]["content"][JSONAPI_MEDIA_TYPE]["schema"]["$ref"]
    books_post_ref = books_rel["post"]["requestBody"]["content"][JSONAPI_MEDIA_TYPE]["schema"]["$ref"]
    books_delete_ref = books_rel["delete"]["requestBody"]["content"][JSONAPI_MEDIA_TYPE]["schema"]["$ref"]
    assert author_patch_ref.endswith("/FastAuthorRelationshipDocumentToOne")
    assert author_post_ref.endswith("/FastAuthorRelationshipDocumentToOne")
    assert books_patch_ref.endswith("/FastBookRelationshipDocumentToMany")
    assert books_post_ref.endswith("/FastBookRelationshipDocumentToMany")
    assert books_delete_ref.endswith("/FastBookRelationshipDocumentToMany")


def test_fastapi_openapi_jsonapi_query_params_documented(fastapi_client: TestClient) -> None:
    response = fastapi_client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]

    collection_get = paths["/FastThings"]["get"]
    collection_params = _query_param_names(collection_get)
    assert {"include", "fields[FastThing]", "page[offset]", "page[limit]", "sort", "filter"} <= collection_params
    assert "filter[name]" in collection_params
    assert "filter[description]" in collection_params

    instance_get = paths["/FastThings/{object_id}"]["get"]
    instance_params = _query_param_names(instance_get)
    assert {"include", "fields[FastThing]"} <= instance_params

    rel_get = paths["/FastAuthors/{object_id}/books"]["get"]
    rel_params = _query_param_names(rel_get)
    assert {"include", "fields[FastBook]", "page[offset]", "page[limit]", "sort", "filter"} <= rel_params
    assert "filter[title]" in rel_params

    post_collection = paths["/FastThings"]["post"]
    post_params = _query_param_names(post_collection)
    assert {"include", "fields[FastThing]"} <= post_params


def test_fastapi_openapi_rpc_query_params_and_tags_documented(fastapi_client: TestClient) -> None:
    response = fastapi_client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    paths = spec["paths"]

    class_rpc_post = paths["/FastAuthors/lookup_by_name"]["post"]
    class_rpc_params = _query_param_names(class_rpc_post)
    assert {"include", "fields[FastAuthor]", "page[offset]", "page[limit]"} <= class_rpc_params

    tags = {str(tag.get("name")): str(tag.get("description", "")) for tag in spec.get("tags", [])}
    assert "FastAuthors" in tags
    assert tags["FastAuthors"]


def test_fastapi_returns_jsonapi_error_document(fastapi_client: TestClient) -> None:
    response = fastapi_client.get("/FastBooks?include=invalid_rel")
    assert response.status_code == 400
    payload = response.json()
    assert "errors" in payload
    assert "detail" not in payload
    assert payload["errors"][0]["status"] == "400"


def test_fastapi_sparse_fields_collection_and_instance(fastapi_client: TestClient) -> None:
    base = fastapi_client.get("/FastThings").json()["data"]
    model_type = base[0]["type"]

    collection = fastapi_client.get(f"/FastThings?fields[{model_type}]=name")
    assert collection.status_code == 200
    for row in collection.json()["data"]:
        assert "name" in row["attributes"]
        assert "description" not in row["attributes"]

    instance = fastapi_client.get(f"/FastThings/1?fields[{model_type}]=description")
    assert instance.status_code == 200
    attrs = instance.json()["data"]["attributes"]
    assert "description" in attrs
    assert "name" not in attrs


def test_fastapi_include_and_relationship_sort_pagination(fastapi_client: TestClient) -> None:
    collection = fastapi_client.get("/FastBooks?include=author")
    assert collection.status_code == 200
    payload = collection.json()
    assert "included" in payload
    assert any(item["type"] == "FastAuthor" for item in payload["included"])

    rel = fastapi_client.get("/FastAuthors/1/books?sort=-title&page[limit]=2")
    assert rel.status_code == 200
    rel_data = rel.json()["data"]
    assert [row["attributes"]["title"] for row in rel_data] == ["book-3", "book-2"]


def test_fastapi_collection_sort_pagination_and_filter_bracket(fastapi_client: TestClient) -> None:
    sorted_page = fastapi_client.get("/FastThings?sort=-name&page[limit]=1")
    assert sorted_page.status_code == 200
    assert sorted_page.json()["data"][0]["attributes"]["name"] == "beta"

    sorted_page_2 = fastapi_client.get("/FastThings?sort=-name&page[offset]=1&page[limit]=1")
    assert sorted_page_2.status_code == 200
    assert sorted_page_2.json()["data"][0]["attributes"]["name"] == "alpha"

    invalid_filter = fastapi_client.get("/FastThings?filter[invalid]=1")
    assert invalid_filter.status_code == 200
    assert invalid_filter.json()["data"] == []


def test_fastapi_validation_errors_for_post_and_patch(fastapi_client: TestClient) -> None:
    invalid_post = fastapi_client.post(
        "/FastThings",
        json={"data": {"type": "WrongType", "attributes": {"name": "x"}}},
    )
    assert invalid_post.status_code == 400
    assert "errors" in invalid_post.json()
    assert "detail" not in invalid_post.json()

    invalid_patch = fastapi_client.patch(
        "/FastThings/1",
        json={"data": {"id": "2", "type": "FastThing", "attributes": {"name": "x"}}},
    )
    assert invalid_patch.status_code == 400
    assert invalid_patch.json()["errors"][0]["detail"] == "Body id does not match path id"


def test_fastapi_request_validation_error_returns_jsonapi_error_document(fastapi_client: TestClient) -> None:
    invalid_body = fastapi_client.post("/FastThings", json=["not-a-jsonapi-object"])
    assert invalid_body.status_code == 422
    assert JSONAPI_MEDIA_TYPE in invalid_body.headers.get("content-type", "")
    payload = invalid_body.json()
    assert "errors" in payload
    assert "detail" not in payload
    assert payload["errors"][0]["status"] == "422"


def test_fastapi_validation_error_pointer_and_parameter_mapping() -> None:
    class _Attrs(BaseModel):
        name: int

    class _Data(BaseModel):
        attributes: _Attrs

    class _Payload(BaseModel):
        data: _Data

    app = FastAPI()
    install_jsonapi_exception_handlers(app)

    @app.post("/typed")
    def typed(payload: _Payload) -> dict[str, bool]:
        return {"ok": bool(payload.data.attributes.name)}

    @app.get("/typed-query")
    def typed_query(limit: int) -> dict[str, bool]:
        return {"ok": bool(limit)}

    with TestClient(app) as client:
        invalid_payload = client.post("/typed", json={"data": {"attributes": {"name": "x"}}})
        assert invalid_payload.status_code == 422
        payload_errors = invalid_payload.json()["errors"]
        assert payload_errors[0]["source"]["pointer"] == "/data/attributes/name"

        invalid_query = client.get("/typed-query?limit=nope")
        assert invalid_query.status_code == 422
        query_errors = invalid_query.json()["errors"]
        assert query_errors[0]["source"]["parameter"] == "limit"


def test_fastapi_patch_supports_sparse_fields_and_include(fastapi_client: TestClient) -> None:
    response = fastapi_client.patch(
        "/FastBooks/1?include=author&fields[FastBook]=title",
        json={"data": {"id": "1", "type": "FastBook", "attributes": {"title": "patched-title"}}},
    )
    assert response.status_code == 200
    body = response.json()
    attrs = body["data"]["attributes"]
    assert attrs["title"] == "patched-title"
    assert "author_id" not in attrs
    assert "included" in body
    assert any(item["type"] == "FastAuthor" for item in body["included"])


def test_fastapi_expose_object_dependencies_enforced() -> None:
    original_db = safrs.DB
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))
    safrs.DB = _SAFRSDBWrapper(Session, Base)
    Base.metadata.create_all(engine)

    try:
        Session.add(FastThing(name="auth-required", description="x"))
        Session.commit()

        app = FastAPI()

        def require_auth(request: Request) -> None:
            if request.headers.get("x-test-auth") != "ok":
                raise HTTPException(status_code=401, detail="Unauthorized")

        api = SafrsFastAPI(app)
        api.expose_object(FastThing, dependencies=[require_auth])

        with TestClient(app) as client:
            unauthorized = client.get("/FastThings")
            assert unauthorized.status_code == 401
            authorized = client.get("/FastThings", headers={"x-test-auth": "ok"})
            assert authorized.status_code == 200
    finally:
        Session.remove()
        Base.metadata.drop_all(engine)
        safrs.DB = original_db


def test_fastapi_delete_toone_relationship_is_idempotent(fastapi_client: TestClient) -> None:
    current_author = fastapi_client.get("/FastBooks/1/author")
    assert current_author.status_code == 200
    data = current_author.json()["data"]

    delete_payload = {"data": {"type": data["type"], "id": data["id"]}}
    delete_one = fastapi_client.request("DELETE", "/FastBooks/1/author", json=delete_payload)
    assert delete_one.status_code == 204

    after_delete = fastapi_client.get("/FastBooks/1/author")
    assert after_delete.status_code == 404

    delete_payload_list = {"data": [delete_payload["data"]]}
    delete_two = fastapi_client.request("DELETE", "/FastBooks/1/author", json=delete_payload_list)
    assert delete_two.status_code == 204


def test_fastapi_post_with_relationship_payload_returns_included(fastapi_client: TestClient) -> None:
    payload = {
        "data": {
            "type": "FastBook",
            "attributes": {"title": "book-from-rel-post"},
                "relationships": {
                    "author": {
                        "data": {
                            "type": "FastAuthor",
                            "id": 999,
                            "attributes": {"name": "author-from-rel-post"},
                        }
                    }
                },
        }
    }

    response = fastapi_client.post("/FastBooks", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["data"]["attributes"]["title"] == "book-from-rel-post"
    assert "included" in body
    assert any(item["type"] == "FastAuthor" for item in body["included"])


def test_fastapi_rpc_routes_instance_class_and_duplicate(fastapi_client: TestClient) -> None:
    instance_rpc = fastapi_client.post("/FastThings/1/prefix_name", json={"meta": {"args": {"prefix": "X-"}}})
    assert instance_rpc.status_code == 200
    assert instance_rpc.json()["meta"]["value"] == "X-alpha"

    class_rpc = fastapi_client.post("/FastAuthors/lookup_by_name", json={"meta": {"args": {"name": "author-1"}}})
    assert class_rpc.status_code == 200
    assert class_rpc.json()["meta"]["count"] >= 1

    duplicate_rpc = fastapi_client.post("/FastAuthors/1/duplicate", json={})
    assert duplicate_rpc.status_code == 200
    payload = duplicate_rpc.json()
    assert payload["data"]["type"] == "FastAuthor"
    assert "id" in payload["data"]


def test_fastapi_internal_helper_branches(monkeypatch: pytest.MonkeyPatch, fastapi_client: TestClient) -> None:
    api = fastapi_client.app.state.safrs_api

    app = FastAPI()

    @app.get("/swagger.json", include_in_schema=False)
    def swagger() -> dict[str, str]:
        return {"ok": "yes"}

    SafrsFastAPI(app)
    swagger_routes = [route for route in app.routes if getattr(route, "path", None) == "/swagger.json"]
    assert len(swagger_routes) == 1

    assert api._with_slash_parity("/abc/") == ["/abc", "/abc/"]

    dep = Depends(lambda: None)
    deps = api._normalize_dependencies([dep, lambda: None])
    assert deps[0] is dep
    with pytest.raises(TypeError):
        api._normalize_dependencies([1])

    class NoMapper:
        pass

    assert api._resolve_relationships(NoMapper) == {}
    class HasFilteredRelationships:
        _s_relationships = {"books": object()}

    assert api._resolve_relationships(HasFilteredRelationships) == HasFilteredRelationships._s_relationships
    assert api._parse_include_paths(FastThing, _request("include=,")) == []
    assert ["books"] in api._parse_include_paths(FastAuthor, _request("include=%2Ball"))
    with pytest.raises(JSONAPIHTTPError):
        api._parse_include_paths(FastBook, _request("include=unknown_rel"))

    class QueryLike:
        def all(self) -> list[int]:
            return [1, 2]

    assert api._iter_related_items(None) == []
    assert api._iter_related_items(QueryLike()) == [1, 2]
    assert api._coerce_items(None) == []
    assert api._coerce_items(7) == [7]

    class BadSortItem:
        key = {}

    items = [BadSortItem(), BadSortItem()]
    assert api._apply_sort(items, _request("")) == items
    assert api._apply_sort(items, _request("sort=key")) == items

    assert api._parse_page_param("oops", 3) == 3

    class QueryPager:
        def __init__(self) -> None:
            self.offset_seen = None
            self.limit_seen = None

        def all(self) -> list[int]:
            return [1, 2, 3]

        def offset(self, value: int) -> "QueryPager":
            self.offset_seen = value
            return self

        def limit(self, value: int) -> dict[str, int]:
            self.limit_seen = value
            return {"limit": value}

    monkeypatch.setattr(safrs.SAFRS, "MAX_PAGE_LIMIT", 2)
    qp = QueryPager()
    assert api._apply_pagination(qp, _request("page[offset]=-1&page[limit]=999")) == {"limit": 2}
    assert qp.offset_seen == 0
    assert qp.limit_seen == 2
    assert api._apply_pagination([1, 2, 3], _request("page[limit]=-1")) == [1, 2]

    class QueryOrder(QueryPager):
        def order_by(self, _expr: Any) -> "QueryOrder":
            return self

    class BadSortModel:
        bad = object()

    q = QueryOrder()
    assert api._apply_sort_query_or_items(FastThing, q, _request("sort=missing")) is q
    assert api._apply_sort_query_or_items(BadSortModel, q, _request("sort=bad")) is q


def test_fastapi_schema_registry_respects_relationship_toggle() -> None:
    from safrs.fastapi.schemas.registry import SchemaRegistry

    registry = SchemaRegistry(document_relationships=False)
    resource_model = registry.resource(FastBook)
    schema = resource_model.model_json_schema()
    assert "relationships" not in schema["properties"]


def test_fastapi_internal_error_and_lookup_paths(fastapi_client: TestClient) -> None:
    api = fastapi_client.app.state.safrs_api

    with pytest.raises(JSONAPIHTTPError):
        api._handle_safrs_exception(JSONAPIHTTPError(400, {"errors": []}))

    class CustomJsonapiError(JsonapiError):
        status_code = 409
        message = "conflict"

    with pytest.raises(JSONAPIHTTPError) as jsonapi_exc:
        api._handle_safrs_exception(CustomJsonapiError())
    assert jsonapi_exc.value.status_code == 409

    with pytest.raises(JSONAPIHTTPError) as validation_exc:
        api._handle_safrs_exception(ValidationError("bad payload"))
    assert validation_exc.value.status_code == 400

    with pytest.raises(JSONAPIHTTPError) as system_exc:
        api._handle_safrs_exception(SystemValidationError("server side validation"))
    assert system_exc.value.status_code == 400

    with pytest.raises(RuntimeError):
        api._handle_safrs_exception(RuntimeError("boom"))

    class ModelValidation:
        @staticmethod
        def filter(_raw: str) -> Any:
            raise ValidationError("invalid")

    with pytest.raises(JSONAPIHTTPError):
        api._apply_filter(ModelValidation, _request("filter=x"), [])

    class ModelJsonapi:
        @staticmethod
        def filter(_raw: str) -> Any:
            raise CustomJsonapiError()

    with pytest.raises(JSONAPIHTTPError):
        api._apply_filter(ModelJsonapi, _request("filter=x"), [])

    class ModelRuntime:
        @staticmethod
        def filter(_raw: str) -> Any:
            raise RuntimeError("broken")

    with pytest.raises(RuntimeError):
        api._apply_filter(ModelRuntime, _request("filter=x"), [])

    class ModelSFilter:
        @staticmethod
        def _s_filter(_raw: str) -> list[str]:
            return ["ok"]

    assert api._apply_filter(ModelSFilter, _request("filter=x"), []) == ["ok"]

    class Target:
        _s_type = "Target"

        @staticmethod
        def get_instance(_value: Any) -> Any:
            return SimpleNamespace(jsonapi_id="7")

    with pytest.raises(JSONAPIHTTPError):
        api._lookup_related_instance(Target, "not-a-dict")
    with pytest.raises(JSONAPIHTTPError):
        api._lookup_related_instance(Target, {}, strict=True)
    with pytest.raises(JSONAPIHTTPError):
        api._lookup_related_instance(Target, {}, strict=False)
    with pytest.raises(JSONAPIHTTPError):
        api._lookup_related_instance(Target, {"id": "1", "type": "Wrong"})

    class TargetRaising(Target):
        @staticmethod
        def get_instance(_value: Any) -> Any:
            raise RuntimeError("not found")

    with pytest.raises(JSONAPIHTTPError):
        api._lookup_related_instance(TargetRaising, {"id": "1", "type": "Target"})

    class TargetNone(Target):
        @staticmethod
        def get_instance(_value: Any) -> Any:
            return None

    with pytest.raises(JSONAPIHTTPError):
        api._lookup_related_instance(TargetNone, {"id": "1", "type": "Target"})

    resolved = api._lookup_related_instance(Target, {"id": "1", "type": "Target"})
    assert resolved.jsonapi_id == "7"

    class RaisingRemove:
        def remove(self, _item: Any) -> None:
            raise RuntimeError("ignore")

    api._clear_relationship(RaisingRemove())

    with pytest.raises(JSONAPIHTTPError):
        api._append_relationship_item(object(), object())
    with pytest.raises(JSONAPIHTTPError):
        api._remove_relationship_item(object(), object())

    api._collect_included(FastThing, SimpleNamespace(), [[], ["missing"]], {}, set(), [])
    api._collect_included(FastAuthor, SimpleNamespace(books=[None]), [["books"]], {}, set(), [])

    class EncObj:
        jsonapi_id = 1
        description = "ok"

        @property
        def name(self) -> Any:
            raise RuntimeError("missing")

    encoded = api._encode_resource(FastThing, EncObj())
    assert encoded["attributes"]["name"] is None


def test_fastapi_relationship_handler_branch_errors(fastapi_client: TestClient) -> None:
    api = fastapi_client.app.state.safrs_api
    req = _request("")

    with pytest.raises(JSONAPIHTTPError):
        api._get_relationship(FastBook, "invalid")(1, req)
    with pytest.raises(JSONAPIHTTPError):
        api._get_relationship_item(FastAuthor, "books")(1, "9999", req)
    with pytest.raises(JSONAPIHTTPError):
        api._patch_relationship(FastBook, "author")(1, {"data": "bad"})
    with pytest.raises(JSONAPIHTTPError):
        api._post_relationship(FastAuthor, "books")(1, {"data": "bad"})
    with pytest.raises(JSONAPIHTTPError):
        api._delete_relationship(FastAuthor, "books")(1, {"data": "bad"})
    with pytest.raises(JSONAPIHTTPError):
        api._delete_relationship(FastBook, "author")(1, {"data": [1]})


def test_fastapi_rpc_and_encoding_internal_branches(fastapi_client: TestClient) -> None:
    api = fastapi_client.app.state.safrs_api

    class _RpcDiscoveryModel:
        @classmethod
        def _s_get_jsonapi_rpc_methods(cls) -> list[Any]:
            return [cls.class_method, cls.class_method, cls.static_method]

        @classmethod
        def class_method(cls) -> None:
            return None

        @staticmethod
        def static_method() -> None:
            return None

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("safrs.fastapi.api.get_http_methods", lambda _method: ["get"])
    try:
        discovered = api._discover_rpc_methods(_RpcDiscoveryModel)
    finally:
        monkeypatch.undo()
    assert discovered == [
        ("class_method", True, ["GET"]),
        ("static_method", True, ["GET"]),
    ]

    parsed_args = api._parse_rpc_args(_request("x=query&y=2"), {"meta": {"args": {"x": "meta"}}})
    assert parsed_args["x"] == "meta"
    assert parsed_args["y"] == "2"

    assert api._encode_rpc_value(None) is None
    assert api._encode_rpc_value({"type": "FastThing", "id": "1"}) == {"type": "FastThing", "id": "1"}
    assert api._encode_rpc_value({"outer": {"inner": 1}}) == {"outer": {"inner": 1}}
    assert api._encode_rpc_value([1, 2]) == [1, 2]
    assert api._encode_rpc_value(123) == 123

    link_payload = {"data": {"type": "FastThing", "id": "1"}, "links": {"self": "/x"}}
    norm = api._normalize_rpc_result(FastThing, link_payload)
    assert norm["links"]["self"] == "/x"

    assert api._normalize_rpc_result(FastThing, {"raw": 1})["meta"]["result"] == {"raw": 1}
    thing_obj = safrs.DB.session.query(FastThing).first()
    encoded_obj = api._normalize_rpc_result(FastThing, thing_obj)
    assert encoded_obj["data"]["type"] == "FastThing"
    encoded_list = api._normalize_rpc_result(FastThing, [thing_obj])
    assert isinstance(encoded_list["data"], list)
    assert api._normalize_rpc_result(FastThing, None)["meta"] == {}
    assert api._normalize_rpc_result(FastThing, 7)["meta"]["result"] == 7


def test_fastapi_rpc_handler_exception_branches(fastapi_client: TestClient) -> None:
    api = fastapi_client.app.state.safrs_api

    class ClassRPCModel:
        @classmethod
        def raise_jsonapi(cls, **_kwargs: Any) -> Any:
            raise JSONAPIHTTPError(409, {"errors": []})

        @classmethod
        def raise_runtime(cls, **_kwargs: Any) -> Any:
            raise RuntimeError("class rpc boom")

    class InstanceRPCModel:
        @staticmethod
        def get_instance(_object_id: str) -> Any:
            class Instance:
                @staticmethod
                def raise_jsonapi(**_kwargs: Any) -> Any:
                    raise JSONAPIHTTPError(410, {"errors": []})

                @staticmethod
                def raise_runtime(**_kwargs: Any) -> Any:
                    raise RuntimeError("instance rpc boom")

            return Instance()

    class_handler_jsonapi = api._rpc_handler(ClassRPCModel, "raise_jsonapi", True)
    with pytest.raises(JSONAPIHTTPError):
        class_handler_jsonapi(_request(""), None)

    class_handler_runtime = api._rpc_handler(ClassRPCModel, "raise_runtime", True)
    with pytest.raises(RuntimeError):
        class_handler_runtime(_request(""), None)

    instance_handler_jsonapi = api._rpc_handler(InstanceRPCModel, "raise_jsonapi", False)
    with pytest.raises(JSONAPIHTTPError):
        instance_handler_jsonapi("1", _request(""), None)

    instance_handler_runtime = api._rpc_handler(InstanceRPCModel, "raise_runtime", False)
    with pytest.raises(RuntimeError):
        instance_handler_runtime("1", _request(""), None)


def test_fastapi_internal_parse_and_instance_error_branches(monkeypatch: pytest.MonkeyPatch, fastapi_client: TestClient) -> None:
    api = fastapi_client.app.state.safrs_api

    with pytest.raises(JSONAPIHTTPError):
        api._require_type(FastThing, {"data": "not-a-dict"})  # type: ignore[arg-type]

    class AttrModel:
        _s_type = "AttrModel"
        _s_jsonapi_attrs = {"known": SimpleNamespace(type=object())}

    monkeypatch.setattr("safrs.fastapi.api.parse_attr", lambda *_a, **_k: (_ for _ in ()).throw(TypeError("boom")))
    parsed = api._parse_attributes_for_model(AttrModel, {"known": "x", "unknown": "y"})
    assert parsed["known"] == "x"
    assert "unknown" not in parsed

    sparse = api._parse_sparse_fields(FastThing, _request("fields[FastThing]=name,description"))
    assert sparse == {"name", "description"}

    include_paths = api._parse_include_paths(FastAuthor, _request("include=.,books"))
    assert include_paths == [["books"]]

    author = safrs.DB.session.query(FastAuthor).filter_by(name="author-1").one()
    included: list[dict[str, Any]] = []
    api._collect_included(FastAuthor, author, [["books", "author"]], {}, set(), included)
    assert any(item["type"] == "FastBook" for item in included)
    assert any(item["type"] == "FastAuthor" for item in included)

    inst = _json_payload(api._get_instance(FastAuthor)(str(author.id), _request("include=books")))
    assert "included" in inst

    class BrokenModel:
        _s_type = "Broken"

        @staticmethod
        def get_instance(_object_id: str) -> Any:
            raise RuntimeError("broken get_instance")

    with pytest.raises(RuntimeError):
        api._get_instance(BrokenModel)("1", _request(""))


def test_fastapi_post_patch_delete_and_relationship_success_branches(fastapi_client: TestClient) -> None:
    api = fastapi_client.app.state.safrs_api

    author1 = safrs.DB.session.query(FastAuthor).filter_by(name="author-1").one()
    author2 = safrs.DB.session.query(FastAuthor).filter_by(name="author-2").one()
    book_other = safrs.DB.session.query(FastBook).filter_by(author_id=author2.id).one()
    book_one = safrs.DB.session.query(FastBook).filter_by(author_id=author1.id).first()

    class PostDummyModel:
        _s_type = "PostDummyModel"
        _s_jsonapi_attrs = {"name": object()}

        @classmethod
        def _s_post(cls, **_kwargs: Any) -> Any:
            return SimpleNamespace(jsonapi_id="1", name="x", included_list=[None, "", "books", "books"])

    post_result = api._post_collection(PostDummyModel)(
        _request(""),
        {"data": {"type": "PostDummyModel", "attributes": {"name": "x"}}},
    )
    assert post_result.status_code == 201

    class BrokenPostModel(PostDummyModel):
        @classmethod
        def _s_post(cls, **_kwargs: Any) -> Any:
            raise RuntimeError("post boom")

    with pytest.raises(RuntimeError):
        api._post_collection(BrokenPostModel)(
            _request(""),
            {"data": {"type": "PostDummyModel", "attributes": {"name": "x"}}},
        )

    class BrokenPatchModel:
        _s_type = "BrokenPatchModel"
        _s_jsonapi_attrs = {"name": object()}

        @staticmethod
        def get_instance(_object_id: str) -> Any:
            raise RuntimeError("patch boom")

    with pytest.raises(RuntimeError):
        api._patch_instance(BrokenPatchModel)(
            "1",
            _request(""),
            {"data": {"type": "BrokenPatchModel", "attributes": {"name": "x"}}},
        )

    class DeleteOKModel:
        @staticmethod
        def get_instance(_object_id: str) -> Any:
            return SimpleNamespace(_s_delete=lambda: None)

    delete_ok = api._delete_instance(DeleteOKModel)("1")
    assert delete_ok.status_code == 204

    class DeleteBrokenModel:
        @staticmethod
        def get_instance(_object_id: str) -> Any:
            raise RuntimeError("delete boom")

    with pytest.raises(RuntimeError):
        api._delete_instance(DeleteBrokenModel)("1")

    class DeleteJSONAPIModel:
        @staticmethod
        def get_instance(_object_id: str) -> Any:
            raise JSONAPIHTTPError(418, {"errors": []})

    with pytest.raises(JSONAPIHTTPError):
        api._delete_instance(DeleteJSONAPIModel)("1")

    rel_item = _json_payload(api._get_relationship_item(FastAuthor, "books")(str(author1.id), str(book_one.id), _request("")))
    assert rel_item["data"]["id"] == str(book_one.id)

    with pytest.raises(JSONAPIHTTPError):
        api._get_relationship_item(FastBook, "unknown_rel")("1", "1", _request(""))

    patched_many = _json_payload(api._patch_relationship(FastAuthor, "books")(
        str(author1.id),
        {"data": [{"type": "FastBook", "id": str(book_other.id)}]},
    ))
    assert patched_many["meta"]["count"] == 1

    patched_toone_none = api._patch_relationship(FastBook, "author")(str(book_other.id), {"data": None})
    assert patched_toone_none.status_code == 204
    patched_toone_set = api._patch_relationship(FastBook, "author")(
        str(book_other.id),
        {"data": {"type": "FastAuthor", "id": str(author2.id)}},
    )
    assert patched_toone_set.status_code == 204

    with pytest.raises(JSONAPIHTTPError):
        api._patch_relationship(FastBook, "unknown_rel")("1", {"data": None})
    with pytest.raises(JSONAPIHTTPError):
        api._patch_relationship(FastAuthor, "books")(str(author1.id), {"data": {"id": str(book_other.id)}})

    posted_many = api._post_relationship(FastAuthor, "books")(
        str(author1.id),
        {"data": [{"type": "FastBook", "id": str(book_other.id)}]},
    )
    assert posted_many.status_code == 204
    posted_toone = _json_payload(api._post_relationship(FastBook, "author")(
        str(book_other.id),
        {"data": {"type": "FastAuthor", "id": str(author1.id)}},
    ))
    assert posted_toone["data"]["type"] == "FastAuthor"

    with pytest.raises(JSONAPIHTTPError):
        api._post_relationship(FastBook, "unknown_rel")("1", {"data": {}})
    with pytest.raises(JSONAPIHTTPError):
        api._post_relationship(FastBook, "author")(str(book_other.id), {"data": []})

    deleted_many = api._delete_relationship(FastAuthor, "books")(
        str(author1.id),
        {"data": [{"type": "FastBook", "id": str(book_other.id)}]},
    )
    assert deleted_many.status_code == 204

    with pytest.raises(JSONAPIHTTPError):
        api._delete_relationship(FastBook, "unknown_rel")("1", {"data": {}})
    with pytest.raises(JSONAPIHTTPError):
        api._delete_relationship(FastBook, "author")(str(book_other.id), {"data": "bad"})
