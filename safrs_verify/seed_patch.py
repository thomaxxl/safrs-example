from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Mapping

from . import verify_openapi_contract as legacy

DEFAULT_COLLECTION_ID_KEYS: dict[str, str] = {
    "People": "PersonId",
    "Books": "BookId",
    "Publishers": "PublisherId",
    "Reviews": "ReviewId",
}


def fetch_seed_payload(base_url: str, request_timeout_s: float, seed_path: str = "/seed") -> dict[str, Any]:
    try:
        import requests
    except Exception:
        return {}

    timeout_s = max(0.5, min(float(request_timeout_s), 5.0))
    seed_url = base_url.rstrip("/") + seed_path
    try:
        response = requests.get(seed_url, timeout=timeout_s)
        if response.status_code >= 400:
            return {}
        payload = response.json()
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _merged_collection_id_keys(
    seed: Mapping[str, Any],
    overrides: Mapping[str, str] | None,
) -> dict[str, str]:
    merged = dict(DEFAULT_COLLECTION_ID_KEYS)
    if overrides:
        merged.update({str(key): str(value) for key, value in overrides.items() if str(key) and str(value)})
    seed_keys = seed.get("collection_id_keys")
    if isinstance(seed_keys, dict):
        merged.update({str(key): str(value) for key, value in seed_keys.items() if str(key) and str(value)})
    return merged


def patch_spec_with_seed(
    spec: dict[str, Any],
    seed: dict[str, Any],
    *,
    collection_id_key_overrides: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    merged_keys = _merged_collection_id_keys(seed, collection_id_key_overrides)
    previous_keys = dict(getattr(legacy, "_COLLECTION_TO_SEED_ID_KEY", {}))
    try:
        legacy._COLLECTION_TO_SEED_ID_KEY = merged_keys
        return legacy._patch_spec_with_seed(spec, seed)
    finally:
        legacy._COLLECTION_TO_SEED_ID_KEY = previous_keys


def prepare_spec_for_run(
    spec_path: Path,
    base_url: str,
    request_timeout_s: float,
    *,
    seed_path: str = "/seed",
    collection_id_key_overrides: Mapping[str, str] | None = None,
) -> tuple[Path, bool]:
    seed = fetch_seed_payload(base_url, request_timeout_s, seed_path=seed_path)
    if not seed:
        return spec_path, False

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    patched = patch_spec_with_seed(spec, seed, collection_id_key_overrides=collection_id_key_overrides)
    fd, tmp_path = tempfile.mkstemp(prefix="safrs_contract_spec_", suffix=".json")
    Path(tmp_path).write_text(json.dumps(patched), encoding="utf-8")
    return Path(tmp_path), True
