from __future__ import annotations

import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPT = ROOT / "safrs" / "tmp" / "verify_openapi_contract.py"
APP = ROOT / "safrs" / "tmp" / "flask_app.py"


def main() -> int:
    cmd = [sys.executable, str(SCRIPT), "--app", str(APP), "--db", "sqlite", *sys.argv[1:]]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
