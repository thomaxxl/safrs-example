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
    app_dir = repo_root / "apps"
    return (
        ContractTarget(
            name="flask",
            app_path=app_dir / "flask_app.py",
            spec_candidates=("/api/swagger.json", "/openapi.json"),
            env={"SAFRS_EXAMPLE_RESET_DB": "1"},
        ),
        ContractTarget(
            name="fastapi",
            app_path=app_dir / "fastapi_app.py",
            spec_candidates=("/openapi.json", "/api/swagger.json"),
            env={"SAFRS_EXAMPLE_RESET_DB": "1"},
        ),
    )
