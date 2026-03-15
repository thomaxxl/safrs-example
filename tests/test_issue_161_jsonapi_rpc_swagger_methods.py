"""Regression tests for GitHub issue #161.

Issue: A method exposed via @jsonapi_rpc(http_methods=[...]) should only show
those HTTP methods in the generated OpenAPI/Swagger spec.

See: https://github.com/thomaxxl/safrs/issues/161
"""

from __future__ import annotations

from flask import Flask

import safrs
from safrs import SAFRSAPI
from safrs.swagger_doc import jsonapi_rpc


def _make_api() -> tuple[Flask, SAFRSAPI]:
    """Create a minimal SAFRSAPI instance backed by an in-memory sqlite DB."""
    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TESTING=True,
    )
    safrs.DB.init_app(app)

    with app.app_context():
        api = SAFRSAPI(app, host="localhost", port=5000, prefix="", swaggerui_blueprint=False)

    return app, api


def _get_path_ops(api: SAFRSAPI, suffix: str) -> dict[str, dict]:
    """Return {path: ops} entries whose path endswith `suffix`."""
    spec = api.get_swagger_doc()
    return {p: ops for p, ops in spec.get("paths", {}).items() if p.endswith(suffix)}


def test_issue_161_classmethod_rpc_only_post_in_swagger() -> None:
    """A classmethod jsonapi_rpc(http_methods=['POST']) must only document POST."""
    app, api = _make_api()

    class ServicesEndPoint(safrs.JABase):
        @classmethod
        @jsonapi_rpc(http_methods=["POST"])
        def myFunction(cls, *args, **kwargs):
            return {"ok": True}

    with app.app_context():
        api.expose_object(ServicesEndPoint)
        paths = _get_path_ops(api, "/myFunction")

    # Two paths may end with /myFunction (instance + class). We specifically
    # want the classmethod path without an instance id.
    class_paths = {p: ops for p, ops in paths.items() if "{" not in p}
    assert class_paths, f"No classmethod myFunction path found in swagger: {list(paths)}"
    assert set(next(iter(class_paths.values())).keys()) == {"post"}


def test_issue_161_instance_method_rpc_only_post_in_swagger() -> None:
    """An instance jsonapi_rpc(http_methods=['POST']) must only document POST."""
    app, api = _make_api()

    class ServicesEndPoint(safrs.JABase):
        @jsonapi_rpc(http_methods=["POST"])
        def myFunction(self, *args, **kwargs):
            return {"ok": True}

    with app.app_context():
        api.expose_object(ServicesEndPoint)
        paths = _get_path_ops(api, "/myFunction")

    inst_paths = {p: ops for p, ops in paths.items() if "{" in p}
    assert inst_paths, f"No instance myFunction path found in swagger: {list(paths)}"
    assert set(next(iter(inst_paths.values())).keys()) == {"post"}


def test_issue_161_rpc_multiple_http_methods_are_documented() -> None:
    """If a jsonapi_rpc is configured for GET+POST, swagger must show both."""
    app, api = _make_api()

    class ServicesEndPoint(safrs.JABase):
        @classmethod
        @jsonapi_rpc(http_methods=["GET", "POST"])
        def myFunction(cls, *args, **kwargs):
            return {"ok": True}

    with app.app_context():
        api.expose_object(ServicesEndPoint)
        paths = _get_path_ops(api, "/myFunction")
        class_paths = {p: ops for p, ops in paths.items() if "{" not in p}

    assert class_paths, f"No classmethod myFunction path found in swagger: {list(paths)}"
    assert set(next(iter(class_paths.values())).keys()) == {"get", "post"}
