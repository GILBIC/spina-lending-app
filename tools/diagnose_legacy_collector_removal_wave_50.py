from __future__ import annotations

import json
import runpy
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "wave-50-collector-removal-diagnostic.json"
REMOVER = ROOT / "tools" / "remove_legacy_collector_presentation_wave_50.py"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        runpy.run_path(str(REMOVER), run_name="__main__")
    except BaseException as exc:
        report = {
            "ok": False,
            "exception_type": type(exc).__name__,
            "exception": str(exc),
            "traceback": traceback.format_exc(),
        }
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=True))
        raise
    else:
        report = {"ok": True}
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
