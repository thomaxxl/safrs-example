import json
from types import SimpleNamespace

from flask import g
import safrs
import safrs.base as safrs_base
from sqlalchemy.exc import InvalidRequestError

from app import models
from tests.factories import BookFactory, PersonFactory, PublisherFactory
import builtins
import pytest
from safrs.errors import ValidationError, SystemValidationError
from sqlalchemy.exc import InvalidRequestError, ArgumentError

from app import models, models_stateless


def _clear_s_columns_cache() -> None:
    """
    _s_columns is lru_cache'd (classmethod under a classproperty).
    Clear it so request-context filtering branches are not bypassed.
    """
    try:
        safrs_base.SAFRSBase.__dict__["_s_columns"].fget.__func__.cache_clear()
    except Exception:
        pass


def _clear_safrs_subclasses_cache() -> None:
    """
    _safrs_subclasses is lru_cache'd; clear to ensure loop/branch coverage.
    """
    try:
        safrs_base.SAFRSBase._safrs_subclasses.cache_clear()
    except Exception:
        pass

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

def test_init_with_Type_kwarg_sets_type_column(monkeypatch):
    """
    Covers SAFRSBase.__init__ 'Type' kwarg mapping (your missing ~352).
    Use ThingWType but neutralize auto-commit by no-op commit.
    """
    monkeypatch.setattr(safrs.DB.session, "commit", lambda: None)
    twt = models.ThingWType(Type="MyType")
    assert twt.type == "MyType"


def test_init_does_not_add_or_commit_implicitly(monkeypatch):
    calls = {"add": 0, "commit": 0}

    def fake_add(_obj):
        calls["add"] += 1

    def fake_commit():
        calls["commit"] += 1

    monkeypatch.setattr(safrs.DB.session, "add", fake_add)
    monkeypatch.setattr(safrs.DB.session, "commit", fake_commit)
    models.Thing(name="constructor-only", description="x")
    assert calls["add"] == 0
    assert calls["commit"] == 0


def test_init_with_jsonapi_attr_kwarg_calls_setter():
    """
    Covers SAFRSBase.__init__ jsonapi_attr kwarg handling (also around ~352).
    UserWithJsonapiAttr.some_attr setter sets .name in safrs-example models.
    """
    u = models.UserWithJsonapiAttr(some_attr="via_setter")
    assert u.name == "via_setter"


def test_s_post_strips_client_generated_composite_pks(monkeypatch):
    """
    Covers _s_post branch stripping PK columns when allow_client_generated_ids is False
    (your missing ~444-445).
    """
    monkeypatch.setattr(safrs.DB.session, "commit", lambda: None)

    item = models.PKItem._s_post(None, pk_A="A", pk_B="B", foo="bar")
    # pk_A / pk_B were passed but should have been removed from attributes
    assert item.pk_A is None
    assert item.pk_B is None


def test_add_rels_validation_paths():
    """
    Covers _add_rels validation errors:
    - _s_allow_add_rels guard (~516)
    - rel_val shape check (~518)
    - data2inst payload check (~507) + ensures _safrs_subclasses executes (~554)
    - payload type mismatch (~530)
    """
    _clear_safrs_subclasses_cache()

    book = models.Book(title="b")

    # Guard: _s_allow_add_rels must be enabled
    book._s_allow_add_rels = False
    with pytest.raises(ValidationError):
        book._add_rels(reader={"data": {"id": "1", "type": "Person"}})
    book._s_allow_add_rels = True

    # Invalid relationship payload (missing "data")
    with pytest.raises(ValidationError):
        book._add_rels(reader={})

    # Invalid relationship payload in data2inst (missing "type")
    with pytest.raises(ValidationError):
        book._add_rels(reader={"data": {"id": "1"}})

    # Wrong shape for MANYTOONE: list instead of dict
    with pytest.raises(ValidationError):
        book._add_rels(reader={"data": []})


def test_add_rels_to_many_empty_list_ok():
    """
    Covers to-many branch in _add_rels (~524-525) without triggering _s_post().
    Book has _s_allow_add_rels=True in safrs-example models.
    """
    book = models.Book(title="b")
    book._add_rels(reviews={"data": []})
    assert list(book.reviews) == []


def test_s_columns_request_context_branch(app):
    """
    Covers request-context branch in _s_columns (~578).
    Important: clear cache first, otherwise earlier calls can bypass the branch.
    """
    _clear_s_columns_cache()
    with app.test_request_context("/"):
        cols = models.Person._s_columns
        assert cols  # just make sure we executed the branch


def test_s_check_perm_missing_guard_branches():
    """
    Covers extra _s_check_perm guards:
    - underscore names (~650)
    - stateless/no mapper (~660)
    - invalid property raises SystemValidationError (~686)
    """
    _clear_check_perm_cache()
    assert models.Person._s_check_perm("_private", "r") is False

    _clear_check_perm_cache()
    assert models_stateless.Test._s_check_perm("anything", "r") is False

    _clear_check_perm_cache()
    with pytest.raises(SystemValidationError):
        models.Person._s_check_perm("definitely_not_a_property", "r")


