from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from . import _legacy_patch_impl as legacy

DEFAULT_COLLECTION_ID_KEYS: dict[str, str] = {
    "People": "PersonId",
    "Books": "BookId",
    "Publishers": "PublisherId",
    "Reviews": "ReviewId",
}


def _relationship_target_type(schema: dict[str, Any], *, to_many: bool) -> str:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return ""
    data = properties.get("data")
    if not isinstance(data, dict):
        return ""

    ref_name = ""
    if to_many:
        items = data.get("items")
        if isinstance(items, dict):
            ref_name = str(items.get("$ref", ""))
    else:
        any_of = data.get("anyOf")
        if isinstance(any_of, list):
            for variant in any_of:
                if not isinstance(variant, dict):
                    continue
                ref_name = str(variant.get("$ref", ""))
                if ref_name:
                    break

    prefix = "#/components/schemas/"
    suffix = "ResourceIdentifier"
    if not ref_name.startswith(prefix):
        return ""
    token = ref_name[len(prefix) :]
    if not token.endswith(suffix):
        return ""
    return token[: -len(suffix)]


def _add_openapi_component_aliases(spec: dict[str, Any]) -> None:
    if "openapi" not in spec:
        return

    components = spec.get("components")
    if not isinstance(components, dict):
        return
    schemas = components.get("schemas")
    if not isinstance(schemas, dict):
        return

    for schema_name in sorted(list(schemas)):
        if not isinstance(schema_name, str):
            continue
        if not schema_name.endswith("DocumentSingle"):
            continue
        payload = schemas.get(schema_name)
        if not isinstance(payload, dict):
            continue
        base_name = schema_name[: -len("DocumentSingle")]
        for suffix in ("DocumentCreate", "DocumentPatch"):
            alias = base_name + suffix
            if alias not in schemas:
                schemas[alias] = copy.deepcopy(payload)

    for schema_name in sorted(list(schemas)):
        payload = schemas.get(schema_name)
        if not isinstance(schema_name, str) or not isinstance(payload, dict):
            continue
        if schema_name.endswith("RelationshipToMany"):
            target_type = _relationship_target_type(payload, to_many=True)
            if target_type:
                alias = f"{target_type}RelationshipDocumentToMany"
                if alias not in schemas:
                    schemas[alias] = copy.deepcopy(payload)
            continue
        if schema_name.endswith("RelationshipToOne"):
            target_type = _relationship_target_type(payload, to_many=False)
            if target_type:
                alias = f"{target_type}RelationshipDocumentToOne"
                if alias not in schemas:
                    schemas[alias] = copy.deepcopy(payload)


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
    spec_with_aliases = copy.deepcopy(spec)
    _add_openapi_component_aliases(spec_with_aliases)
    merged_keys = _merged_collection_id_keys(seed, collection_id_key_overrides)
    previous_keys = dict(getattr(legacy, "_COLLECTION_TO_SEED_ID_KEY", {}))
    try:
        legacy._COLLECTION_TO_SEED_ID_KEY = merged_keys
        return legacy._patch_spec_with_seed(spec_with_aliases, seed)
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
    os.close(fd)
    Path(tmp_path).write_text(json.dumps(patched), encoding="utf-8")
    return Path(tmp_path), True
