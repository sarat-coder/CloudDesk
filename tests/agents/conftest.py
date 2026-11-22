from __future__ import annotations

import sys
from pathlib import Path

# tests/agents/ must NOT have __init__.py — it would shadow the real agents/ package.
# This conftest ensures the project root is on sys.path before collection.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
_BACKEND = str(Path(_PROJECT_ROOT) / "backend")
for _p in (_BACKEND, _PROJECT_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
