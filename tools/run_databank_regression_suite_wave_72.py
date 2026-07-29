from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
SELF = Path(__file__).resolve()
EXCLUDED_PARTS = ("plan_", "inspect_", "extract_", "run_databank_regression_suite_wave_72")


def main() -> None:
    candidates = set(TOOLS.glob("test_*databank*.py"))
    candidates.update(TOOLS.glob("test_data_bank*.py"))
    tests = []
    for path in sorted(candidates):
        if path.resolve() == SELF:
            continue
        if any(part in path.name for part in EXCLUDED_PARTS):
            continue
        tests.append(path)

    assert len(tests) >= 8, [path.name for path in tests]

    failures = []
    print(f"Running {len(tests)} Data Bank regression files")
    for path in tests:
        module = ".".join(path.relative_to(ROOT).with_suffix("").parts)
        print(f"\n=== {module} ===", flush=True)
        result = subprocess.run([sys.executable, "-m", module], cwd=ROOT, check=False)
        if result.returncode != 0:
            failures.append((path.name, result.returncode))

    print("\nExecuted:")
    for path in tests:
        print(f"- {path.name}")

    if failures:
        print("\nData Bank regression failures:")
        for name, returncode in failures:
            print(f"- {name} (exit {returncode})")
        raise SystemExit(1)

    print("\nAll discovered Data Bank regressions passed")


if __name__ == "__main__":
    main()
