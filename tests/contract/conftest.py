from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def app() -> None:
    return None


@pytest.fixture(scope="session")
def database(app: None) -> None:
    return None


@pytest.fixture(scope="session")
def connection(database: None) -> None:
    return None


@pytest.fixture(autouse=True)
def db_session() -> None:
    yield None


@pytest.fixture(scope="session", autouse=True)
def api(app: None, database: None) -> None:
    return None


@pytest.fixture(scope="session")
def client(app: None, api: None) -> None:
    return None


@pytest.fixture(scope="session", autouse=True)
def flask_request_context(app: None, api: None) -> None:
    yield None
