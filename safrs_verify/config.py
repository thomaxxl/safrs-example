from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class ContractTarget:
    name: str
    app_path: Path
    health_path: str = "/health"
    seed_path: str = "/seed"
    spec_candidates: tuple[str, ...] = ("/openapi.json", "/api/swagger.json")
    app_args: tuple[str, ...] = ()
    env: Mapping[str, str] = field(default_factory=dict)
    collection_id_keys: Mapping[str, str] = field(default_factory=dict)


def default_contract_targets(repo_root: Path) -> tuple[ContractTarget, ...]:
    tmp_dir = repo_root / "safrs" / "tmp"
    return (
        ContractTarget(
            name="tmp-flask",
            app_path=tmp_dir / "flask_app.py",
            spec_candidates=("/api/swagger.json", "/openapi.json"),
            env={"SAFRS_TMP_RESET_DB": "1"},
        ),
        ContractTarget(
            name="tmp-fastapi",
            app_path=tmp_dir / "fastapi_app.py",
            spec_candidates=("/openapi.json", "/api/swagger.json"),
            env={"SAFRS_TMP_RESET_DB": "1"},
        ),
    )
