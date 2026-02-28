from __future__ import annotations

import tempfile
from pathlib import Path


class SQLiteBackend:
    name = "sqlite"

    def __init__(self) -> None:
        self._paths: dict[str, Path] = {}

    def provision(self, run_id: str) -> dict[str, str]:
        tmp_dir = Path(tempfile.gettempdir()) / "safrs_verify"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_dir / f"sqlite_{run_id}.db"
        self._paths[run_id] = db_path
        return {
            "SAFRS_DATABASE_URL": f"sqlite:///{db_path}",
            "SAFRS_TMP_DB": str(db_path),
            "SAFRS_TMP_RESET_DB": "1",
        }

    def cleanup(self, run_id: str) -> None:
        path = self._paths.pop(run_id, None)
        if path is None:
            return
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
