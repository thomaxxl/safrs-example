from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


TMP_DIR = Path(__file__).resolve().parents[1] / "safrs" / "tmp"
if str(TMP_DIR) not in sys.path:
    sys.path.insert(0, str(TMP_DIR))

import verify_openapi_contract as legacy_wrapper


def test_wrapper_patch_spec_with_seed_preserves_legacy_behavior() -> None:
    spec = {
        "swagger": "2.0",
        "paths": {
            "/api/Books/{BookId}": {
                "get": {
                    "parameters": [
                        {"name": "BookId", "in": "path", "type": "string"},
                    ],
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }

    patched = legacy_wrapper._patch_spec_with_seed(spec, {"BookId": "book-1"})
    param = patched["paths"]["/api/Books/{BookId}"]["get"]["parameters"][0]
    assert param["enum"] == ["book-1"]
    assert param["default"] == "book-1"


def test_wrapper_prepare_spec_for_run_uses_monkeypatched_seed_fetch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path = tmp_path / "swagger.json"
    spec_path.write_text(
        json.dumps(
            {
                "swagger": "2.0",
                "paths": {
                    "/api/Books/{BookId}": {
                        "get": {
                            "parameters": [
                                {"name": "BookId", "in": "path", "type": "string"},
                            ],
                            "responses": {"200": {"description": "ok"}},
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(legacy_wrapper, "_fetch_seed_payload", lambda *_a, **_k: {"BookId": "book-seed-42"})
    prepared_path, cleanup = legacy_wrapper._prepare_spec_for_run(spec_path, "http://127.0.0.1:1", 1.0)
    try:
        assert cleanup is True
        assert prepared_path != spec_path
        patched = json.loads(prepared_path.read_text(encoding="utf-8"))
        param = patched["paths"]["/api/Books/{BookId}"]["get"]["parameters"][0]
        assert param["enum"] == ["book-seed-42"]
        assert param["default"] == "book-seed-42"
    finally:
        if cleanup:
            prepared_path.unlink(missing_ok=True)
