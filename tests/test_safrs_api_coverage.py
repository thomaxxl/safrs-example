import builtins
from types import SimpleNamespace

import pytest
import werkzeug
from flask import Response
from flask_restful import Resource

import safrs
import safrs.safrs_api as safrs_api
from safrs import tx as safrs_tx
from safrs.errors import SystemValidationError


def test_expose_object_logs_outside_app_and_parse_doc_failure(monkeypatch):
    class DummyRestAPI:
        pass

    class DummyObject:
        _s_expose = True
        _rest_api = DummyRestAPI
        http_methods = ["GET", "POST", "PATCH", "DELETE"]
        _s_collection_name = "DummyObjects"
        _s_type = "DummyObject"
        _s_relationships = {}

        @classmethod
        def get_endpoint(cls, type=None):
            return "dummy.endpoint.instance" if type == "instance" else "dummy.endpoint"

    calls = {"add_resource": 0}
    fake_api = SimpleNamespace(
        swaggerui_blueprint=False,
        _swagger_object={"tags": [], "definitions": {}},
        _als_resources=[],
        expose_methods=lambda *a, **k: None,
        expose_relationship=lambda *a, **k: None,
        update_spec=lambda: None,
        add_resource=lambda *a, **k: calls.__setitem__("add_resource", calls["add_resource"] + 1),
    )

    monkeypatch.setattr(safrs_api, "current_app", None)
    monkeypatch.setattr(safrs_api, "parse_object_doc", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")))
    safrs_api.SAFRSAPI.expose_object(fake_api, DummyObject)
    assert calls["add_resource"] == 2
    assert fake_api._swagger_object["tags"][0]["name"] == "DummyObjects"

    class Hidden:
        _s_expose = False

    with pytest.raises(SystemValidationError):
        safrs_api.SAFRSAPI.expose_object(fake_api, Hidden)


def test_expose_iterates_all_objects():
    exposed = []
    fake_api = SimpleNamespace(expose_object=lambda obj, url_prefix="", **props: exposed.append((obj, url_prefix, props)))
    safrs_api.SAFRSAPI.expose(fake_api, "a", "b", url_prefix="/x", k=1)
    assert exposed == [("a", "/x", {"k": 1}), ("b", "/x", {"k": 1})]


def test_expose_relationship_skip_and_object_id_fallback(monkeypatch):
    calls = []
    fake_api = SimpleNamespace(add_resource=lambda *a, **k: calls.append((a, k)))

    hidden_target = SimpleNamespace(_s_expose=False, _relationship_api=Resource)
    hidden_rel = SimpleNamespace(
        mapper=SimpleNamespace(class_=hidden_target),
        key="hidden_rel",
        parent=SimpleNamespace(class_=SimpleNamespace(http_methods=["GET"], custom_decorators=[], decorators=[], __name__="Parent")),
    )
    safrs_api.SAFRSAPI.expose_relationship(fake_api, hidden_rel, "", ["T"], {})
    assert calls == []

    class Parent:
        __name__ = "Parent"
        http_methods = ["GET", "PATCH", "DELETE"]
        custom_decorators = []
        decorators = []
        _s_expose = True
        _relationship_api = Resource

    rel = SimpleNamespace(
        mapper=SimpleNamespace(class_=Parent),
        key="self_rel",
        parent=SimpleNamespace(class_=Parent),
        direction=safrs_api.MANYTOONE,
    )
    monkeypatch.setattr(safrs_api, "api_decorator", lambda cls, _decorator: cls)
    monkeypatch.setattr(safrs_api, "swagger_relationship_doc", lambda *_a, **_k: (lambda f: f))
    safrs_api.SAFRSAPI.expose_relationship(fake_api, rel, "/api", ["Tag"], {})
    # First add_resource for relation, second add_resource for /<target_id>; self-referencing gets "2" suffix
    second_url = calls[-1][0][1]
    assert second_url.endswith("self_rel/<string:Parent2>")


def test_add_resource_validation_error_branch_exits(monkeypatch):
    class DummyResource(Resource):
        SAFRSObject = SimpleNamespace()

    api = safrs_api.SAFRSAPI.__new__(safrs_api.SAFRSAPI)
    api._swagger_object = {"definitions": {}, "paths": {}}
    api._add_oas_resource_definitions = lambda _res, path_item: path_item.update({"get": {"summary": "x", "parameters": [], "responses": {}}})
    api._add_oas_req_params = lambda *_a, **_k: None
    api._add_oas_references = lambda *_a, **_k: None
    api.get_resource_methods = lambda _res: ["get"]

    monkeypatch.setattr(safrs_api, "validate_path_item_object", lambda *_a, **_k: (_ for _ in ()).throw(safrs_api.FRSValidationError("bad")))
    monkeypatch.setattr(builtins, "exit", lambda *_a, **_k: (_ for _ in ()).throw(SystemExit()))
    with pytest.raises(SystemExit):
        safrs_api.SAFRSAPI.add_resource(api, DummyResource, "/safrs_api_cov_validation")


def test_add_oas_references_and_resource_definition_error_paths(monkeypatch):
    api_like = SimpleNamespace(_swagger_object={"definitions": {}})

    class Ref:
        def reference(self):
            return {"$ref": "#/x", "type": "object"}

    fake_safrs_obj = SimpleNamespace(swagger_models={"instance": Ref(), "collection": Ref()})
    path_item = {"patch": {"responses": {"201": {"schema": {"type": "x"}}}}}
    safrs_api.SAFRSAPI._add_oas_references(api_like, fake_safrs_obj, path_item, "patch", True, None)
    assert path_item["patch"]["responses"]["201"]["schema"]["$ref"] == "#/x"
    assert "type" not in path_item["patch"]["responses"]["201"]["schema"]

    path_item = {"patch": {"responses": {"201": {"schema": {"type": "x"}}}}}
    safrs_api.SAFRSAPI._add_oas_references(api_like, fake_safrs_obj, path_item, "patch", False, None)
    assert path_item["patch"]["responses"]["201"]["schema"]["$ref"] == "#/x"
    assert "type" not in path_item["patch"]["responses"]["201"]["schema"]

    class DummyResource:
        methods = []

    monkeypatch.setattr(api_like, "get_resource_methods", lambda _r: ["TRACE", "GET"], raising=False)
    safrs_api.SAFRSAPI._add_oas_resource_definitions(api_like, DummyResource, {})

    monkeypatch.setattr(api_like, "get_resource_methods", lambda _r: [], raising=False)
    monkeypatch.setattr(safrs_api, "validate_definitions_object", lambda *_a, **_k: (_ for _ in ()).throw(safrs_api.FRSValidationError("bad")))
    monkeypatch.setattr(builtins, "exit", lambda *_a, **_k: (_ for _ in ()).throw(SystemExit()))
    with pytest.raises(SystemExit):
        safrs_api.SAFRSAPI._add_oas_resource_definitions(api_like, DummyResource, {})


def test_expose_als_schema_yaml_branch(app):
    captured = {}

    class DummyRel:
        target = SimpleNamespace(key="Books")
        _calculated_foreign_keys = [SimpleNamespace(key="book_id")]
        direction = safrs_api.MANYTOONE

    dummy_resource = SimpleNamespace(
        _s_type="Dummy",
        _s_jsonapi_attrs={"name": object()},
        _s_relationships={"books": DummyRel()},
        _s_collection_name="Dummies",
    )
    api_like = SimpleNamespace(
        _als_resources=[dummy_resource],
        add_resource=lambda cls, loc: captured.update({"cls": cls, "loc": loc}),
    )
    result_json = safrs_api.SAFRSAPI.expose_als_schema(api_like, api_root="/api", schema_loc="/als_schema")
    assert '"Dummies"' in result_json
    assert captured["loc"] == "/als_schema"

    with app.test_request_context("/als_schema?yaml=1"):
        yaml_resp = captured["cls"]().get()
        assert isinstance(yaml_resp, Response)
        assert yaml_resp.content_type == "text/yaml"

    with app.test_request_context("/als_schema"):
        plain = captured["cls"]().get()
        assert "resources" in plain


def test_api_decorator_and_http_method_decorator_branches(app, monkeypatch):
    cors_calls = {"count": 0}
    monkeypatch.setattr(safrs_api, "get_config", lambda key: "http://x" if key == "cors_domain" else None)
    monkeypatch.setattr(
        safrs_api.cors,
        "crossdomain",
        lambda origin=None: (lambda f: cors_calls.__setitem__("count", cors_calls["count"] + 1) or f),
    )

    class DummySAFRSObject:
        custom_decorators = []
        decorators = []

        @staticmethod
        def get(*_a, **_k):
            return {"ok": True}

    class DummyAPI:
        SAFRSObject = DummySAFRSObject

        def get(self):
            return {"fallback": True}

    decorated = safrs_api.api_decorator(DummyAPI, lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("swagger boom")))
    assert "get" in decorated.http_methods
    assert cors_calls["count"] > 0

    abort_calls = []

    def fake_abort(status_code, errors=None):
        abort_calls.append((status_code, errors))
        raise RuntimeError("aborted")

    monkeypatch.setattr(safrs_api, "abort", fake_abort)
    monkeypatch.setattr(safrs, "DB", SimpleNamespace(session=SimpleNamespace(commit=lambda: None, rollback=lambda: None)))

    def get(*_a, **_k):
        raise werkzeug.exceptions.BadRequest("bad request")

    wrapped_http = safrs_api.http_method_decorator(get)
    with app.test_request_context("/", method="GET"):
        with pytest.raises(RuntimeError):
            wrapped_http()
    assert abort_calls[-1][0] == 400

    old_level = safrs.log.level
    safrs.log.setLevel(50)

    def get(*_a, **_k):
        raise RuntimeError("secret")

    wrapped_generic = safrs_api.http_method_decorator(get)
    with app.test_request_context("/", method="GET"):
        with pytest.raises(RuntimeError):
            wrapped_generic()
    assert abort_calls[-1][1][0]["title"] == "Logging Disabled"
    safrs.log.setLevel(old_level)


