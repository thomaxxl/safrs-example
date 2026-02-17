import datetime
import pytest
from sqlalchemy import event

from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
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
    # Outer transaction (rolled back at end of test)
    transaction = connection.begin()

    # Session bound to the connection
    session_factory = sessionmaker(bind=connection)
    session = scoped_session(session_factory)
    db.session = session

    # Start a SAVEPOINT so application commit/rollback doesn't end the outer transaction
    session().begin_nested()

    @event.listens_for(session(), "after_transaction_end")
    def _restart_savepoint(sess, trans):
        # Restart the SAVEPOINT after commit/rollback of the nested transaction
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    yield session

    session.remove()
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

    app.test_client_class = SafrsClient
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
