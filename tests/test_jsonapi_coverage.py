import builtins
from types import SimpleNamespace

import pytest
import sqlalchemy

from app import models

import safrs.jsonapi as jsonapi
from safrs.errors import ValidationError


def _thing_api():
    class ThingAPI(jsonapi.SAFRSRestAPI):
        SAFRSObject = models.Thing

    return ThingAPI()


def _person_rpc_api():
    class PersonRPCAPI(jsonapi.SAFRSJSONRPCAPI):
        SAFRSObject = models.Person
        method_name = "my_rpc"

    return PersonRPCAPI()


def test_resource_head_options_fallback_to_make_response(app, api, monkeypatch):
    """
    Covers Resource.head/options fallback branch (make_response()) when super has no method.
    Targets: jsonapi.py 64-69, 75-80 (fallback path)
    """
    class Dummy(jsonapi.Resource):
        pass

    real_hasattr = builtins.hasattr

    def fake_hasattr(obj, name):
        # Force fallback branch
        if name in {"head", "options"}:
            return False
        return real_hasattr(obj, name)

    monkeypatch.setattr(builtins, "hasattr", fake_hasattr)

    with app.test_request_context("/"):
        assert Dummy().head().status_code == 200
        assert Dummy().options().status_code == 200


def test_resource_head_options_call_super_when_present(app, api, monkeypatch):
    """
    Covers Resource.head/options super() call branch.
    Targets: jsonapi.py 66 and 77 (super().head/options called)
    """
    class Dummy(jsonapi.Resource):
        pass

    def _super_impl(self, *args, **kwargs):
        return jsonapi.make_response()

    # Ensure hasattr(super(), ...) is True and the call succeeds
    monkeypatch.setattr(jsonapi.FRSResource, "head", _super_impl, raising=False)
    monkeypatch.setattr(jsonapi.FRSResource, "options", _super_impl, raising=False)

    with app.test_request_context("/"):
        assert Dummy().head().status_code == 200
        assert Dummy().options().status_code == 200


@pytest.mark.parametrize(
    "target_data, patch_get_instance",
    [
        ("not-a-dict", False),  # 93
        ({}, False),  # 96
        ({"id": "", "type": models.Thing._s_type}, False),  # 99
        ({"id": "x", "type": ""}, False),  # (100/101)
        ({"id": "x", "type": "wrong"}, False),  # 103
        ({"id": "x", "type": models.Thing._s_type}, True),  # 106 via patched get_instance
    ],
)
def test_parse_target_data_validation_errors(monkeypatch, target_data, patch_get_instance):
    """
    Targets: jsonapi.py 93, 96, 99, 103, 106 via different invalid payload shapes.
    """
    class Dummy(jsonapi.Resource):
        target = models.Thing

    if patch_get_instance:
        monkeypatch.setattr(models.Thing, "get_instance", classmethod(lambda cls, _id: None))

    with pytest.raises(ValidationError):
        Dummy()._parse_target_data(target_data)


def test_get_swagger_sort_includes_string_and_integer_attrs():
    """
    Targets: jsonapi.py 156 (attr_list.append(attr_name) branch)
    """
    class DummySAFRSObject:
        _s_class_name = "Dummy"
        _s_jsonapi_attrs = {
            "name": SimpleNamespace(type=sqlalchemy.String),
            "age": SimpleNamespace(type=sqlalchemy.Integer),
            "active": SimpleNamespace(type=sqlalchemy.Boolean),
        }

    class DummyResource(jsonapi.Resource):
        SAFRSObject = DummySAFRSObject

    spec = DummyResource.get_swagger_sort()
    default_val = spec["default"]  # csv string, eg "id,name,age"
    assert "name" in default_val
    assert "age" in default_val
    assert "active" not in default_val


