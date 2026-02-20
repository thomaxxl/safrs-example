import os
from urllib.parse import parse_qsl
import datetime
import pytest

from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from app import create_app, create_api, create_fastapi_api
from app.base_model import db
from tests.helpers.db import clean_database, create_database
from tests.factories import (
    BookFactory,
    PersonFactory,
    PublisherFactory,
    ThingFactory,
    SubThingFactory,
)

from flask.testing import FlaskClient
from werkzeug.datastructures import Headers


class SafrsClient(FlaskClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def open(self, *args, **kwargs):
        custom_headers = Headers({
            'Content-Type': 'application/vnd.api+json; ext=bulk'
        })
        headers = kwargs.pop('headers', Headers())
        headers.extend(custom_headers)
        kwargs['headers'] = headers
        return super().open(*args, **kwargs)


class RespWrap:
    def __init__(self, response):
        self._response = response
        self.status_code = response.status_code
        self.headers = response.headers
        self.data = response.content

    def get_json(self):
        return self._response.json()

    @property
    def json(self):
        return self._response.json()


class FastAPICompatClient:
    def __init__(self, client):
        self._client = client

    @staticmethod
    def _merge_headers(headers):
        merged = {"Content-Type": "application/vnd.api+json; ext=bulk"}
        if headers:
            merged.update(dict(headers))
        return merged

    @staticmethod
    def _normalize_query(query_string):
        if query_string is None:
            return None
        if isinstance(query_string, str):
            return parse_qsl(query_string, keep_blank_values=True)
        return query_string

    def open(self, path, method="GET", query_string=None, headers=None, **kwargs):
        response = self._client.request(
            method.upper(),
            path,
            params=self._normalize_query(query_string),
            headers=self._merge_headers(headers),
            **kwargs,
        )
        return RespWrap(response)

    def get(self, path, **kwargs):
        return self.open(path, method="GET", **kwargs)

    def post(self, path, **kwargs):
        return self.open(path, method="POST", **kwargs)

    def patch(self, path, **kwargs):
        return self.open(path, method="PATCH", **kwargs)

    def delete(self, path, **kwargs):
        return self.open(path, method="DELETE", **kwargs)

    def request(self, method, path, **kwargs):
        return self.open(path, method=method, **kwargs)


def _selected_backend():
    return os.getenv("SAFRS_BACKEND", "flask").strip().lower()


@pytest.fixture(scope="session")
def app():
    """Setup our flask test app and provide an app context"""
    _app = create_app()
    #_app.test_client_class = SafrsClient
    with _app.app_context():
        yield _app


@pytest.fixture(scope="session")
def database(app):
    """Session-wide test database."""
    clean_database(app.config["DB_NAME"])
    create_database(app.config["DB_NAME"])
    db.create_all()

_connection_fixture_connection = None
@pytest.fixture(scope="session")
def connection(database):
    # Create a connection
    global _connection_fixture_connection
    connection = db.engine.connect()
    _connection_fixture_connection = connection
    yield connection
    connection.close()


@pytest.fixture(autouse=True)
def db_session(connection,scope="session"):
    original_session = db.session
    backend = _selected_backend()

    # Outer transaction (rolled back at end of test)
    transaction = connection.begin()

    # IMPORTANT:
    # SAFRS commits on success and rollbacks on any exception (incl. ValidationError).
    # In tests we keep one outer transaction per test; SAFRS must not be able to
    # commit/rollback that outer transaction or it will wipe fixtures and deassociate
    # the connection transaction.
    #
    # join_transaction_mode="create_savepoint" makes Session commit/rollback use
    # SAVEPOINTs instead of the outer transaction.
    session_factory = sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    if backend == "fastapi":
        # FastAPI's TestClient serves requests from a different thread than pytest.
        # Use a fixed scope key so request handling and test code share one session
        # and one nested transaction stack.
        session = scoped_session(session_factory, scopefunc=lambda: 1)
        session.info["_safrs_skip_cleanup"] = True
    else:
        session = scoped_session(session_factory)
    db.session = session

    try:
        yield session
    finally:
        if backend == "fastapi":
            session.info.pop("_safrs_skip_cleanup", None)
        session.remove()
        db.session = original_session
        transaction.rollback()


@pytest.fixture(scope="session", autouse=True)
def api(app, database):
    """Init SAFRS"""
    create_api(app)

    backend = _selected_backend()
    if backend == "fastapi":
        pytest.importorskip("fastapi")
        from safrs.safrs_api import SAFRSJSONEncoder

        app.json_encoder = SAFRSJSONEncoder  # type: ignore[attr-defined]
    return None


@pytest.fixture(scope="session")
def client(app, api):
    """Setup an flask app client, yields an flask app client"""
    backend = _selected_backend()
    if backend == "fastapi":
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient

        fastapi_app = create_fastapi_api(seed_data=False)
        with TestClient(fastapi_app, raise_server_exceptions=False) as c:
            yield FastAPICompatClient(c)
        return

    app.test_client_class = SafrsClient
    with app.test_client() as c:
        yield c


@pytest.fixture(scope="session", autouse=True)
def flask_request_context(app, api):
    if _selected_backend() != "fastapi":
        yield
        return

    ctx = app.test_request_context("/")
    ctx.push()
    try:
        yield
    finally:
        ctx.pop()


@pytest.fixture(scope="function")
def mock_subthing(db_session):
    subthing = SubThingFactory.create(name="mock_subthing")

    yield subthing


@pytest.fixture(scope="function")
def mock_thing(db_session):
    thing = ThingFactory.create(name="mock_thing", created=str(datetime.datetime.now()), description="mock_description")

    yield thing


@pytest.fixture(scope="function")
def mock_publisher_with_3_books(db_session):
    publisher = PublisherFactory.create(name="mock_publisher_with_3_books")

    book1 = BookFactory(publisher=publisher)
    book2 = BookFactory(publisher=publisher)
    book3 = BookFactory(publisher=publisher)

    yield publisher

@pytest.fixture(scope="function")
def mock_publisher_lazy_with_3_books(db_session):
    publisher = PublisherFactory.create(name="mock_publisher_lazy_with_3_books")

    book1 = BookFactory(publisher=publisher)
    book2 = BookFactory(publisher=publisher)
    book3 = BookFactory(publisher=publisher)

    yield publisher


@pytest.fixture(scope="function")
def mock_person_with_3_books_read(db_session):
    person = PersonFactory.create(name="mock_pers_with_3_books_read")

    book1 = BookFactory(reader_id=person.id)
    book2 = BookFactory(reader_id=person.id)
    book3 = BookFactory(reader_id=person.id)

    yield person
