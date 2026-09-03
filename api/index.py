from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for package_root in (
    ROOT / "gilbic_backend" / "src",
    ROOT / "spina_backend_mobile" / "src",
):
    value = str(package_root)
    if value not in sys.path:
        sys.path.insert(0, value)

from gilbic_backend.main import app

__all__ = ["app"]
