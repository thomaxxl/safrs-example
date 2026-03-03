from __future__ import annotations

import difflib
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import requests

from safrs_verify.artifacts import cleanup_artifacts, create_artifact_bundle
from safrs_verify.config import ContractTarget, default_contract_targets
from safrs_verify.runner import AppRunner


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARITY_REQUESTS: tuple[str, ...] = (
    "/api/Order?page[offset]=0&page[limit]=1&include=Customer,Employee",
)


@dataclass(frozen=True)
class _PairCase:
    name: str
    left: ContractTarget
    right: ContractTarget
    requests: tuple[str, ...]


def _parse_request_paths(raw: str) -> tuple[str, ...]:
    value = str(raw or "").strip()
    if not value:
        return ()

    # Preferred: JSON array for multiple requests.
    if value.startswith("["):
        parsed = json.loads(value)
        if not isinstance(parsed, list):
            raise AssertionError("SAFRS_PARITY_REQUESTS JSON value must be a list of request paths")
        result = tuple(str(item).strip() for item in parsed if str(item).strip())
        if not result:
            raise AssertionError("SAFRS_PARITY_REQUESTS parsed to an empty request list")
        return result

    # Also support newline-separated requests.
    if "\n" in value:
        result = tuple(part.strip() for part in value.splitlines() if part.strip())
        if not result:
            raise AssertionError("SAFRS_PARITY_REQUESTS parsed to an empty request list")
        return result

    # Legacy alternate separator for multiple requests.
    if "||" in value:
        result = tuple(part.strip() for part in value.split("||") if part.strip())
        if not result:
            raise AssertionError("SAFRS_PARITY_REQUESTS parsed to an empty request list")
        return result

    # Default: single request string (commas are valid inside query parameters).
    return (value,)


def _normalize_unordered(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize_unordered(item) for key, item in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, list):
        normalized = [_normalize_unordered(item) for item in value]
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
        request_paths = _parse_request_paths(request_csv)
    else:
        request_paths = DEFAULT_PARITY_REQUESTS

    return _PairCase(
        name=f"{left_name} vs {right_name}",
        left=targets[left_name],
        right=targets[right_name],
        requests=request_paths,
    )


def _get_json(base_url: str, path_and_query: str) -> tuple[int, Any, str]:
    request_path = str(path_and_query).strip()
    if not request_path.startswith("/"):
        request_path = "/" + request_path
    response = requests.get(base_url.rstrip("/") + request_path, timeout=20)
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type and "application/vnd.api+json" not in content_type:
        return response.status_code, response.text, content_type
    try:
        return response.status_code, response.json(), content_type
    except Exception:
        return response.status_code, response.text, content_type


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

        for path_and_query in case.requests:
            left_status, left_body, left_content_type = _get_json(left_base_url, path_and_query)
            right_status, right_body, right_content_type = _get_json(right_base_url, path_and_query)

            assert left_status == right_status, "\n".join(
                [
                    f"Parity status mismatch for {path_and_query}",
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

            left_normalized = _normalize_unordered(left_body)
            right_normalized = _normalize_unordered(right_body)
            assert left_normalized == right_normalized, "\n".join(
                [
                    f"Parity payload mismatch for {path_and_query}",
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


def test_parse_request_paths_single_path_with_query_commas() -> None:
    value = "/api/Order?page[offset]=0&page[limit]=1&include=Customer,Employee"
    assert _parse_request_paths(value) == (value,)


def test_parse_request_paths_from_json_array() -> None:
    value = '["/api/Order?page[offset]=0&page[limit]=1", "/api/Customer?page[offset]=0&page[limit]=1"]'
    assert _parse_request_paths(value) == (
        "/api/Order?page[offset]=0&page[limit]=1",
        "/api/Customer?page[offset]=0&page[limit]=1",
    )


def test_parse_request_paths_from_newlines() -> None:
    value = "/api/Order?page[offset]=0&page[limit]=1\n/api/Customer?page[offset]=0&page[limit]=1"
    assert _parse_request_paths(value) == (
        "/api/Order?page[offset]=0&page[limit]=1",
        "/api/Customer?page[offset]=0&page[limit]=1",
    )
