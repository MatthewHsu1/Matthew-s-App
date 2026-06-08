from __future__ import annotations

import sys
from pathlib import Path

REPO_TOOL_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_TOOL_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
