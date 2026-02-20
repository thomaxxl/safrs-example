import builtins
from types import SimpleNamespace

import pytest
import sqlalchemy

from app import models

import safrs.jsonapi as jsonapi
from safrs.errors import NotFoundError, ValidationError


def _thing_api():
    class ThingAPI(jsonapi.SAFRSRestAPI):
        SAFRSObject = models.Thing

    return ThingAPI()


def _person_rpc_api():
    class PersonRPCAPI(jsonapi.SAFRSJSONRPCAPI):
        SAFRSObject = models.Person
        method_name = "my_rpc"

    return PersonRPCAPI()


def _rel_api_stub(direction, parse_args_fn, target=None):
    api = object.__new__(jsonapi.SAFRSRestRelationshipAPI)
    api.SAFRSObject = SimpleNamespace(relationship=SimpleNamespace(direction=direction))
    api.relationship = api.SAFRSObject.relationship
    api.source_class = SimpleNamespace(__name__="Parent")
    api.parse_args = parse_args_fn
    api.target = target or SimpleNamespace(_s_type="Target", get_instance=lambda _id: None)
    api.child_object_id = "ChildId"
    api.parent_object_id = "ParentId"
    api.rel_name = "rel"
    return api


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


def test_post_bulk_and_unserializable_warning_branches(app, api, monkeypatch):
    """
    Targets: jsonapi.py 429, 446
    """
    thing_api = _thing_api()

    with app.test_request_context(
        "/thing/",
        method="POST",
        json={"data": [{"type": models.Thing._s_type, "attributes": {"name": "x"}}]},
    ):
        from flask import request
        with monkeypatch.context() as m:
            req_cls = type(request._get_current_object())
            m.setattr(req_cls, "is_bulk", property(lambda _self: False), raising=False)
            m.setattr(thing_api, "_create_instance", lambda *_a, **_k: {"ok": True})
            resp = thing_api.post()
            assert resp.status_code == 201

    with app.test_request_context(
        "/thing/",
        method="POST",
        json={"data": {"type": models.Thing._s_type, "attributes": {"name": "x"}}},
    ):
        with monkeypatch.context() as m:
            m.setattr(thing_api, "_create_instance", lambda *_a, **_k: SimpleNamespace(jsonapi_id="1"))
            resp = thing_api.post()
            assert resp.status_code == 201


def test_rest_delete_missing_id_branch(app, api):
    """
    Targets: jsonapi.py 522
    """
    thing_api = _thing_api()
    with app.test_request_context("/thing/", method="DELETE"):
        with pytest.raises(ValidationError):
            thing_api.delete()


def test_relationship_init_and_get_notfound_branches(app, api, mock_thing, mock_subthing):
    """
    Targets: jsonapi.py 587, 628, 630
    """
    class Node:
        _s_object_id = "NodeId"

    rel = SimpleNamespace(parent=SimpleNamespace(class_=Node), mapper=SimpleNamespace(class_=Node), key="friends")

    class DummyRelAPI(jsonapi.SAFRSRestRelationshipAPI):
        SAFRSObject = SimpleNamespace(relationship=rel)

    rel_api = DummyRelAPI()
    assert rel_api.child_object_id == "NodeId2"

    api_628 = _rel_api_stub(
        direction=object(),
        parse_args_fn=lambda **_k: (None, mock_thing),
        target=SimpleNamespace(_s_type=models.SubThing._s_type, get_instance=lambda _id: mock_subthing),
    )
    with app.test_request_context("/rel", method="GET"):
        with pytest.raises(NotFoundError):
            api_628.get(**{"ChildId": mock_subthing.id})

    api_630 = _rel_api_stub(
        direction=object(),
        parse_args_fn=lambda **_k: (None, []),
        target=SimpleNamespace(_s_type=models.SubThing._s_type, get_instance=lambda _id: mock_subthing),
    )
    with app.test_request_context("/rel", method="GET"):
        with pytest.raises(NotFoundError):
            api_630.get(**{"ChildId": mock_subthing.id})


