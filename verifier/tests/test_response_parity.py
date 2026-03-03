from __future__ import annotations

import difflib
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from safrs_verify.artifacts import cleanup_artifacts, create_artifact_bundle
from safrs_verify.config import ContractTarget, default_contract_targets
from safrs_verify.runner import AppRunner


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class _ParityRequest:
    path: str
    method: str = "GET"
    body: Any = None
    preserve_data_order: bool = False


DEFAULT_PARITY_REQUESTS: tuple[_ParityRequest, ...] = (
    _ParityRequest("/api/Order?page[offset]=0&page[limit]=1&include=Customer,Employee"),
    _ParityRequest("/api/Order?page[number]=2&page[size]=5"),
    _ParityRequest("/api/Order?sort=CustomerId,-OrderDate&page[offset]=0&page[limit]=10", preserve_data_order=True),
    _ParityRequest("/api/Product?filter[CategoryId]=1,2&page[offset]=0&page[limit]=50"),
    _ParityRequest("/api/Product?fields[Product]=ProductName,UnitPrice&page[offset]=0&page[limit]=5"),
    _ParityRequest("/api/Order/{seed:OrderId}?include=Customer,OrderDetailList"),
    _ParityRequest("/api/Order/{seed:OrderId}/OrderDetailList?page[offset]=0&page[limit]=5"),
    _ParityRequest(
        "/api/Order/{seed:OrderId}/OrderDetailList",
        method="PATCH",
        body={},
    ),
    _ParityRequest("/api/Order?include=InvalidRelationship&page[offset]=0&page[limit]=1"),
)


@dataclass(frozen=True)
class _PairCase:
    name: str
    left: ContractTarget
    right: ContractTarget
    requests: tuple[_ParityRequest, ...]


def _request_case_from_raw(raw: Any) -> _ParityRequest:
    if isinstance(raw, _ParityRequest):
        return raw
    if isinstance(raw, str):
        path = raw.strip()
        if not path:
            raise AssertionError("Request path must be non-empty")
        return _ParityRequest(path=path)
    if not isinstance(raw, dict):
        raise AssertionError("Request entries must be strings or objects with at least a 'path' field")

    path = str(raw.get("path", "")).strip()
    if not path:
        raise AssertionError("Request object must include non-empty 'path'")
    method = str(raw.get("method", "GET")).strip().upper() or "GET"
    body = raw.get("body")
    preserve_data_order = bool(raw.get("preserve_data_order", False))
    if not preserve_data_order:
        parsed = urlsplit(path)
        preserve_data_order = "sort" in parse_qs(parsed.query, keep_blank_values=True)
    return _ParityRequest(
        path=path,
        method=method,
        body=body,
        preserve_data_order=preserve_data_order,
    )


def _parse_requests(raw: str) -> tuple[_ParityRequest, ...]:
    value = str(raw or "").strip()
    if not value:
        return ()

    # Preferred: JSON array for multiple requests.
    if value.startswith("["):
        parsed = json.loads(value)
        if not isinstance(parsed, list):
            raise AssertionError("SAFRS_PARITY_REQUESTS JSON value must be a list")
        result = tuple(_request_case_from_raw(item) for item in parsed)
        if not result:
            raise AssertionError("SAFRS_PARITY_REQUESTS parsed to an empty request list")
        return result

    # Also support newline-separated requests.
    if "\n" in value:
        result = tuple(_request_case_from_raw(part.strip()) for part in value.splitlines() if part.strip())
        if not result:
            raise AssertionError("SAFRS_PARITY_REQUESTS parsed to an empty request list")
        return result

    # Legacy alternate separator for multiple requests.
    if "||" in value:
        result = tuple(_request_case_from_raw(part.strip()) for part in value.split("||") if part.strip())
        if not result:
            raise AssertionError("SAFRS_PARITY_REQUESTS parsed to an empty request list")
        return result

    # Default: single request string (commas are valid inside query parameters).
    return (_request_case_from_raw(value),)


