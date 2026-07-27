from __future__ import annotations

import ast
import hashlib
import pprint
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "system_data_presentation.py"
TEST = ROOT / "tools" / "test_system_data_presentation_wave_55.py"
TARGETS = (
    "_show_system_data_tab",
    "_hide_system_data_tab",
    "_system_data_get_date",
    "_system_data_use_focus_date",
    "_system_data_refresh_summary",
    "_system_data_open_close",
    "_system_data_open_history",
    "_system_data_open_records",
    "_system_data_print_report",
    "_build_system_data_tab",
)
WRITE_MARKERS = {
    "add_client", "update_client", "renew_client", "delete_client", "archive_client",
    "set_transaction", "save_transaction", "close_day", "reopen_day", "run_write",
    "execute", "executemany", "commit", "rollback", "save_settings", "write_text",
    "write_bytes", "unlink", "remove", "replace", "rename", "mkdir",
}
TEMPORARY = (
    ROOT / "tools" / "plan_system_data_presentation_wave_55.py",
    ROOT / ".github" / "workflows" / "plan-system-data-presentation-wave-55.yml",
    ROOT / "tools" / "extract_system_data_presentation_wave_55.py",
    ROOT / ".github" / "workflows" / "extract-system-data-presentation-wave-55.yml",
)


def normalized(source: str) -> str:
    return "\n".join(line.rstrip() for line in source.strip().splitlines())


def source_hash(source: str) -> str:
    return hashlib.sha256(normalized(source).encode("utf-8")).hexdigest()


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def build_module(metadata: dict[str, dict[str, object]], sources: dict[str, str]) -> str:
    protected = {
        "_SYSTEM_DATA_PRESENTATION_DEPENDENCIES",
        "_PROTECTED_GLOBALS",
        "configure_system_data_presentation_dependencies",
        "SYSTEM_DATA_PRESENTATION_TARGETS",
        "SYSTEM_DATA_PRESENTATION_SOURCE_LINES",
        "SYSTEM_DATA_PRESENTATION_SOURCE_SHA256",
        "SYSTEM_DATA_PRESENTATION_SIGNATURES",
        "SYSTEM_DATA_PRESENTATION_CALLS",
        "SYSTEM_DATA_PRESENTATION_TOTAL_SOURCE_LINES",
        *TARGETS,
        "__name__", "__file__", "__package__", "__loader__", "__spec__",
        "__builtins__", "__cached__", "__doc__",
    }
    meta_repr = pprint.pformat(metadata, width=140, sort_dicts=False)
    pieces = [
        '"""System Data tab presentation extracted in Wave 55."""\n',
        "from __future__ import annotations\n\n",
        "_SYSTEM_DATA_PRESENTATION_DEPENDENCIES = {}\n",
        f"_PROTECTED_GLOBALS = {protected!r}\n\n",
        "def configure_system_data_presentation_dependencies(namespace):\n",
        "    _SYSTEM_DATA_PRESENTATION_DEPENDENCIES.clear()\n",
        "    _SYSTEM_DATA_PRESENTATION_DEPENDENCIES.update(namespace)\n",
        "    for name, value in namespace.items():\n",
        "        if name not in _PROTECTED_GLOBALS:\n",
        "            globals()[name] = value\n\n",
        f"_SYSTEM_DATA_PRESENTATION_METADATA = {meta_repr}\n",
        f"SYSTEM_DATA_PRESENTATION_TARGETS = {list(TARGETS)!r}\n",
        "SYSTEM_DATA_PRESENTATION_SOURCE_LINES = {name: item['lines'] for name, item in _SYSTEM_DATA_PRESENTATION_METADATA.items()}\n",
        "SYSTEM_DATA_PRESENTATION_SOURCE_SHA256 = {name: item['sha256'] for name, item in _SYSTEM_DATA_PRESENTATION_METADATA.items()}\n",
        "SYSTEM_DATA_PRESENTATION_SIGNATURES = {name: item['signature'] for name, item in _SYSTEM_DATA_PRESENTATION_METADATA.items()}\n",
        "SYSTEM_DATA_PRESENTATION_CALLS = {name: item['calls'] for name, item in _SYSTEM_DATA_PRESENTATION_METADATA.items()}\n",
        f"SYSTEM_DATA_PRESENTATION_TOTAL_SOURCE_LINES = {sum(int(item['lines']) for item in metadata.values())}\n\n",
    ]
    for name in TARGETS:
        pieces.append(sources[name].rstrip() + "\n\n")
    return "".join(pieces)


