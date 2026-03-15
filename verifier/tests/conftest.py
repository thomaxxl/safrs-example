from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
VERIFIER_ROOT = HERE.parent
SRC = VERIFIER_ROOT / "src"
APPS = VERIFIER_ROOT / "apps"

for path in (SRC, APPS, VERIFIER_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


@pytest.fixture(autouse=True)
def _require_loopback_socket_for_network_tests(request: pytest.FixtureRequest) -> None:
    if request.node.get_closest_marker("contract") is None and request.node.get_closest_marker("parity") is None:
        return

    sock: socket.socket | None = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
    except PermissionError as exc:
        pytest.fail(
            "Verifier needs loopback TCP bind permission but it is blocked in this environment "
            f"({exc!r}). Run the verifier outside restricted sandbox/container security settings.",
            pytrace=False,
        )
    finally:
        if sock is not None:
            sock.close()