def _normalize_unordered(
    value: Any,
    *,
    preserve_data_order: bool = False,
    path: tuple[str, ...] = (),
) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _normalize_unordered(
                item,
                preserve_data_order=preserve_data_order,
                path=path + (str(key),),
            )
            for key, item in sorted(value.items(), key=lambda kv: str(kv[0]))
        }
    if isinstance(value, list):
        normalized = [
            _normalize_unordered(item, preserve_data_order=preserve_data_order, path=path)
            for item in value
        ]
        parent_key = path[-1] if path else ""
        if parent_key == "included":
            normalized.sort(
                key=lambda item: (
                    str(item.get("type", "")) if isinstance(item, dict) else "",
                    str(item.get("id", "")) if isinstance(item, dict) else "",
                    json.dumps(item, sort_keys=True, separators=(",", ":")),
                )
            )
            return normalized
        if parent_key == "data" and preserve_data_order:
            return normalized
        normalized.sort(key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
        return normalized
    return value


def _pretty(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)


def _diff_json(left: Any, right: Any) -> str:
    left_lines = _pretty(left).splitlines()
    right_lines = _pretty(right).splitlines()
    return "\n".join(
        difflib.unified_diff(
            left_lines,
            right_lines,
            fromfile="flask(normalized)",
            tofile="fastapi(normalized)",
            lineterm="",
        )
    )


def _resolve_pair_case() -> _PairCase:
    targets = {target.name: target for target in default_contract_targets(PROJECT_ROOT)}
    pair_csv = os.environ.get("SAFRS_PARITY_TARGETS", "nw-flask,nw-fastapi")
    pair_names = [part.strip() for part in pair_csv.split(",") if part.strip()]
    if len(pair_names) != 2:
        raise AssertionError("SAFRS_PARITY_TARGETS must contain exactly 2 target names, e.g. 'nw-flask,nw-fastapi'")

    left_name, right_name = pair_names
    if left_name not in targets:
        raise AssertionError(f"Unknown parity left target: {left_name!r}")
    if right_name not in targets:
        raise AssertionError(f"Unknown parity right target: {right_name!r}")

    request_csv = os.environ.get("SAFRS_PARITY_REQUESTS", "").strip()
    if request_csv:
        request_paths = _parse_requests(request_csv)
    else:
        request_paths = DEFAULT_PARITY_REQUESTS

    return _PairCase(
        name=f"{left_name} vs {right_name}",
        left=targets[left_name],
        right=targets[right_name],
        requests=request_paths,
    )


def _resolve_seed_value(seed_payload: dict[str, Any], key: str) -> Any:
    if key in seed_payload:
        return seed_payload[key]
    current: Any = seed_payload
    for part in key.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(key)
        current = current[part]
    return current


def _resolve_seed_placeholders(path_and_query: str, seed_payload: dict[str, Any]) -> str:
    request_path = str(path_and_query)
    while "{seed:" in request_path:
        start = request_path.index("{seed:")
        end = request_path.find("}", start)
        if end < 0:
            raise AssertionError(f"Invalid seed placeholder syntax in request path: {path_and_query}")
        token = request_path[start : end + 1]
        seed_key = token[len("{seed:") : -1].strip()
        if not seed_key:
            raise AssertionError(f"Empty seed placeholder in request path: {path_and_query}")
        try:
            seed_value = _resolve_seed_value(seed_payload, seed_key)
        except KeyError as exc:
            raise AssertionError(f"Missing seed key '{seed_key}' required by request path '{path_and_query}'") from exc
        request_path = request_path.replace(token, str(seed_value), 1)
    return request_path


def _request_json(base_url: str, request_case: _ParityRequest) -> tuple[int, Any, str]:
    request_path = str(request_case.path).strip()
    if not request_path.startswith("/"):
        request_path = "/" + request_path
    headers = {"Accept": "application/vnd.api+json"}
    method = str(request_case.method).upper()
    if method in {"POST", "PATCH", "PUT", "DELETE"} or request_case.body is not None:
        headers["Content-Type"] = "application/vnd.api+json"

    response = requests.request(
        method=method,
        url=base_url.rstrip("/") + request_path,
        json=request_case.body,
        headers=headers,
        timeout=20,
    )
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type and "application/vnd.api+json" not in content_type:
        return response.status_code, response.text, content_type
    try:
        return response.status_code, response.json(), content_type
    except Exception:
        return response.status_code, response.text, content_type


def _error_status_codes(body: Any) -> tuple[str, ...]:
    if not isinstance(body, dict):
        return ()
    errors = body.get("errors")
    if not isinstance(errors, list):
        return ()
    statuses: list[str] = []
    for item in errors:
        if not isinstance(item, dict):
            continue
        raw_status = item.get("status", item.get("code", ""))
        statuses.append(str(raw_status))
    return tuple(statuses)


@pytest.mark.parity
@pytest.mark.slow
def test_jsonapi_response_parity_order_insensitive() -> None:
    case = _resolve_pair_case()
    left_bundle = create_artifact_bundle("parity_resp_left_" + uuid.uuid4().hex[:8])
    right_bundle = create_artifact_bundle("parity_resp_right_" + uuid.uuid4().hex[:8])
    keep = os.environ.get("SAFRS_VERIFY_KEEP_ARTIFACTS", "1").strip() == "1"

    left_runner: AppRunner | None = None
    right_runner: AppRunner | None = None
    try:
        left_runner = AppRunner(
            app_path=case.left.app_path,
            health_path=case.left.health_path,
            env=dict(case.left.env),
            app_log_file=left_bundle.directory / "app.log",
        )
        right_runner = AppRunner(
            app_path=case.right.app_path,
            health_path=case.right.health_path,
            env=dict(case.right.env),
            app_log_file=right_bundle.directory / "app.log",
        )
        left_base_url = left_runner.start()
        right_base_url = right_runner.start()

        seed_status, seed_body, _seed_content_type = _request_json(left_base_url, _ParityRequest(path="/seed"))
        seed_payload: dict[str, Any] = seed_body if seed_status == 200 and isinstance(seed_body, dict) else {}

        for request_case in case.requests:
            resolved_path = _resolve_seed_placeholders(request_case.path, seed_payload)
            resolved_case = _ParityRequest(
                path=resolved_path,
                method=request_case.method,
                body=request_case.body,
                preserve_data_order=request_case.preserve_data_order,
            )

            left_status, left_body, left_content_type = _request_json(left_base_url, resolved_case)
            right_status, right_body, right_content_type = _request_json(right_base_url, resolved_case)

            assert left_status == right_status, "\n".join(
                [
                    f"Parity status mismatch for {resolved_case.method} {resolved_path}",
                    f"pair={case.name}",
                    f"left_status={left_status}",
                    f"right_status={right_status}",
                    f"left_content_type={left_content_type}",
                    f"right_content_type={right_content_type}",
                    f"left_base_url={left_base_url}",
                    f"right_base_url={right_base_url}",
                    "left_body:\n" + _pretty(left_body),
                    "right_body:\n" + _pretty(right_body),
                ]
            )

            if left_status >= 400:
                left_error_codes = _error_status_codes(left_body)
                right_error_codes = _error_status_codes(right_body)
                assert left_error_codes == right_error_codes, "\n".join(
                    [
                        f"Parity error-code mismatch for {resolved_case.method} {resolved_path}",
                        f"pair={case.name}",
                        f"left_error_codes={left_error_codes}",
                        f"right_error_codes={right_error_codes}",
                        "left_body:\n" + _pretty(left_body),
                        "right_body:\n" + _pretty(right_body),
                    ]
                )
                continue

            left_normalized = _normalize_unordered(
                left_body,
                preserve_data_order=resolved_case.preserve_data_order,
            )
            right_normalized = _normalize_unordered(
                right_body,
                preserve_data_order=resolved_case.preserve_data_order,
            )
            assert left_normalized == right_normalized, "\n".join(
                [
                    f"Parity payload mismatch for {resolved_case.method} {resolved_path}",
                    f"pair={case.name}",
                    f"left_base_url={left_base_url}",
                    f"right_base_url={right_base_url}",
                    _diff_json(left_normalized, right_normalized),
                ]
            )
    finally:
        if left_runner is not None:
            left_runner.stop()
        if right_runner is not None:
            right_runner.stop()
        if not keep:
            cleanup_artifacts(left_bundle)
            cleanup_artifacts(right_bundle)


def test_parse_requests_single_path_with_query_commas() -> None:
    value = "/api/Order?page[offset]=0&page[limit]=1&include=Customer,Employee"
    assert _parse_requests(value) == (_ParityRequest(path=value),)


def test_parse_requests_from_json_array() -> None:
    value = '["/api/Order?page[offset]=0&page[limit]=1", "/api/Customer?page[offset]=0&page[limit]=1"]'
    assert _parse_requests(value) == (
        _ParityRequest(path="/api/Order?page[offset]=0&page[limit]=1"),
        _ParityRequest(path="/api/Customer?page[offset]=0&page[limit]=1"),
    )


def test_parse_requests_from_newlines() -> None:
    value = "/api/Order?page[offset]=0&page[limit]=1\n/api/Customer?page[offset]=0&page[limit]=1"
    assert _parse_requests(value) == (
        _ParityRequest(path="/api/Order?page[offset]=0&page[limit]=1"),
        _ParityRequest(path="/api/Customer?page[offset]=0&page[limit]=1"),
    )


def test_parse_requests_from_json_objects() -> None:
    value = '[{"method":"PATCH","path":"/api/Order/1/OrderDetailList","body":{}},{"path":"/api/Order?sort=Id"}]'
    assert _parse_requests(value) == (
        _ParityRequest(path="/api/Order/1/OrderDetailList", method="PATCH", body={}, preserve_data_order=False),
        _ParityRequest(path="/api/Order?sort=Id", method="GET", body=None, preserve_data_order=True),
    )


def test_resolve_seed_placeholders() -> None:
    seed = {"OrderId": "10248", "nested": {"BookId": "1"}}
    assert _resolve_seed_placeholders("/api/Order/{seed:OrderId}", seed) == "/api/Order/10248"
    assert _resolve_seed_placeholders("/api/Books/{seed:nested.BookId}", seed) == "/api/Books/1"


def test_error_status_codes_extracts_status_and_code_fields() -> None:
    assert _error_status_codes({"errors": [{"status": "400"}, {"code": "409"}]}) == ("400", "409")
