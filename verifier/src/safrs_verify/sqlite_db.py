from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .artifacts import ArtifactBundle


@dataclass(frozen=True)
class SQLiteRun:
    db_path: Path
    env: dict[str, str]


def prepare_sqlite_env(artifacts: ArtifactBundle) -> SQLiteRun:
    db_path = artifacts.directory / "db.sqlite"
    return SQLiteRun(
        db_path=db_path,
        env={
            "SAFRS_EXAMPLE_DB_PATH": str(db_path),
            "SAFRS_EXAMPLE_RESET_DB": "1",
        },
    )
