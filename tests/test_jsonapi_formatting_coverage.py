from types import SimpleNamespace

import pytest
import sqlalchemy

from app import models
import safrs.jsonapi_formatting as jsonapi_formatting
from safrs.errors import GenericError, ValidationError


def test_jsonapi_filter_list_handles_safrs_and_non_safrs_items(app, api, mock_thing):
    with app.test_request_context("/thing"):
        items = ["raw-item", mock_thing]
        result = jsonapi_formatting.jsonapi_filter_list(items)
        assert "raw-item" in result
        assert any(getattr(item, "id", None) == mock_thing.id for item in result)


def test_jsonapi_sort_id_primary_key_fallback_and_jsonapi_attr_branch(app, api):
    fake_model = SimpleNamespace(
        _s_jsonapi_attrs={},
        id_type=SimpleNamespace(primary_keys=["pk"]),
        pk=SimpleNamespace(name="pk"),
    )
    records = [SimpleNamespace(pk=2), SimpleNamespace(pk=1)]
    with app.test_request_context("/?sort=id"):
        sorted_records = jsonapi_formatting.jsonapi_sort(records, fake_model)
    assert [record.pk for record in sorted_records] == [1, 2]

    no_pk_model = SimpleNamespace(_s_jsonapi_attrs={}, id_type=SimpleNamespace(primary_keys=[]))
    with app.test_request_context("/?sort=id"):
        untouched = jsonapi_formatting.jsonapi_sort(records, no_pk_model)
    assert untouched == records

    with app.test_request_context("/?sort=some_attr"):
        # hits "sorting not implemented for jsonapi_attr" branch
        result = jsonapi_formatting.jsonapi_sort(object(), models.UserWithJsonapiAttr)
    assert result is not None


def test_jsonapi_sort_order_by_exception_branches(app, api):
    fake_model = SimpleNamespace(_s_jsonapi_attrs={"name": object()}, name=SimpleNamespace())

    class QueryRaisesArgumentError:
        def order_by(self, _attr):
            raise sqlalchemy.exc.ArgumentError("bad sort arg")

    class QueryRaisesGenericError:
        def order_by(self, _attr):
            raise RuntimeError("bad sort")

    with app.test_request_context("/?sort=name"):
        arg_err_query = QueryRaisesArgumentError()
        assert jsonapi_formatting.jsonapi_sort(arg_err_query, fake_model) is arg_err_query

    with app.test_request_context("/?sort=name"):
        generic_err_query = QueryRaisesGenericError()
        assert jsonapi_formatting.jsonapi_sort(generic_err_query, fake_model) is generic_err_query


def test_paginate_value_error_dict_no_offset_and_error_paths(app, api, monkeypatch):
    with app.test_request_context("/"):
        monkeypatch.setattr(jsonapi_formatting, "get_request_param", lambda *_a, **_k: "invalid")
        with pytest.raises(ValidationError):
            jsonapi_formatting.paginate([])

    class FakeSAFRSObject:
        _s_url = "/Fake"
        id = object()
        id_type = SimpleNamespace(primary_keys=["id"])

        @staticmethod
        def _s_count():
            return 3

    with app.test_request_context("/"):
        monkeypatch.setattr(
            jsonapi_formatting,
            "get_request_param",
            lambda param, default=0: 0 if param == "page_offset" else 2,
        )
        links, instances, count = jsonapi_formatting.paginate({"k": "v"}, FakeSAFRSObject)
        assert instances == {"k": "v"}
        assert count == 3
        assert "self" in links

    with app.test_request_context("/"):
        monkeypatch.setattr(
            jsonapi_formatting,
            "get_request_param",
            lambda param, default=0: 0 if param == "page_offset" else 2,
        )
        links, instances, count = jsonapi_formatting.paginate(object(), FakeSAFRSObject)
        assert instances == []
        assert count == 3
        assert "self" in links

    class QueryOverflow:
        def offset(self, _value):
            return self

        def limit(self, _value):
            return self

        def all(self):
            raise OverflowError("overflow")

    with app.test_request_context("/"):
        monkeypatch.setattr(
            jsonapi_formatting,
            "get_request_param",
            lambda param, default=0: 0 if param == "page_offset" else 2,
        )
        with pytest.raises(ValidationError):
            jsonapi_formatting.paginate(QueryOverflow(), FakeSAFRSObject)

    class QueryCompileRecover:
        def offset(self, _value):
            return self

        def limit(self, _value):
            return self

        def all(self):
            raise sqlalchemy.exc.CompileError("MSSQL requires an order_by")

        def order_by(self, _attr):
            return QueryGood()

    class QueryGood:
        def offset(self, _value):
            return self

        def limit(self, _value):
            return self

        def all(self):
            return ["ok"]

    with app.test_request_context("/"):
        monkeypatch.setattr(
            jsonapi_formatting,
            "get_request_param",
            lambda param, default=0: 0 if param == "page_offset" else 2,
        )
        _links, instances, _count = jsonapi_formatting.paginate(QueryCompileRecover(), FakeSAFRSObject)
        assert instances == ["ok"]

    class QueryCompileFail:
        def offset(self, _value):
            return self

        def limit(self, _value):
            return self

        def all(self):
            raise sqlalchemy.exc.CompileError("Different compile error")

    with app.test_request_context("/"):
        monkeypatch.setattr(
            jsonapi_formatting,
            "get_request_param",
            lambda param, default=0: 0 if param == "page_offset" else 2,
        )
        with pytest.raises(GenericError):
            jsonapi_formatting.paginate(QueryCompileFail(), FakeSAFRSObject)

    class QueryGenericFail:
        def offset(self, _value):
            return self

        def limit(self, _value):
            return self

        def all(self):
            raise RuntimeError("boom")

    with app.test_request_context("/"):
        monkeypatch.setattr(
            jsonapi_formatting,
            "get_request_param",
            lambda param, default=0: 0 if param == "page_offset" else 2,
        )
        with pytest.raises(GenericError):
            jsonapi_formatting.paginate(QueryGenericFail(), FakeSAFRSObject)


def test_jsonapi_format_response_limit_validation_and_errors_key(app, api, monkeypatch):
    with app.test_request_context("/"):
        monkeypatch.setattr(jsonapi_formatting, "get_request_param", lambda *_a, **_k: "invalid")
        with pytest.raises(ValidationError):
            jsonapi_formatting.jsonapi_format_response(data=[])

    with app.test_request_context("/"):
        monkeypatch.setattr(jsonapi_formatting, "get_request_param", lambda *_a, **_k: 5)
        response = jsonapi_formatting.jsonapi_format_response(data=[{"id": 1}], errors=[{"detail": "x"}], count=1)
        assert response["meta"]["limit"] == 5
        assert response["errors"] == [{"detail": "x"}]
        assert "included" in response