def test_instance_jsonapi_attrs_hasattr_fallback_branch(monkeypatch):
    """
    Covers instance _s_jsonapi_attrs fallback when hasattr(self, attr) is False (~716-717).
    This is a defensive branch; easiest is to force hasattr False for one attribute.
    """
    thing = models.Thing(name="n", description="X")
    real_hasattr = builtins.hasattr

    def fake_hasattr(obj, name):
        if obj is thing and name == "description":
            return False
        return real_hasattr(obj, name)

    with monkeypatch.context() as mp:
        mp.setattr(builtins, "hasattr", fake_hasattr)
        attrs = thing._s_jsonapi_attrs
        assert attrs.get("description") == "X"


def test_auto_commit_setter_sets_db_commit_flag():
    """
    Covers _s_auto_commit setter (~788).
    It sets the class-level db_commit flag; restore to avoid cross-test side effects.
    """
    thing = models.Thing(name="x", description="y")
    orig = models.Thing.db_commit
    try:
        thing._s_auto_commit = (not orig)
        assert models.Thing.db_commit is (not orig)
    finally:
        thing._s_auto_commit = orig
        assert models.Thing.db_commit is orig


def test_s_post_marks_write_and_honors_db_commit_flag(db_session):
    orig = models.Thing.db_commit
    try:
        models.Thing.db_commit = True
        token = safrs.tx.begin_request()
        try:
            models.Thing._s_post(None, name="uow-default", description="d")
            assert safrs.tx.has_writes() is True
            assert safrs.tx.should_autocommit() is True
        finally:
            safrs.tx.end_request(token)
            db_session.rollback()

        models.Thing.db_commit = False
        token = safrs.tx.begin_request()
        try:
            models.Thing._s_post(None, name="uow-optout", description="d")
            assert safrs.tx.has_writes() is True
            assert safrs.tx.should_autocommit() is False
        finally:
            safrs.tx.end_request(token)
            db_session.rollback()
    finally:
        models.Thing.db_commit = orig


def test_get_instance_by_id_and_s_query_error_paths(monkeypatch, db_session):
    """
    Covers:
    - _s_get_instance_by_id (~849-850)
    - _s_query InvalidRequestError handling for stateless types (~890-893)
    - _s_query fallback to _table on generic exception (~896)
    """
    p = models.Person(name="Q", email="q@example.com")
    db_session.add(p)
    db_session.flush()

    q = models.Person._s_get_instance_by_id(p.jsonapi_id)
    assert q.first() == p

    class DummyStateless(safrs_base.SAFRSBase):
        _s_stateless = True

    monkeypatch.setattr(
        safrs.DB.session,
        "query",
        lambda *_a, **_k: (_ for _ in ()).throw(InvalidRequestError("boom")),
    )
    assert DummyStateless._s_query is None

    class DummyWithTable(safrs_base.SAFRSBase):
        # base._s_query uses `if _table:` so don't use a SQLAlchemy Table here
        _table = models.Person

    def fake_query(arg):
        if arg is DummyWithTable:
            raise RuntimeError("boom")
        if arg is DummyWithTable._table:
            return "fallback_query"
        raise AssertionError("unexpected query arg")

    monkeypatch.setattr(safrs.DB.session, "query", fake_query)
    assert DummyWithTable._s_query == "fallback_query"


def test_count_large_table_warning_and_sample_id_first_exception(monkeypatch, db_session):
    """
    Covers:
    - normal _s_count path (~1087-1088)
    - large table warning branch (~1108) by forcing MAX_TABLE_COUNT to 0
    - _s_sample_id query.first exception path (~1127-1128)
    """
    db_session.add(models.Person(name="CountMe", email="countme@example.com"))
    db_session.flush()

    orig_get_config = safrs_base.get_config
    monkeypatch.setattr(
        safrs_base,
        "get_config",
        lambda key: 0 if key == "MAX_TABLE_COUNT" else orig_get_config(key),
    )
    assert models.Person._s_count() >= 1

    class BoomQuery:
        def first(self):
            raise Exception("boom")

    monkeypatch.setattr(models.Person, "query", BoomQuery())
    assert isinstance(models.Person._s_sample_id(), str)


def test_Type_property_setter_executes(monkeypatch):
    """
    Covers Type property setter (~1304-1305).
    Normal `obj.Type = x` is rewritten to `obj.type = x` by SAFRSBase.__setattr__,
    so call the descriptor setter directly.
    """
    monkeypatch.setattr(safrs.DB.session, "commit", lambda: None)
    # Avoid passing `type=` in __init__ (strict request-context parsing).
    twt = models.ThingWType()
    # Call the property setter directly; twt.Type = ... is rewritten by __setattr__.
    safrs_base.SAFRSBase.Type.fset(twt, "new")
    assert twt.type == "new"

def test_unicode_and_http_methods_cover_remaining_lines(monkeypatch):
    # make it robust even if a model has auto-commit enabled
    monkeypatch.setattr(safrs.DB.session, "add", lambda *_a, **_k: None)
    monkeypatch.setattr(safrs.DB.session, "commit", lambda *_a, **_k: None)

    t = models.Thing(name="n", description="d")

    assert t.__unicode__() == "n"      # covers 1087-1088
    assert "GET" in t.http_methods     # covers 554
