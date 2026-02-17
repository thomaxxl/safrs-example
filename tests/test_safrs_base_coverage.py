import json
from types import SimpleNamespace

from flask import g
import safrs
import safrs.base as safrs_base
from sqlalchemy.exc import InvalidRequestError

from app import models
from tests.factories import BookFactory, PersonFactory, PublisherFactory


def _clear_check_perm_cache() -> None:
    """
    SAFRSBase._s_check_perm class-expression is lru_cache'd.
    Clear it so branch tests aren't bypassed by cache hits.
    """
    try:
        safrs_base.SAFRSBase.__dict__["_s_check_perm"].expr.cache_clear()
    except Exception:
        pass


def _clear_jsonapi_attrs_cache(cls: type) -> None:
    """
    _s_jsonapi_attrs has both an lru_cache'd expression and per-class cache.
    Clear both to avoid cross-test leakage.
    """
    if hasattr(cls, "_cached_jsonapi_attrs"):
        delattr(cls, "_cached_jsonapi_attrs")
    try:
        safrs_base.SAFRSBase.__dict__["_s_jsonapi_attrs"].expr.cache_clear()
    except Exception:
        pass


def test_s_patch_skips_unauthorized_attr(monkeypatch, db_session):
    """
    Cover SAFRSBase._s_patch write-permission skip (base.py:482).
    Use Thing to avoid UserWithPerms request-context parsing issues.
    """
    monkeypatch.setattr(safrs.DB.session, "commit", lambda: None)

    thing = models.Thing(name="old", description="d")
    db_session.add(thing)
    db_session.flush()

    thing._s_check_perm = lambda *_a, **_k: False
    thing._s_patch(name="new")
    assert thing.name == "old"


def test_s_check_perm_branches():
    _clear_check_perm_cache()

    old_exclude_attrs = list(models.Person.exclude_attrs)
    models.Person.exclude_attrs = ["dummy_exclude"]
    assert models.Person._s_check_perm("dummy_exclude", "r") is False
    models.Person.exclude_attrs = old_exclude_attrs
    _clear_check_perm_cache()

    old_supports = getattr(models.Person, "supports_includes", True)
    models.Person.supports_includes = False
    assert models.Person._s_check_perm("name", "r") is True
    models.Person.supports_includes = old_supports
    _clear_check_perm_cache()

    old_excl_rels = list(getattr(models.Person, "exclude_rels", []))
    models.Person.exclude_rels = ["books_read"]
    assert models.Person._s_check_perm("books_read", "r") is False
    models.Person.exclude_rels = old_excl_rels
    _clear_check_perm_cache()

    rel = None
    for relationship in models.Person.__mapper__.relationships:
        if relationship.key == "books_read":
            rel = relationship
            break
    assert rel is not None
    old_rel_expose = getattr(rel, "expose", True)
    setattr(rel, "expose", False)
    assert models.Person._s_check_perm("books_read", "r") is False
    setattr(rel, "expose", old_rel_expose)
    _clear_check_perm_cache()


def test_instance_s_jsonapi_attrs_fallback_and_exceptions(app, monkeypatch):
    thing = models.Thing(name="n", description="X")

    def boom(*_a, **_k):
        raise TypeError("boom")

    with monkeypatch.context() as mp:
        mp.setattr(safrs_base.json, "dumps", boom)
        attrs = thing._s_jsonapi_attrs
        assert isinstance(attrs, dict)

    with monkeypatch.context() as mp:
        mp.setattr(safrs_base, "current_app", None)
        attrs = thing._s_jsonapi_attrs
        assert attrs.get("description") == "X"