def build_test(metadata: dict[str, dict[str, object]]) -> str:
    expected = pprint.pformat(metadata, width=160, sort_dicts=False)
    return f'''from __future__ import annotations

import ast
import hashlib
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE_PATH = ROOT / "spina_app" / "system_data_presentation.py"
TARGETS = {TARGETS!r}
EXPECTED = {expected}
WRITE_MARKERS = {WRITE_MARKERS!r}


def normalized(source: str) -> str:
    return "\\n".join(line.rstrip() for line in source.strip().splitlines())


def source_hash(source: str) -> str:
    return hashlib.sha256(normalized(source).encode("utf-8")).hexdigest()


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{{left}}.{{node.attr}}" if left else node.attr
    return ""


def main() -> None:
    module = importlib.import_module("spina_app.system_data_presentation")
    assert module.SYSTEM_DATA_PRESENTATION_TARGETS == list(TARGETS)
    assert module.SYSTEM_DATA_PRESENTATION_TOTAL_SOURCE_LINES == 175
    assert module.SYSTEM_DATA_PRESENTATION_SOURCE_LINES == {{name: item["lines"] for name, item in EXPECTED.items()}}
    assert module.SYSTEM_DATA_PRESENTATION_SOURCE_SHA256 == {{name: item["sha256"] for name, item in EXPECTED.items()}}
    assert module.SYSTEM_DATA_PRESENTATION_SIGNATURES == {{name: item["signature"] for name, item in EXPECTED.items()}}
    assert module.SYSTEM_DATA_PRESENTATION_CALLS == {{name: item["calls"] for name, item in EXPECTED.items()}}

    module_text = MODULE_PATH.read_text(encoding="utf-8")
    module_lines = module_text.splitlines()
    module_tree = ast.parse(module_text)
    for name in TARGETS:
        matches = [node for node in module_tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
        assert len(matches) == 1, (name, len(matches))
        node = matches[0]
        source = "\\n".join(module_lines[node.lineno - 1 : node.end_lineno])
        assert len(normalized(source).splitlines()) == EXPECTED[name]["lines"]
        assert source_hash(source) == EXPECTED[name]["sha256"]
        assert ast.unparse(node.args) == EXPECTED[name]["signature"]
        calls = sorted({{dotted(call.func) for call in ast.walk(node) if isinstance(call, ast.Call) and dotted(call.func)}})
        assert calls == EXPECTED[name]["calls"], (name, calls)
        write_like = sorted({{call for call in calls if call.rsplit(".", 1)[-1].lower() in WRITE_MARKERS}})
        assert not write_like, (name, write_like)

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text)
    app = next(node for node in desktop_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    remaining = {{node.name for node in app.body if isinstance(node, ast.FunctionDef)}}
    assert not (set(TARGETS) & remaining), sorted(set(TARGETS) & remaining)

    imports = [
        node for node in desktop_tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.system_data_presentation"
    ]
    assert len(imports) == 1
    aliases = {{(item.name, item.asname) for item in imports[0].names}}
    assert ("configure_system_data_presentation_dependencies", "_wave55_configure_system_data_presentation_dependencies") in aliases
    for name in TARGETS:
        assert (name, "_wave55" + name) in aliases

    configure = [
        node for node in desktop_tree.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "_wave55_configure_system_data_presentation_dependencies"
    ]
    assert len(configure) == 1

    bindings = []
    for node in desktop_tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
            and target.value.id == "App" and target.attr in TARGETS
            and isinstance(node.value, ast.Name)
        ):
            bindings.append((target.attr, node.value.id, node.lineno))
    assert sorted((name, value) for name, value, _ in bindings) == sorted((name, "_wave55" + name) for name in TARGETS)
    assert all(app.end_lineno < line for _, _, line in bindings)

    print("Wave 55 System Data presentation regression passed.")


if __name__ == "__main__":
    main()
'''


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    methods = {node.name: node for node in app.body if isinstance(node, ast.FunctionDef)}
    missing = [name for name in TARGETS if name not in methods]
    if missing:
        raise SystemExit(f"Missing App methods: {missing}")

    metadata: dict[str, dict[str, object]] = {}
    sources: dict[str, str] = {}
    spans: list[tuple[int, int]] = []
    for name in TARGETS:
        node = methods[name]
        start = node.lineno
        end = node.end_lineno or node.lineno
        raw = "".join(lines[start - 1:end])
        source = textwrap.dedent(raw)
        calls = sorted({dotted(call.func) for call in ast.walk(node) if isinstance(call, ast.Call) and dotted(call.func)})
        write_like = sorted({call for call in calls if call.rsplit(".", 1)[-1].lower() in WRITE_MARKERS})
        if write_like:
            raise SystemExit(f"Protected write-like calls in {name}: {write_like}")
        metadata[name] = {
            "lines": len(normalized(source).splitlines()),
            "sha256": source_hash(source),
            "signature": ast.unparse(node.args),
            "calls": calls,
        }
        sources[name] = source
        spans.append((start, end))

    total = sum(int(item["lines"]) for item in metadata.values())
    if total != 175:
        raise SystemExit(f"Unexpected source total: {total}")

    for start, end in sorted(spans, reverse=True):
        del lines[start - 1:end]
    desktop = "".join(lines)

    marker = "# --- Wave 54 Audit presentation wiring ---"
    if marker not in desktop:
        raise SystemExit("Wave 54 wiring marker not found")
    wiring_lines = [
        "# --- Wave 55 System Data presentation wiring ---",
        "from spina_app.system_data_presentation import (",
        "    configure_system_data_presentation_dependencies as _wave55_configure_system_data_presentation_dependencies,",
    ]
    for name in TARGETS:
        wiring_lines.append(f"    {name} as _wave55{name},")
    wiring_lines.extend([
        ")",
        "_wave55_configure_system_data_presentation_dependencies(globals())",
    ])
    for name in TARGETS:
        wiring_lines.append(f"App.{name} = _wave55{name}")
    wiring_lines.extend(["# --- End Wave 55 System Data presentation wiring ---", "", ""])
    desktop = desktop.replace(marker, "\n".join(wiring_lines) + marker, 1)

    MODULE.write_text(build_module(metadata, sources), encoding="utf-8")
    DESKTOP.write_text(desktop, encoding="utf-8")
    TEST.write_text(build_test(metadata), encoding="utf-8")

    for path in TEMPORARY:
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    print(f"Extracted {len(TARGETS)} System Data methods and {total} exact source lines.")


if __name__ == "__main__":
    main()