def test_http_method_decorator_request_uow_commit_and_opt_out(app, monkeypatch):
    calls = {"commit": 0, "rollback": 0}

    class Session:
        def commit(self):
            calls["commit"] += 1

        def rollback(self):
            calls["rollback"] += 1

    monkeypatch.setattr(safrs, "DB", SimpleNamespace(session=Session()))

    class CommitModel:
        db_commit = True

    class NoCommitModel:
        db_commit = False

    def get(*_a, **_k):
        safrs_tx.note_write(CommitModel)
        return {"ok": True}

    wrapped_commit = safrs_api.http_method_decorator(get)
    with app.test_request_context("/", method="POST", headers={"Content-Type": "application/vnd.api+json"}):
        assert wrapped_commit() == {"ok": True}
    assert calls["commit"] == 1
    assert calls["rollback"] == 0

    def get_no_commit(*_a, **_k):
        safrs_tx.note_write(NoCommitModel)
        return {"ok": True}

    wrapped_no_commit = safrs_api.http_method_decorator(get_no_commit)
    with app.test_request_context("/", method="POST", headers={"Content-Type": "application/vnd.api+json"}):
        assert wrapped_no_commit() == {"ok": True}
    assert calls["commit"] == 1
    assert calls["rollback"] == 1

    def get(*_a, **_k):
        return {"ok": True}

    wrapped_read = safrs_api.http_method_decorator(get)
    with app.test_request_context("/", method="GET"):
        assert wrapped_read() == {"ok": True}
    assert calls["commit"] == 1
    assert calls["rollback"] == 2


