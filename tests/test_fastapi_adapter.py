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
from safrs.fastapi.api import JSONAPIHTTPError, SafrsFastAPI


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


def test_fastapi_swagger_alias_and_slash_parity(fastapi_client: TestClient) -> None:
    response = fastapi_client.get("/swagger.json")
    assert response.status_code == 200
    assert "openapi" in response.json()

    no_slash = fastapi_client.get("/FastThings")
    assert no_slash.status_code == 200

    with_slash = fastapi_client.get("/FastThings/")
    assert with_slash.status_code == 200


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
