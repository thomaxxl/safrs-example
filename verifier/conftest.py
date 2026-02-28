from __future__ import annotations

import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SAFRS_REPO = ROOT / "safrs"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SAFRS_REPO) not in sys.path:
    sys.path.insert(0, str(SAFRS_REPO))
