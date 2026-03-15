from __future__ import annotations

import sys
import types

import pytest

from safrs_verify.spec import SpecDiscoveryError, discover_spec, extract_base_path_from_spec, join_base_url


class _Response:
    def __init__(self, status_code: int, payload: object, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> object:
        return self._payload


def _patch_requests(monkeypatch: pytest.MonkeyPatch, responder: object) -> None:
    fake_module = types.SimpleNamespace(get=responder)
    monkeypatch.setitem(sys.modules, "requests", fake_module)


def test_discover_spec_prefers_openapi3_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    def responder(url: str, timeout: float) -> _Response:
        assert timeout == 5.0
        if url.endswith("/openapi.json"):
            return _Response(200, {"openapi": "3.1.0", "paths": {}})
        return _Response(404, {}, "missing")

    _patch_requests(monkeypatch, responder)
    fetched = discover_spec("http://127.0.0.1:8000")
    assert fetched.endpoint == "/openapi.json"
    assert fetched.status_code == 200
    assert fetched.spec["openapi"] == "3.1.0"


def test_discover_spec_falls_back_to_swagger(monkeypatch: pytest.MonkeyPatch) -> None:
    def responder(url: str, timeout: float) -> _Response:
        if url.endswith("/openapi.json"):
            return _Response(404, {}, "missing")
        if url.endswith("/api/swagger.json"):
            return _Response(200, {"swagger": "2.0", "paths": {}})
        return _Response(404, {}, "missing")

    _patch_requests(monkeypatch, responder)
    fetched = discover_spec("http://127.0.0.1:5000")
    assert fetched.endpoint == "/api/swagger.json"
    assert fetched.spec["swagger"] == "2.0"


def test_discover_spec_raises_clear_error_when_no_candidate_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    def responder(url: str, timeout: float) -> _Response:
        return _Response(404, {}, "not found")

    _patch_requests(monkeypatch, responder)
    with pytest.raises(SpecDiscoveryError, match="Unable to discover API spec"):
        discover_spec("http://127.0.0.1:6000")


def test_extract_base_path_and_join_url() -> None:
    swagger = {"swagger": "2.0", "basePath": "/api"}
    openapi_relative = {"openapi": "3.1.0", "servers": [{"url": "/v1"}]}
    openapi_absolute = {"openapi": "3.1.0", "servers": [{"url": "http://localhost:1234/api"}]}

    assert extract_base_path_from_spec(swagger) == "/api"
    assert extract_base_path_from_spec(openapi_relative) == "/v1"
    assert extract_base_path_from_spec(openapi_absolute) == "/api"

    assert join_base_url("http://127.0.0.1:5000", "/api") == "http://127.0.0.1:5000/api"
    assert join_base_url("http://127.0.0.1:5000/", "/") == "http://127.0.0.1:5000"