def test_http_method_decorator_relationship_notes_parent_and_target(app, monkeypatch):
    calls = {"commit": 0, "rollback": 0}

    class Session:
        def commit(self):
            calls["commit"] += 1

        def rollback(self):
            calls["rollback"] += 1

    monkeypatch.setattr(safrs, "DB", SimpleNamespace(session=Session()))

    class ParentCommit:
        db_commit = True

    class TargetCommit:
        db_commit = True

    class ParentNoCommit:
        db_commit = False

    class RelWrapperCommit:
        parent = ParentCommit
        _target = TargetCommit

    class RelWrapperNoCommit:
        parent = ParentNoCommit
        _target = TargetCommit

    def handler(*_a, **_k):
        return {"ok": True}

    wrapped = safrs_api.http_method_decorator(handler)

    with app.test_request_context("/", method="POST", headers={"Content-Type": "application/vnd.api+json"}):
        assert wrapped(SimpleNamespace(SAFRSObject=RelWrapperCommit)) == {"ok": True}
    assert calls["commit"] == 1
    assert calls["rollback"] == 0

    with app.test_request_context("/", method="POST", headers={"Content-Type": "application/vnd.api+json"}):
        assert wrapped(SimpleNamespace(SAFRSObject=RelWrapperNoCommit)) == {"ok": True}
    assert calls["commit"] == 1
    assert calls["rollback"] == 1
