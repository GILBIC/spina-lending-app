from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "wave-60-architecture-refresh.json"


def _run(module: str) -> dict[str, object]:
    proc = subprocess.run(
        [sys.executable, "-m", module],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "module": module,
        "returncode": proc.returncode,
        "output": proc.stdout,
    }


def main() -> None:
    results = [
        _run("tools.generate_architecture_map"),
        _run("tools.test_architecture_map"),
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    for result in results:
        print(f"=== {result['module']} (exit {result['returncode']}) ===")
        print(result["output"])
    failed = [result for result in results if result["returncode"] != 0]
    if failed:
        raise SystemExit(int(failed[0]["returncode"]) or 1)


if __name__ == "__main__":
    main()
