import datetime
from types import SimpleNamespace

import sqlalchemy

from safrs.attr_parse import parse_attr


class _TypeRaisesNotImplemented:
    @property
    def python_type(self):
        raise NotImplementedError("custom type python_type not implemented")


def test_parse_attr_uses_column_default_when_value_is_none():
    """
    Covers attr_parse.py:16-17
    """
    col = SimpleNamespace(
        default=SimpleNamespace(arg="DEFAULT_VALUE"),
        type=SimpleNamespace(python_type=str),
    )
    assert parse_attr(col, None) == "DEFAULT_VALUE"


def test_parse_attr_uses_column_python_type_and_returns_on_notimplemented():
    """
    Covers:
      - attr_parse.py:24 (column.python_type coercion)
      - attr_parse.py:28-37 (NotImplementedError -> log.debug -> return raw)
    """
    col = SimpleNamespace(
        default=None,
        python_type=int,  # custom deserializer at column level
        type=_TypeRaisesNotImplemented(),
    )
    assert parse_attr(col, "7") == 7


def test_parse_attr_skips_type_coercion_for_json_columns(monkeypatch):
    """
    Covers attr_parse.py:41 (JSON short-circuit)

    Some SQLAlchemy versions may have JSON.python_type behave differently;
    patch it to be safe so the code reaches the JSON branch instead of
    returning early from the NotImplementedError handler.
    """
    monkeypatch.setattr(
        sqlalchemy.sql.sqltypes.JSON,
        "python_type",
        property(lambda _self: object),
        raising=False,
    )
    col = SimpleNamespace(default=None, type=sqlalchemy.sql.sqltypes.JSON())
    payload = {"a": 1, "b": ["x", "y"]}
    assert parse_attr(col, payload) == payload


def test_parse_attr_parses_datetime_without_microseconds():
    """
    Covers attr_parse.py:55 (datetime.strptime without microseconds)
    """
    col = SimpleNamespace(default=None, type=SimpleNamespace(python_type=datetime.datetime))
    dt = parse_attr(col, "2025-01-02 03:04:05")
    assert dt == datetime.datetime(2025, 1, 2, 3, 4, 5)
