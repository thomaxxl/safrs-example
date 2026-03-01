from __future__ import annotations

import os
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
    targets = (
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
        ContractTarget(
            name="nw-flask",
            app_path=app_dir / "nw_flask_app.py",
            spec_candidates=("/api/swagger.json", "/openapi.json"),
            env={"SAFRS_NW_RESET_DB": "1"},
            collection_id_keys={"Customer": "CustomerId", "Employee": "EmployeeId", "Order": "OrderId"},
        ),
        ContractTarget(
            name="nw-fastapi",
            app_path=app_dir / "nw_fastapi_app.py",
            spec_candidates=("/openapi.json", "/api/swagger.json"),
            env={"SAFRS_NW_RESET_DB": "1"},
            collection_id_keys={"Customer": "CustomerId", "Employee": "EmployeeId", "Order": "OrderId"},
        ),
    )

    filter_names = os.environ.get("SAFRS_CONTRACT_TARGETS", "").strip()
    if not filter_names:
        return targets

    wanted = {name.strip() for name in filter_names.split(",") if name.strip()}
    return tuple(target for target in targets if target.name in wanted)
