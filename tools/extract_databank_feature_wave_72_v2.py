from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path

from tools.extract_databank_feature_wave_72 import (
    APP_METHODS,
    EXPECTED,
    LEGACY_BUILD_DATA_TAB,
    MODULE,
    SOURCE,
    TOP_LEVEL_FUNCTIONS,
    _final_main_guard,
    _roots,
    _sha256,
)


def _dedent_method_source(raw: str) -> str:
    """Remove the class indent without changing multiline string contents."""
    protected_rows = set()
    for token in tokenize.generate_tokens(io.StringIO(raw).readline):
        if token.type == tokenize.STRING and token.end[0] > token.start[0]:
            protected_rows.update(range(token.start[0] + 1, token.end[0] + 1))

    output = []
    for row, line in enumerate(raw.splitlines(keepends=True), start=1):
        if row in protected_rows:
            output.append(line)
        elif line.startswith("    "):
            output.append(line[4:])
        else:
            output.append(line)
    moved = "".join(output)
    ast.parse(moved)
    return moved


def main() -> None:
    original = SOURCE.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    tree = ast.parse(original)
    roots = _roots(tree)

    extracted = []
    removal_ranges = []
    for key, (expected_lines, raw_hash, ast_hash) in EXPECTED.items():
        node = roots.get(key)
        assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)), key
        start = node.lineno
        end = node.end_lineno or start
        raw = "".join(lines[start - 1:end])
        assert end - start + 1 == expected_lines, (key, end - start + 1)
        assert _sha256(raw) == raw_hash, key
        assert _sha256(ast.dump(node, include_attributes=False)) == ast_hash, key
        moved = _dedent_method_source(raw) if key[0] else raw
        moved_node = next(
            item for item in ast.parse(moved).body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        )
        assert _sha256(ast.dump(moved_node, include_attributes=False)) == ast_hash, key
        extracted.append((start, key, moved))
        removal_ranges.append((start - 1, end))

    legacy = roots.get(("App", "_build_data_tab"))
    assert isinstance(legacy, (ast.FunctionDef, ast.AsyncFunctionDef))
    legacy_start = legacy.lineno
    legacy_end = legacy.end_lineno or legacy_start
    legacy_raw = "".join(lines[legacy_start - 1:legacy_end])
    assert legacy_end - legacy_start + 1 == LEGACY_BUILD_DATA_TAB[0]
    assert _sha256(legacy_raw) == LEGACY_BUILD_DATA_TAB[1]
    assert _sha256(ast.dump(legacy, include_attributes=False)) == LEGACY_BUILD_DATA_TAB[2]
    assert "App._build_data_tab = _spina_v15_build_data_tab" in original
    removal_ranges.append((legacy_start - 1, legacy_end))

    module_parts = [
        "from __future__ import annotations\n\n",
        "def configure_databank_feature_dependencies(namespace):\n",
        "    # Shared imports, constants, logging, and DB helpers remain owned by the foundation app.\n",
        "    for name, value in namespace.items():\n",
        "        if not str(name).startswith('__'):\n",
        "            globals()[name] = value\n",
        "\n\n",
    ]
    for _start, _key, source in sorted(extracted, key=lambda item: item[0]):
        module_parts.append(source.rstrip() + "\n\n\n")
    module_text = "".join(module_parts).rstrip() + "\n"
    ast.parse(module_text)
    MODULE.write_text(module_text, encoding="utf-8")

    cleaned_lines = list(lines)
    for start, end in sorted(removal_ranges, reverse=True):
        del cleaned_lines[start:end]
    cleaned = "".join(cleaned_lines)
    cleaned_tree = ast.parse(cleaned)
    app_node = next(node for node in cleaned_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")

    import_lines = [
        "# Wave 72: complete Data Bank feature/controller extraction.\n",
        "import spina_app.databank_feature as _wave72_databank_feature\n",
    ]
    for name in TOP_LEVEL_FUNCTIONS:
        import_lines.append(f"{name} = _wave72_databank_feature.{name}\n")
    import_lines.append("\n")
    cleaned_lines = cleaned.splitlines(keepends=True)
    cleaned_lines[app_node.lineno - 1:app_node.lineno - 1] = import_lines
    cleaned = "".join(cleaned_lines)

    rebound_tree = ast.parse(cleaned)
    rebound_app = next(node for node in rebound_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    bind_lines = ["\n# Wave 72: bind complete Data Bank App methods before later runtime patches.\n"]
    for name in APP_METHODS:
        bind_lines.append(f"App.{name} = _wave72_databank_feature.{name}\n")
    bind_lines.append("\n")
    cleaned_lines = cleaned.splitlines(keepends=True)
    cleaned_lines[rebound_app.end_lineno:rebound_app.end_lineno] = bind_lines
    cleaned = "".join(cleaned_lines)

    configured_tree = ast.parse(cleaned)
    final_guard = _final_main_guard(configured_tree)
    configure_lines = [
        "# Refresh application-owned dependencies after all runtime patches load.\n",
        "_wave72_databank_feature.configure_databank_feature_dependencies(globals())\n",
        "\n",
    ]
    cleaned_lines = cleaned.splitlines(keepends=True)
    cleaned_lines[final_guard.lineno - 1:final_guard.lineno - 1] = configure_lines
    cleaned = "".join(cleaned_lines)

    verified = ast.parse(cleaned)
    verified_roots = _roots(verified)
    for key in EXPECTED:
        assert key not in verified_roots, key
    assert ("App", "_build_data_tab") not in verified_roots
    assert cleaned.count("import spina_app.databank_feature as _wave72_databank_feature") == 1
    assert cleaned.count("_wave72_databank_feature.configure_databank_feature_dependencies(globals())") == 1
    for name in APP_METHODS:
        assert cleaned.count(f"App.{name} = _wave72_databank_feature.{name}") == 1
    for name in TOP_LEVEL_FUNCTIONS:
        assert cleaned.count(f"{name} = _wave72_databank_feature.{name}") == 1
    assert "App._build_data_tab = _spina_v15_build_data_tab" in cleaned

    SOURCE.write_text(cleaned, encoding="utf-8")
    print(f"Moved {len(EXPECTED)} complete Data Bank functions ({sum(item[0] for item in EXPECTED.values())} lines)")
    print("Removed 67-line legacy _build_data_tab; modern Wave 49 binding retained")


if __name__ == "__main__":
    main()
