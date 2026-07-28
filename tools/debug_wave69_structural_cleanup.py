from __future__ import annotations

import runpy
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "tools" / "test_legacy_collector_editor_cleanup_wave_69.py"


def main() -> None:
    try:
        runpy.run_path(str(TEST), run_name="__main__")
    except Exception:
        print("WAVE69_STRUCTURAL_TRACEBACK_START")
        traceback.print_exc()
        print("WAVE69_STRUCTURAL_TRACEBACK_END")
        raise


if __name__ == "__main__":
    main()