def test_relationship_post_delete_and_parse_args_branches(app, api, mock_subthing):
    """
    Targets: jsonapi.py 790, 797, 845, 890, 896, 909
    """
    manytoone_api = _rel_api_stub(
        direction=jsonapi.MANYTOONE,
        parse_args_fn=lambda **_k: (SimpleNamespace(), None),
        target=SimpleNamespace(_s_type=models.SubThing._s_type, get_instance=lambda _id: mock_subthing),
    )
    with app.test_request_context("/rel", method="POST", json={}):
        with pytest.raises(ValidationError):
            manytoone_api.post()
    with app.test_request_context("/rel", method="POST", json={"data": [{"id": mock_subthing.id, "type": models.SubThing._s_type}]}):
        with pytest.raises(ValidationError):
            manytoone_api.post()

    tomany_api = _rel_api_stub(
        direction=object(),
        parse_args_fn=lambda **_k: (SimpleNamespace(), []),
        target=SimpleNamespace(_s_type=models.SubThing._s_type, get_instance=lambda _id: mock_subthing),
    )
    with app.test_request_context("/rel", method="DELETE", json={"data": []}):
        from flask import request
        req_obj = request._get_current_object()
        setattr(req_obj, "get_jsonapi_payload", lambda: "not-a-dict")
        with pytest.raises(ValidationError):
            tomany_api.delete()

    with app.test_request_context("/rel", method="DELETE", json={"data": [{"id": mock_subthing.id, "type": "Wrong"}]}):
        with pytest.raises(ValidationError):
            tomany_api.delete()

    with app.test_request_context("/rel", method="DELETE", json={"data": [{"id": mock_subthing.id, "type": models.SubThing._s_type}]}):
        resp = tomany_api.delete()
        assert resp.status_code == 204

    parse_api = object.__new__(jsonapi.SAFRSRestRelationshipAPI)
    parse_api.parent_object_id = "ParentId"
    with pytest.raises(ValidationError):
        parse_api.parse_args()


def test_jsonrpc_post_get_invalid_method_public_and_payload_branches(app, monkeypatch):
    """
    Targets: jsonapi.py 964, 973, 975, 983, 1014, 1016
    """
    rpc_api = _person_rpc_api()

    with monkeypatch.context() as m:
        m.setattr(models.Person, "get_instance", classmethod(lambda cls, _id: None))
        with app.test_request_context("/", method="POST", json={"a": 1}):
            with pytest.raises(ValidationError):
                rpc_api.post(**{rpc_api._s_object_id: "bad-id"})

    with app.test_request_context("/", method="POST", json={"a": 1}):
        rpc_api.method_name = "does_not_exist"
        with pytest.raises(ValidationError):
            rpc_api.post()

    def _private_rpc(**kwargs):
        return kwargs

    monkeypatch.setattr(models.Person, "_private_rpc", staticmethod(_private_rpc), raising=False)
    with app.test_request_context("/", method="POST", json={"a": 1}):
        rpc_api.method_name = "_private_rpc"
        with pytest.raises(ValidationError):
            rpc_api.post()

    def plain_rpc(**kwargs):
        return kwargs

    plain_rpc.valid_jsonapi = False
    setattr(plain_rpc, "__rest_doc", {})
    monkeypatch.setattr(models.Person, "plain_rpc", staticmethod(plain_rpc), raising=False)
    with app.test_request_context("/", method="POST", json={"a": 1}):
        rpc_api.method_name = "plain_rpc"
        resp = rpc_api.post()
        assert resp.get_json() == {"a": 1}

    with app.test_request_context("/", method="GET"):
        rpc_api.method_name = "does_not_exist_get"
        with pytest.raises(ValidationError):
            rpc_api.get()

    with app.test_request_context("/", method="GET"):
        rpc_api.method_name = "_private_rpc"
        with pytest.raises(ValidationError):
            rpc_api.get()


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
