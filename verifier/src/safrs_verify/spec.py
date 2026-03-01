from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


class SpecDiscoveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class FetchedSpec:
    spec: dict[str, object]
    endpoint: str
    status_code: int


@dataclass(frozen=True)
class SpecDiscoveryResult:
    fetched: FetchedSpec
    effective_url: str


def extract_base_path_from_spec(spec: dict[str, object]) -> str:
    if str(spec.get("swagger", "")) == "2.0":
        base_path = spec.get("basePath", "")
        return base_path if isinstance(base_path, str) else ""

    if "openapi" in spec:
        servers = spec.get("servers")
        if isinstance(servers, list) and servers:
            first = servers[0]
            if isinstance(first, dict):
                server_url = first.get("url", "")
                if isinstance(server_url, str) and server_url:
                    if server_url.startswith("/"):
                        return server_url
                    if server_url.startswith("http://") or server_url.startswith("https://"):
                        parsed = urlparse(server_url)
                        return parsed.path or ""
    return ""


def join_base_url(base_url: str, base_path: str) -> str:
    if not base_path or base_path == "/":
        return base_url.rstrip("/")
    return base_url.rstrip("/") + "/" + base_path.lstrip("/")


def discover_spec(
    base_url: str,
    candidates: tuple[str, ...] = ("/openapi.json", "/api/swagger.json"),
    request_timeout_s: float = 5.0,
) -> FetchedSpec:
    try:
        import requests
    except Exception as exc:
        raise SpecDiscoveryError("Missing dependency 'requests' (pip install requests)") from exc

    attempts: list[str] = []
    for endpoint in candidates:
        url = base_url.rstrip("/") + endpoint
        try:
            response = requests.get(url, timeout=request_timeout_s)
        except Exception as exc:
            attempts.append(f"{endpoint}: request error {exc!r}")
            continue

        if response.status_code >= 400:
            snippet = (response.text or "")[:160].replace("\n", " ").strip()
            attempts.append(f"{endpoint}: HTTP {response.status_code} {snippet}")
            continue

        try:
            payload = response.json()
        except Exception as exc:
            attempts.append(f"{endpoint}: invalid JSON ({exc!r})")
            continue

        if not isinstance(payload, dict):
            attempts.append(f"{endpoint}: top-level JSON is not an object")
            continue

        if endpoint.endswith("/openapi.json") and "openapi" in payload:
            return FetchedSpec(spec=payload, endpoint=endpoint, status_code=response.status_code)
        if endpoint.endswith("/swagger.json") and str(payload.get("swagger", "")) == "2.0":
            return FetchedSpec(spec=payload, endpoint=endpoint, status_code=response.status_code)

        if "openapi" in payload or str(payload.get("swagger", "")) == "2.0":
            return FetchedSpec(spec=payload, endpoint=endpoint, status_code=response.status_code)

        attempts.append(f"{endpoint}: JSON is present but not Swagger2/OpenAPI3")

    joined_attempts = " | ".join(attempts) if attempts else "<no attempts>"
    raise SpecDiscoveryError(
        "Unable to discover API spec. Tried endpoints: " + joined_attempts
    )


def discover_spec_with_effective_url(
    base_url: str,
    candidates: tuple[str, ...] = ("/openapi.json", "/api/swagger.json"),
    request_timeout_s: float = 5.0,
) -> SpecDiscoveryResult:
    fetched = discover_spec(base_url=base_url, candidates=candidates, request_timeout_s=request_timeout_s)
    effective_url = join_base_url(base_url, extract_base_path_from_spec(fetched.spec))
    return SpecDiscoveryResult(fetched=fetched, effective_url=effective_url)


def write_temp_spec(spec: dict[str, object], *, prefix: str = "safrs_contract_spec_") -> Path:
    fd, tmp_path = tempfile.mkstemp(prefix=prefix, suffix=".json")
    os.close(fd)
    Path(tmp_path).write_text(json.dumps(spec), encoding="utf-8")
    return Path(tmp_path)
