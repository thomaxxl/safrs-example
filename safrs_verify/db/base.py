from __future__ import annotations

from typing import Protocol


class BackendUnavailable(RuntimeError):
    pass


class DBBackend(Protocol):
    name: str

    def provision(self, run_id: str) -> dict[str, str]:
        raise NotImplementedError

    def cleanup(self, run_id: str) -> None:
        raise NotImplementedError
