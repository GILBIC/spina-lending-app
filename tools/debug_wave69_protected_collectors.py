from __future__ import annotations

import runpy
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "tools" / "test_collectors_editor_wave_26.py"


def main() -> None:
    try:
        runpy.run_path(str(TEST), run_name="__main__")
    except Exception as exc:
        frames = traceback.extract_tb(exc.__traceback__)
        last = frames[-1]
        print(
            "WAVE69_PROTECTED_COLLECTORS_FAILURE "
            f"type={type(exc).__name__} line={last.lineno} "
            f"code={last.line!r} message={exc!r}",
            flush=True,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
