from __future__ import annotations

import sys
from pathlib import Path

# Project root must be on sys.path so rag/, agents/, memory/ are importable.
_root = str(Path(__file__).resolve().parent)
if _root not in sys.path:
    sys.path.insert(0, _root)
