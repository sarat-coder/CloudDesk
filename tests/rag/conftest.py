from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path so `rag.*` is importable during collection.
_root = str(Path(__file__).resolve().parent.parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)
