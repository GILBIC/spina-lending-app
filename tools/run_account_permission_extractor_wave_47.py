from __future__ import annotations

import runpy
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTRACTOR = ROOT / "tools" / "extract_account_permission_wave_47.py"
TEST = ROOT / "tools" / "test_account_permission_presentation_wave_47.py"


def main() -> None:
    text = EXTRACTOR.read_text(encoding="utf-8")
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line == "    module_source = textwrap.dedent(")
    end = next(i for i in range(start, len(lines)) if lines[i] == "    ast.parse(module_source)")
    replacement = [
        "    module_source = (",
        "        '\"\"\"Account permission summary presentation extracted in Wave 47.\"\"\"\\n'",
        "        'from __future__ import annotations\\n\\n'",
        "        f'ACCOUNT_PERMISSION_TARGET = {TARGET!r}\\n'",
        "        f'ACCOUNT_PERMISSION_SOURCE_LINES = {EXPECTED_LINES}\\n'",
        "        f'ACCOUNT_PERMISSION_SOURCE_SHA256 = {EXPECTED_HASH!r}\\n'",
        "        f'ACCOUNT_PERMISSION_SIGNATURE = {EXPECTED_SIGNATURE!r}\\n\\n\\n'",
        "        + source.strip()",
        "        + '\\n'",
        "    )",
    ]
    lines[start:end] = replacement
    updated = "\n".join(lines) + "\n"

    needle = (
        "        import ast\n"
        "        import hashlib\n"
        "        from pathlib import Path\n\n"
        "        from spina_app.account_permission_presentation import ("
    )
    test_imports = (
        "        import ast\n"
        "        import hashlib\n"
        "        import sys\n"
        "        from pathlib import Path\n\n"
        "        _TEST_ROOT = Path(__file__).resolve().parents[1]\n"
        "        if str(_TEST_ROOT) not in sys.path:\n"
        "            sys.path.insert(0, str(_TEST_ROOT))\n\n"
        "        from spina_app.account_permission_presentation import ("
    )
    assert updated.count(needle) == 1
    updated = updated.replace(needle, test_imports)

    compile(updated, str(EXTRACTOR), "exec")
    EXTRACTOR.write_text(updated, encoding="utf-8")
    runpy.run_path(str(EXTRACTOR), run_name="__main__")
    try:
        runpy.run_path(str(TEST), run_name="__main__")
    except Exception as exc:
        frames = traceback.extract_tb(exc.__traceback__)
        last = frames[-1] if frames else None
        location = f"{last.filename}:{last.lineno} in {last.name}" if last else "unknown"
        print(f"WAVE47_REGRESSION_ERROR type={type(exc).__name__} message={exc!r} location={location}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
