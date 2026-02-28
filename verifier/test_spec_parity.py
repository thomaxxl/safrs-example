from __future__ import annotations

import uuid
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from safrs.fastapi.openapi import diff_openapi_documents
from safrs_verify.config import default_contract_targets
from safrs_verify.db.sqlite import SQLiteBackend
from safrs_verify.runner import AppRunner
from safrs_verify.spec import discover_spec


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parity
@pytest.mark.slow
def test_runtime_swagger2_openapi3_parity() -> None:
    targets = {target.name: target for target in default_contract_targets(PROJECT_ROOT)}
    flask_target = targets["tmp-flask"]
    fastapi_target = targets["tmp-fastapi"]

    backend = SQLiteBackend()
    flask_run_id = "parity_flask_" + uuid.uuid4().hex[:8]
    fastapi_run_id = "parity_fastapi_" + uuid.uuid4().hex[:8]

    flask_env = backend.provision(flask_run_id)
    fastapi_env = backend.provision(fastapi_run_id)

    flask_spec: dict[str, object]
    fastapi_spec: dict[str, object]
    try:
        try:
            with AppRunner(
                app_path=flask_target.app_path,
                health_path=flask_target.health_path,
                env={**dict(flask_target.env), **flask_env},
            ) as runner:
                fetched = discover_spec(runner.base_url or "", candidates=flask_target.spec_candidates)
                flask_spec = fetched.spec

            with AppRunner(
                app_path=fastapi_target.app_path,
                health_path=fastapi_target.health_path,
                env={**dict(fastapi_target.env), **fastapi_env},
            ) as runner:
                fetched = discover_spec(runner.base_url or "", candidates=fastapi_target.spec_candidates)
                fastapi_spec = fetched.spec
        except PermissionError as exc:
            pytest.skip(f"local socket binding not permitted in this environment: {exc}")
    finally:
        backend.cleanup(flask_run_id)
        backend.cleanup(fastapi_run_id)

    assert str(flask_spec.get("swagger", "")) == "2.0"
    assert "openapi" in fastapi_spec

    report = diff_openapi_documents(flask_spec, fastapi_spec)
    assert report["missing_operations"] == []
    assert report["missing_tags"] == []
    assert report["missing_request_body"] == []
