#!/usr/bin/env python3
"""Guarded wiring patch for hierarchical Area storage Phase 1."""

from __future__ import annotations

import argparse
from pathlib import Path

APP = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MARKER = "from spina_app.area_hierarchy import ensure_area_hierarchy_schema"

ANCHOR = '''        # Areas master table (for validation & dropdown)
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS areas (
                    name TEXT PRIMARY KEY,
                    created_at TEXT
                )
            """)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0092', 'suppressed exception excpass_0092', __spina_exc)
            pass
'''

INTEGRATION = '''
        # Unlimited hierarchical Area storage.
        # Keep clients.area and areas.name synchronized for existing screens,
        # Collector Route, Data Bank, reports, and legacy databases.
        try:
            from spina_app.area_hierarchy import ensure_area_hierarchy_schema
            ensure_area_hierarchy_schema(self.conn)
        except Exception as e:
            try:
                _log_exc("schema:ensure hierarchical areas", e)
            except Exception as __spina_exc:
                _log_suppressed_once(
                    'excpass_area_hierarchy_schema',
                    'suppressed exception excpass_area_hierarchy_schema',
                    __spina_exc,
                )
                pass
'''


def inspect() -> str:
    source = APP.read_text(encoding="utf-8")
    marker_count = source.count(MARKER)
    anchor_count = source.count(ANCHOR)
    if marker_count == 1:
        if anchor_count != 1:
            raise RuntimeError(
                f"Patched state must retain one reviewed anchor, found {anchor_count}"
            )
        return "patched"
    if marker_count != 0:
        raise RuntimeError(f"Unexpected hierarchy marker count: {marker_count}")
    if anchor_count != 1:
        raise RuntimeError(f"Expected one exact Area schema anchor, found {anchor_count}")
    return "source"


def apply() -> bool:
    state = inspect()
    if state == "patched":
        return False
    source = APP.read_text(encoding="utf-8")
    patched = source.replace(ANCHOR, ANCHOR + INTEGRATION, 1)
    compile(patched, str(APP), "exec")
    APP.write_text(patched, encoding="utf-8")
    if inspect() != "patched":
        raise RuntimeError("Post-patch validation failed")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    changed = apply() if args.apply else False
    print(f"state={inspect()} changed={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
