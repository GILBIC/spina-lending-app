from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "dashboard_chart_presentation.py"
DASHBOARD_BRIDGE = ROOT / "spina_app" / "tabs" / "dashboard.py"

TARGETS = (
    "_spina_v18_draw_dashboard_charts",
    "_spina_v20_fix_chart_titles",
    "_spina_v20_draw_dashboard_charts",
)
EXPECTED_LINES = {
    "_spina_v18_draw_dashboard_charts": 112,
    "_spina_v20_fix_chart_titles": 28,
    "_spina_v20_draw_dashboard_charts": 134,
}
EXPECTED_HASHES = {
    "_spina_v18_draw_dashboard_charts": "d8c62b3f57ba4de33e2fe5b2c3d706e7cf0f7213b2edfedfb20ffa39fbb31c5d",
    "_spina_v20_fix_chart_titles": "f545fb2e927fe39486312e806bb6df12b58fc501fa2baa12dbd9835b469fe1c1",
    "_spina_v20_draw_dashboard_charts": "cc50e2f5571433e55685fa621d92a8e304110b87200808b40a88b951673945a6",
}
EXPECTED_SIGNATURES = {
    "_spina_v18_draw_dashboard_charts": "self, rows",
    "_spina_v20_fix_chart_titles": "self",
    "_spina_v20_draw_dashboard_charts": "self, rows",
}
EXPECTED_CALLS = {
    "_spina_v18_draw_dashboard_charts": [
        "_log_exc", "_spina_v18_dashboard_palette", "_spina_v18_draw_round_rect",
        "_spina_v18_fmt_money_compact", "_spina_v18_patch_dashboard_chart_cards",
        "counts.get", "counts.values", "cv.configure", "cv.create_arc",
        "cv.create_oval", "cv.create_text", "cv.delete", "cv.winfo_height",
        "cv.winfo_width", "enumerate", "float", "format", "getattr", "int",
        "list", "lower", "max", "min", "r.get", "replace", "str", "sum",
    ],
    "_spina_v20_fix_chart_titles": [
        "child.cget", "child.configure", "getattr", "isinstance",
        "parent.winfo_children", "str",
    ],
    "_spina_v20_draw_dashboard_charts": [
        "_log_exc", "_spina_v20_dash_palette", "_spina_v20_fix_chart_titles",
        "_spina_v20_money", "_spina_v20_round_rect", "balances.get",
        "balances.values", "counts.get", "cv.configure", "cv.create_text",
        "cv.delete", "cv.winfo_height", "cv.winfo_width", "float", "getattr",
        "int", "len", "list", "lower", "max", "r.get", "replace", "str", "sum",
    ],
}
REQUIRED_DEPENDENCIES = (
    "_log_exc",
    "_spina_v18_dashboard_palette",
    "_spina_v18_draw_round_rect",
    "_spina_v18_fmt_money_compact",
    "_spina_v18_patch_dashboard_chart_cards",
    "_spina_v20_dash_palette",
    "_spina_v20_money",
    "_spina_v20_round_rect",
)
FORBIDDEN = (
    "connect_db(", "run_write(", ".execute(", ".executemany(", ".commit(",
    ".rollback(", "insert into", "delete from", "open(", "json.load",
    "json.dump", ".write_text(", ".read_text(", "os.remove", "os.replace",
    "subprocess.", "threading.", "reportlab", "filedialog.", "password",
    "verify_login", "permission",
)
BRIDGE_HASHES = {
    "configure_legacy_dashboard_feature": "89a44bd4c7cfa2ca660b5cdbc650c5755fcaf336ab1bf79ab13e65dc9d86e3c7",
    "_spina_v18_draw_dashboard_charts": "564eb211c951afb048d69c7704dc7269106e2a6393dc2a0fd0bf04650f8fd171",
    "_spina_v20_draw_dashboard_charts": "be9916f48720b41c943ff6db64088f6bbdea33d17454c364e8572fc70f670538",
}


def normalized(source: str) -> str:
    return "\n".join(line.rstrip() for line in source.strip().splitlines()) + "\n"


def source_hash(source: str) -> str:
    return hashlib.sha256(normalized(source).encode("utf-8")).hexdigest()


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def top_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(matches) == 1, (name, len(matches))
    return matches[0]


def source_for(text: str, node: ast.AST) -> str:
    source = ast.get_source_segment(text, node)
    assert source is not None
    return source


def calls_for(node: ast.FunctionDef) -> list[str]:
    return sorted({
        dotted(call.func)
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and dotted(call.func)
    })


def verify_bridge() -> None:
    text = DASHBOARD_BRIDGE.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for name, expected in BRIDGE_HASHES.items():
        node = top_function(tree, name)
        actual = source_hash(source_for(text, node))
        assert actual == expected, (name, actual, expected)


def verify_bridge_call(tree: ast.Module, last_target_line: int) -> None:
    candidates = []
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        fn = dotted(call.func)
        if not fn.endswith("configure_legacy_dashboard_feature"):
            continue
        kw = {item.arg: dotted(item.value) for item in call.keywords if item.arg}
        if kw.get("draw_v18_charts") == "_spina_v18_draw_dashboard_charts" and kw.get("draw_v20_charts") == "_spina_v20_draw_dashboard_charts":
            candidates.append((call.lineno, kw))
    assert len(candidates) == 1, candidates
    assert candidates[0][0] > last_target_line, candidates


