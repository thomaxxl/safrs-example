import datetime
import pytest

from app import create_app, create_api
from app.base_model import db
from tests.helpers.db import clean_database, create_database
from tests.factories import ThingFactory, SubThingFactory


@pytest.fixture(scope="session")
def app():
    """Setup our flask test app and provide an app context"""
    _app = create_app()
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
    with app.test_client() as c:
        yield c


@pytest.fixture(scope='function')
def mock_subthing(db_session):
    subthing = SubThingFactory.create(name="mock_name")

    yield subthing


@pytest.fixture(scope='function')
def mock_thing(db_session):
    thing = ThingFactory.create(name="mock_name", created=str(datetime.datetime.now()), description="mock_description")

    yield thing
