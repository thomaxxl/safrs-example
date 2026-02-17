from typing import Any, Generator

import pytest

import safrs
from safrs import SAFRSBase
from safrs.errors import SystemValidationError
from sqlalchemy import Column, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, relationship, scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

pytest.importorskip("fastapi")
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from safrs.fastapi.api import SafrsFastAPI


Base = declarative_base()


class _SAFRSDBWrapper:
    def __init__(self, session: Any, model: Any) -> None:
        self.session = session
        self.Model = model


class FastAuthor(SAFRSBase, Base):
    __tablename__ = "FastAuthors"

    id = Column(Integer, primary_key=True)
    name = Column(String)


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
    api.expose_object(FastThing)
    api.expose_object(FastAuthor)
    api.expose_object(FastBook)

    with TestClient(app) as client:
        yield client

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

    Session.remove()
    Base.metadata.drop_all(engine)
    safrs.DB = original_db


def test_fastapi_delete_toone_relationship_is_idempotent(fastapi_client: TestClient) -> None:
    current_author = fastapi_client.get("/FastBooks/1/author")
    assert current_author.status_code == 200
    data = current_author.json()["data"]

    delete_payload = {"data": {"type": data["type"], "id": data["id"]}}
    delete_one = fastapi_client.delete("/FastBooks/1/author", json=delete_payload)
    assert delete_one.status_code == 204

    after_delete = fastapi_client.get("/FastBooks/1/author")
    assert after_delete.status_code == 404

    delete_payload_list = {"data": [delete_payload["data"]]}
    delete_two = fastapi_client.delete("/FastBooks/1/author", json=delete_payload_list)
    assert delete_two.status_code == 204
