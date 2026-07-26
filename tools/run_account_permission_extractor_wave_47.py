from __future__ import annotations

import runpy
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
    compile(updated, str(EXTRACTOR), "exec")
    EXTRACTOR.write_text(updated, encoding="utf-8")
    runpy.run_path(str(EXTRACTOR), run_name="__main__")
    runpy.run_path(str(TEST), run_name="__main__")


if __name__ == "__main__":
    main()
