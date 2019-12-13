import datetime
import pytest

from app import create_app, create_api
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

class SafrsClient(FlaskClient):
    def __init__(self, authentication=None, *args, **kwargs):
        FlaskClient.__init__(*args, **kwargs)
        self.headers["Content-Type"] = "application/vnd.api+json; ext=bulk"
        self._authentication = authentication

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


@pytest.fixture(scope="session")
def connection(database):
    # Create a connection
    connection = db.engine.connect()
    yield connection
    connection.close()


@pytest.fixture(autouse=True)
def db_session(connection):
    # Start a transaction
    transaction = connection.begin()
    # Start a scoped session (i.e it'll be closed after current application context)
    session = db.create_scoped_session(options={"bind": connection, "binds": {}})

    # Put our session on the db object for the codebase to use
    db.session = session

    yield session

    # Rollback the whole transaction after each test
    transaction.rollback()


@pytest.fixture(scope="session")
def api(app, database):
    """Init SAFRS"""
    create_api(app)


@pytest.fixture(scope="session")
def client(app, api):
    """Setup an flask app client, yields an flask app client"""
    headers = {}
    headers["Content-Type"] = "application/vnd.api+json; ext=bulk"
    with app.test_client() as c:
        yield c


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
def mock_person_with_3_books_read(db_session):
    person = PersonFactory.create(name="mock_pers_with_3_books_read")

    book1 = BookFactory(reader_id=person.id)
    book2 = BookFactory(reader_id=person.id)
    book3 = BookFactory(reader_id=person.id)

    yield person