def build_module(sources: dict[str, str]) -> str:
    lines = [
        '"""Dashboard chart presentation extracted in Wave 51."""',
        "from __future__ import annotations",
        "",
        "import tkinter as tk",
        "",
        "_DASHBOARD_CHART_DEPENDENCIES = {}",
        f"DASHBOARD_CHART_TARGETS = {TARGETS!r}",
        f"DASHBOARD_CHART_SOURCE_LINES = {EXPECTED_LINES!r}",
        f"DASHBOARD_CHART_SOURCE_SHA256 = {EXPECTED_HASHES!r}",
        f"DASHBOARD_CHART_SIGNATURES = {EXPECTED_SIGNATURES!r}",
        f"DASHBOARD_CHART_CALLS = {EXPECTED_CALLS!r}",
        f"DASHBOARD_CHART_REQUIRED_DEPENDENCIES = {REQUIRED_DEPENDENCIES!r}",
        "_PROTECTED_GLOBALS = {",
        "    '__builtins__', '__cached__', '__doc__', '__file__', '__loader__',",
        "    '__name__', '__package__', '__spec__', 'tk', '_PROTECTED_GLOBALS',",
        "    '_DASHBOARD_CHART_DEPENDENCIES', 'configure_dashboard_chart_dependencies',",
        "    'DASHBOARD_CHART_TARGETS', 'DASHBOARD_CHART_SOURCE_LINES',",
        "    'DASHBOARD_CHART_SOURCE_SHA256', 'DASHBOARD_CHART_SIGNATURES',",
        "    'DASHBOARD_CHART_CALLS', 'DASHBOARD_CHART_REQUIRED_DEPENDENCIES',",
        "}",
        "",
        "",
        "def configure_dashboard_chart_dependencies(namespace):",
        "    _DASHBOARD_CHART_DEPENDENCIES.clear()",
        "    missing = []",
        "    for name in DASHBOARD_CHART_REQUIRED_DEPENDENCIES:",
        "        if name not in namespace:",
        "            missing.append(name)",
        "            continue",
        "        value = namespace[name]",
        "        _DASHBOARD_CHART_DEPENDENCIES[name] = value",
        "        if name not in _PROTECTED_GLOBALS:",
        "            globals()[name] = value",
        "    if missing:",
        "        raise RuntimeError('Missing dashboard chart dependencies: ' + ', '.join(missing))",
        "",
        "",
    ]
    for name in TARGETS:
        lines.extend(normalized(sources[name]).rstrip().splitlines())
        lines.extend(["", ""])
    return "\n".join(lines).rstrip() + "\n"


def rewrite_desktop(text: str, nodes: dict[str, ast.FunctionDef]) -> str:
    lines = text.splitlines()
    remove_lines = set()
    for node in nodes.values():
        assert node.end_lineno is not None
        remove_lines.update(range(node.lineno, node.end_lineno + 1))

    insertion_after = max(int(node.end_lineno or node.lineno) for node in nodes.values())
    block = [
        "",
        "from spina_app.dashboard_chart_presentation import (",
        "    configure_dashboard_chart_dependencies as _wave51_configure_dashboard_chart_dependencies,",
        "    _spina_v18_draw_dashboard_charts as _wave51_spina_v18_draw_dashboard_charts,",
        "    _spina_v20_fix_chart_titles as _wave51_spina_v20_fix_chart_titles,",
        "    _spina_v20_draw_dashboard_charts as _wave51_spina_v20_draw_dashboard_charts,",
        ")",
        "_wave51_configure_dashboard_chart_dependencies(globals())",
        "_spina_v18_draw_dashboard_charts = _wave51_spina_v18_draw_dashboard_charts",
        "_spina_v20_fix_chart_titles = _wave51_spina_v20_fix_chart_titles",
        "_spina_v20_draw_dashboard_charts = _wave51_spina_v20_draw_dashboard_charts",
        "",
    ]

    out = []
    for lineno, line in enumerate(lines, start=1):
        if lineno not in remove_lines:
            out.append(line)
        if lineno == insertion_after:
            out.extend(block)
    updated = "\n".join(out) + ("\n" if text.endswith("\n") else "")
    ast.parse(updated)
    return updated


def main() -> None:
    assert not MODULE.exists(), MODULE
    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text)

    nodes: dict[str, ast.FunctionDef] = {}
    sources: dict[str, str] = {}
    for name in TARGETS:
        node = top_function(desktop_tree, name)
        source = source_for(desktop_text, node)
        assert (node.end_lineno or node.lineno) - node.lineno + 1 == EXPECTED_LINES[name]
        assert source_hash(source) == EXPECTED_HASHES[name]
        assert ast.unparse(node.args) == EXPECTED_SIGNATURES[name]
        assert calls_for(node) == EXPECTED_CALLS[name]
        lower = source.lower()
        for token in FORBIDDEN:
            assert token.lower() not in lower, (name, token)
        nodes[name] = node
        sources[name] = source

    for dependency in REQUIRED_DEPENDENCIES:
        assert any(
            isinstance(node, (ast.FunctionDef, ast.ImportFrom, ast.Import, ast.Assign))
            and dependency in (ast.get_source_segment(desktop_text, node) or "")
            for node in desktop_tree.body
        ), dependency

    verify_bridge()
    verify_bridge_call(desktop_tree, max(int(node.end_lineno or node.lineno) for node in nodes.values()))

    MODULE.write_text(build_module(sources), encoding="utf-8")
    DESKTOP.write_text(rewrite_desktop(desktop_text, nodes), encoding="utf-8")
    print("Wave 51 dashboard chart extraction applied: 3 functions, 274 lines.")


if __name__ == "__main__":
    main()
