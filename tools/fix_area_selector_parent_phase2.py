from __future__ import annotations

from pathlib import Path

APP = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
OLD = "    area_frame = build_simple_area_selector(self, win, area_var, width=34)\n"
NEW = "    area_frame = build_simple_area_selector(self, outer, area_var, width=34)\n"


def main() -> int:
    source = APP.read_text(encoding="utf-8")
    old_count = source.count(OLD)
    new_count = source.count(NEW)
    if old_count == 1 and new_count == 0:
        source = source.replace(OLD, NEW, 1)
        compile(source, str(APP), "exec")
        APP.write_text(source, encoding="utf-8")
        print("Corrected legacy Area selector parent")
        return 0
    if old_count == 0 and new_count == 1:
        print("Legacy Area selector parent already corrected")
        return 0
    raise SystemExit(f"Unexpected selector parent state: old={old_count}, new={new_count}")


if __name__ == "__main__":
    raise SystemExit(main())
