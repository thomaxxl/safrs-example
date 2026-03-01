from __future__ import annotations

import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
VERIFIER_ROOT = HERE.parent
SRC = VERIFIER_ROOT / "src"
APPS = VERIFIER_ROOT / "apps"

for path in (SRC, APPS, VERIFIER_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
