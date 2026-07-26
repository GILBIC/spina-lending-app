from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTRACTOR = ROOT / "tools" / "extract_side_navigation_batch_wave_48.py"


def replace_block(lines: list[str], start_marker: str, end_marker: str, replacement: list[str]) -> None:
    start = next(i for i, line in enumerate(lines) if line.startswith(start_marker))
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith(end_marker))
    lines[start:end] = replacement


def main() -> None:
    text = EXTRACTOR.read_text(encoding="utf-8")
    lines = text.splitlines()

    replace_block(
        lines,
        "def assignment_capture(",
        "def app_binding(",
        [
            "def assignment_capture(tree: ast.AST, name: str, owner: str, attr: str) -> ast.Assign:",
            "    matches = []",
            "    for node in ast.walk(tree):",
            "        if not isinstance(node, ast.Assign) or len(node.targets) != 1:",
            "            continue",
            "        target = node.targets[0]",
            "        if isinstance(target, ast.Name) and target.id == name:",
            "            matches.append(node)",
            "    assert len(matches) == 1, (name, len(matches))",
            "    rendered = ast.unparse(matches[0].value)",
            "    assert owner in rendered and attr in rendered, (name, rendered)",
            "    return matches[0]",
            "",
            "",
        ],
    )

    replace_block(
        lines,
        "def find_capture(",
        "def find_binding(",
        [
            "def find_capture(tree: ast.AST, name: str, attr: str):",
            "    matches = []",
            "    for node in ast.walk(tree):",
            "        if not isinstance(node, ast.Assign) or len(node.targets) != 1:",
            "            continue",
            "        target = node.targets[0]",
            "        if isinstance(target, ast.Name) and target.id == name:",
            "            matches.append(node)",
            "    assert len(matches) == 1, (name, len(matches))",
            "    rendered = ast.unparse(matches[0].value)",
            "    assert 'App' in rendered and attr in rendered, (name, rendered)",
            "    return matches[0]",
            "",
            "",
        ],
    )

    updated = "\n".join(lines) + "\n"
    compile(updated, str(EXTRACTOR), "exec")
    EXTRACTOR.write_text(updated, encoding="utf-8")
    runpy.run_path(str(EXTRACTOR), run_name="__main__")


if __name__ == "__main__":
    main()
