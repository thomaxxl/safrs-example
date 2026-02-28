from __future__ import annotations

import os

from .base import BackendUnavailable, DBBackend
from .sqlite import SQLiteBackend


def resolve_db_backends(selection: str | None = None) -> tuple[DBBackend, ...]:
    selected = selection if selection is not None else os.environ.get("SAFRS_TEST_DBS", "sqlite")
    names = [item.strip().lower() for item in selected.split(",") if item.strip()]
    if not names:
        names = ["sqlite"]

    backends: list[DBBackend] = []
    for name in names:
        if name != "sqlite":
            raise ValueError(f"Unsupported DB backend '{name}'. This verifier only supports sqlite.")
        backends.append(SQLiteBackend())
    return tuple(backends)


__all__ = [
    "BackendUnavailable",
    "DBBackend",
    "SQLiteBackend",
    "resolve_db_backends",
]
