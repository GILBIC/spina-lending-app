from __future__ import annotations

import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "wave-60-databank-editor-smoke-traceback.txt"


def main() -> None:
    try:
        from tools import test_databank_editor_widget_smoke_wave_60 as smoke
        smoke.main()
    except BaseException:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(traceback.format_exc(), encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
