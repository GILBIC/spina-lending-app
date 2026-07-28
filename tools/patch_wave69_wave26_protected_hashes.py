from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "tools" / "test_collectors_editor_wave_26.py"
STALE = "'_spina_v25_build_collectors_tab': 'f5b787f580fd4202ebbc324e70da4a8c2adee5190e959c3af01b0e2402b32e92', "


def main() -> None:
    text = TEST.read_text(encoding="utf-8")
    if text.count(STALE) != 1:
        raise RuntimeError(f"Expected one stale Wave 26 collector-tab hash; found {text.count(STALE)}")
    text = text.replace(STALE, "", 1)
    ast.parse(text, filename=str(TEST))
    TEST.write_text(text, encoding="utf-8")
    print("Removed stale Wave 26 _spina_v25_build_collectors_tab hash; Wave 44 protects the active replacement.")


if __name__ == "__main__":
    main()