def test_get_related_branches(app, api, db_session, monkeypatch):
    pub = PublisherFactory.create(name="cov_pub")
    BookFactory.create(publisher=pub)
    BookFactory.create(publisher=pub)
    db_session.flush()

    with app.test_request_context("/?include=books&exclude=books"):
        g.ja_included = set()
        g.ja_data = set()
        rels = pub._s_get_related()
        assert "books" in rels

    orig_get_config = safrs_base.get_config

    monkeypatch.setattr(
        safrs_base,
        "get_config",
        lambda key: False if key == "ENABLE_RELATIONSHIPS" else orig_get_config(key),
    )
    with app.test_request_context("/?include=books"):
        g.ja_included = set()
        g.ja_data = set()
        rels = pub._s_get_related()
        assert "warning" in rels["books"].get("meta", {})

    monkeypatch.setattr(
        safrs_base,
        "get_config",
        lambda key: 0 if key == "BIG_QUERY_THRESHOLD" else orig_get_config(key),
    )
    with app.test_request_context("/?include=books"):
        g.ja_included = set()
        g.ja_data = set()
        rels = pub._s_get_related()
        assert "warning" in rels["books"].get("meta", {})


def test_count_and_sample_id_and_sample_dict(monkeypatch):
    class BadCountQuery:
        def count(self):
            raise Exception("boom")

    monkeypatch.setattr(models.Person, "jsonapi_filter", classmethod(lambda cls: BadCountQuery()))
    assert models.Person._s_count() == -1

    class BadSample:
        @property
        def jsonapi_id(self):
            raise RuntimeError("boom")

    class SeqQuery:
        def __init__(self):
            self.calls = 0

        def first(self):
            self.calls += 1
            if self.calls == 1:
                return BadSample()
            return None

    monkeypatch.setattr(models.Thing, "query", SeqQuery(), raising=False)
    assert models.Thing._s_sample_id() == "jsonapi_id_string"

    class NoPythonType:
        @property
        def python_type(self):
            raise NotImplementedError("no type")

    _clear_jsonapi_attrs_cache(models.Thing)
    models.Thing._cached_jsonapi_attrs = {
        "with_sample": SimpleNamespace(name="with_sample", sample="sample_value", type=SimpleNamespace(python_type=str)),
        "callable_default": SimpleNamespace(
            name="callable_default",
            default=SimpleNamespace(arg=lambda: "x"),
            type=SimpleNamespace(python_type=str),
        ),
        "no_pytype": SimpleNamespace(name="no_pytype", type=NoPythonType()),
    }
    sample = models.Thing._s_sample_dict()
    assert sample["with_sample"] == "sample_value"
    assert sample["callable_default"] == ""
    assert sample["no_pytype"] is None
    _clear_jsonapi_attrs_cache(models.Thing)


def test_rpc_methods_s_url_type_setter_and_in_filter(monkeypatch, db_session):
    def boom_getmembers(*_a, **_k):
        raise InvalidRequestError("boom")

    monkeypatch.setattr(safrs_base.inspect, "getmembers", boom_getmembers)
    assert models.Thing._s_get_jsonapi_rpc_methods() == []

    thing = models.Thing(name="url-thing", description="d")
    db_session.add(thing)
    db_session.flush()

    def boom_url_for(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr(safrs_base, "url_for", boom_url_for)
    assert thing._s_url == ""

    twt = models.ThingWType()
    twt.Type = "new"
    assert twt.type == "new"

    PersonFactory.create(name="A", email="a@example.com")
    PersonFactory.create(name="B", email="b@example.com")

    flt = [
        42,
        {"name": "name", "op": "in", "val": ["A"]},
        {"name": "email", "op": "eq", "val": "a@example.com"},
    ]
    q = models.Person._s_filter(json.dumps(flt))
    res = q.all()
    assert any(p.email == "a@example.com" for p in res)


def test_class_jsonapi_attrs_type_branch(monkeypatch):
    """
    Cover base.py:755 ("type" to "Type" branch) by forcing colname mapping.
    """
    _clear_jsonapi_attrs_cache(models.ThingWType)
    monkeypatch.setattr(models.ThingWType, "colname_to_attrname", classmethod(lambda cls, col: col))
    _clear_jsonapi_attrs_cache(models.ThingWType)
    attrs = models.ThingWType._s_jsonapi_attrs
    assert "Type" in attrs
    _clear_jsonapi_attrs_cache(models.ThingWType)