def test_patch_validation_branches(app, api, monkeypatch):
    """
    Targets:
      - 309: payload isn't a dict (forced via monkeypatch)
      - 314-318: bulk patch list path
      - 316: invalid item inside bulk list
      - 321: data not dict (and not list)
      - 323: id missing in URL while body has dict data
    """
    thing_api = _thing_api()

    # 309: payload isn't a dict (force request.get_jsonapi_payload() to return non-dict)
    with app.test_request_context("/thing/", method="PATCH", json={"data": {}}):
        from flask import request
        with monkeypatch.context() as m:
            req_obj = request._get_current_object()
            m.setattr(req_obj, "get_jsonapi_payload", lambda: "not-a-dict", raising=False)
            with pytest.raises(ValidationError):
                thing_api.patch()

    # 314-318: bulk patch list; stub _patch_instance to avoid DB work
    with app.test_request_context("/thing/", method="PATCH", json={"data": [{"whatever": True}]}):
        with monkeypatch.context() as m:
            m.setattr(thing_api, "_patch_instance", lambda *_a, **_k: None)
            resp = thing_api.patch()
            assert resp.status_code == 202

    # 316: non-dict item in bulk patch => "Invalid Data Object"
    with app.test_request_context("/thing/", method="PATCH", json={"data": ["bad-item"]}):
        with pytest.raises(ValidationError):
            thing_api.patch()

    # 321: data not a dict (and not list) => "Invalid Data Object"
    with app.test_request_context("/thing/", method="PATCH", json={"data": "not-a-dict"}):
        with pytest.raises(ValidationError):
            thing_api.patch()

    # 323: URL id missing but body data is a dict => "Invalid ID"
    with app.test_request_context("/thing/", method="PATCH", json={"data": {"id": "some-id"}}):
        with pytest.raises(ValidationError):
            thing_api.patch()


def test_patch_instance_no_instance_branch(app, api, mock_thing, monkeypatch):
    """
    Targets: jsonapi.py 360 ('No instance with ID') by forcing _parse_target_data to return None.
    """
    thing_api = _thing_api()

    data = {"id": mock_thing.id, "type": models.Thing._s_type, "attributes": {}}
    monkeypatch.setattr(thing_api, "_parse_target_data", lambda *_a, **_k: None)

    with pytest.raises(ValidationError):
        thing_api._patch_instance(data, mock_thing.id)


def test_post_and_create_instance_validation_branches(app, api, monkeypatch):
    """
    Targets:
      - 416: POSTing to instance not allowed
      - 423: missing "data" in payload
      - 429: bulk POST without bulk extension (request.is_bulk False)
      - 462: _create_instance rejects non-dict
      - 473: client-generated ids not allowed warning branch
    """
    thing_api = _thing_api()

    # 423: POST missing "data"
    with app.test_request_context("/thing/", method="POST", json={}):
        with pytest.raises(ValidationError):
            thing_api.post()

    # 416: POSTing to instance is not allowed (call method directly with kwargs)
    with app.test_request_context("/thing/some-id", method="POST", json={"data": {"type": models.Thing._s_type}}):
        with pytest.raises(ValidationError):
            thing_api.post(**{thing_api._s_object_id: "some-id"})

    # 429: bulk POST but request.is_bulk is False -> warning branch executed
    with app.test_request_context(
        "/thing/",
        method="POST",
        json={"data": [{"type": models.Thing._s_type, "attributes": {"name": "x"}}]},
    ):
        # Avoid touching DB; return JSON-serializable objects
        with monkeypatch.context() as m:
            m.setattr(thing_api, "_create_instance", lambda *_a, **_k: {"ok": True})
            resp = thing_api.post()
            assert resp.status_code == 201

    # 462: _create_instance rejects non-dict
    with pytest.raises(ValidationError):
        thing_api._create_instance("not-a-dict")

    # 473: client-generated ids are not allowed -> warning branch executed
    with monkeypatch.context() as m:
        m.setattr(models.Thing, "_s_post", classmethod(lambda cls, **kwargs: {"created": True}))
        created = thing_api._create_instance({"type": models.Thing._s_type, "id": "client-id"})
        assert created == {"created": True}


def test_jsonrpc_get_invalid_id_branch(monkeypatch):
    """
    Targets: jsonapi.py 1001-1004
    """
    rpc_api = _person_rpc_api()
    monkeypatch.setattr(models.Person, "get_instance", classmethod(lambda cls, _id: None))
    with pytest.raises(ValidationError):
        rpc_api.get(**{rpc_api._s_object_id: "does-not-exist"})


def test_jsonrpc_create_response_non_jsonapi_and_default_meta(app):
    """
    Targets: jsonapi.py 1028-1031
    """
    rpc_api = _person_rpc_api()

    def non_jsonapi_method(**_kwargs):
        return {"raw": True}

    non_jsonapi_method.valid_jsonapi = False

    def default_method(**_kwargs):
        return 42

    with app.test_request_context("/"):
        raw_resp = rpc_api._create_rpc_response(non_jsonapi_method, {})
        assert raw_resp.status_code == 200
        assert raw_resp.get_json() == {"raw": True}

        default_resp = rpc_api._create_rpc_response(default_method, {})
        assert default_resp.status_code == 200
        assert default_resp.get_json() == {"meta": {"result": 42}}
