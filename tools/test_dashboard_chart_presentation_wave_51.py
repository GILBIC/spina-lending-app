from __future__ import annotations

import ast
import hashlib
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "dashboard_chart_presentation.py"
BRIDGE = ROOT / "spina_app" / "tabs" / "dashboard.py"

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
BRIDGE_HASHES = {
    "configure_legacy_dashboard_feature": "89a44bd4c7cfa2ca660b5cdbc650c5755fcaf336ab1bf79ab13e65dc9d86e3c7",
    "_spina_v18_draw_dashboard_charts": "564eb211c951afb048d69c7704dc7269106e2a6393dc2a0fd0bf04650f8fd171",
    "_spina_v20_draw_dashboard_charts": "be9916f48720b41c943ff6db64088f6bbdea33d17454c364e8572fc70f670538",
}
FORBIDDEN = (
    "connect_db(", "run_write(", ".execute(", ".executemany(", ".commit(",
    ".rollback(", "insert into", "delete from", "open(", "json.load",
    "json.dump", ".write_text(", ".read_text(", "os.remove", "os.replace",
    "subprocess.", "threading.", "reportlab", "filedialog.", "password",
    "verify_login", "permission",
)


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


def top_functions(tree: ast.Module, name: str):
    return [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]


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


def verify_bridge_sources() -> None:
    text = BRIDGE.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for name, expected in BRIDGE_HASHES.items():
        matches = top_functions(tree, name)
        assert len(matches) == 1, (name, len(matches))
        actual = source_hash(source_for(text, matches[0]))
        assert actual == expected, (name, actual, expected)


def main() -> None:
    module = importlib.import_module("spina_app.dashboard_chart_presentation")
    assert module.DASHBOARD_CHART_TARGETS == TARGETS
    assert module.DASHBOARD_CHART_SOURCE_LINES == EXPECTED_LINES
    assert module.DASHBOARD_CHART_SOURCE_SHA256 == EXPECTED_HASHES
    assert module.DASHBOARD_CHART_SIGNATURES == EXPECTED_SIGNATURES
    assert module.DASHBOARD_CHART_CALLS == EXPECTED_CALLS

    module_text = MODULE.read_text(encoding="utf-8")
    module_tree = ast.parse(module_text)
    total_lines = 0
    for name in TARGETS:
        matches = top_functions(module_tree, name)
        assert len(matches) == 1, (name, len(matches))
        node = matches[0]
        source = source_for(module_text, node)
        line_count = (node.end_lineno or node.lineno) - node.lineno + 1
        assert line_count == EXPECTED_LINES[name], (name, line_count)
        assert source_hash(source) == EXPECTED_HASHES[name], name
        assert ast.unparse(node.args) == EXPECTED_SIGNATURES[name], name
        assert calls_for(node) == EXPECTED_CALLS[name], name
        lower = source.lower()
        for token in FORBIDDEN:
            assert token.lower() not in lower, (name, token)
        total_lines += line_count
    assert total_lines == 274, total_lines

    sentinels = {name: object() for name in module.DASHBOARD_CHART_REQUIRED_DEPENDENCIES}
    module.configure_dashboard_chart_dependencies(sentinels)
    assert module._DASHBOARD_CHART_DEPENDENCIES == sentinels
    for name, value in sentinels.items():
        assert getattr(module, name) is value

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text)
    for name in TARGETS:
        assert not top_functions(desktop_tree, name), f"{name} remains in desktop"

    imports = [
        node for node in desktop_tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "spina_app.dashboard_chart_presentation"
    ]
    assert len(imports) == 1, len(imports)
    aliases = {(alias.name, alias.asname) for alias in imports[0].names}
    expected_aliases = {
        ("configure_dashboard_chart_dependencies", "_wave51_configure_dashboard_chart_dependencies"),
        ("_spina_v18_draw_dashboard_charts", "_wave51_spina_v18_draw_dashboard_charts"),
        ("_spina_v20_fix_chart_titles", "_wave51_spina_v20_fix_chart_titles"),
        ("_spina_v20_draw_dashboard_charts", "_wave51_spina_v20_draw_dashboard_charts"),
    }
    assert aliases == expected_aliases, aliases

    expected_rebinds = {
        "_spina_v18_draw_dashboard_charts": "_wave51_spina_v18_draw_dashboard_charts",
        "_spina_v20_fix_chart_titles": "_wave51_spina_v20_fix_chart_titles",
        "_spina_v20_draw_dashboard_charts": "_wave51_spina_v20_draw_dashboard_charts",
    }
    actual_rebinds = {}
    configure_calls = []
    bridge_calls = []
    for node in desktop_tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in expected_rebinds and isinstance(node.value, ast.Name):
                actual_rebinds[target.id] = node.value.id
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if dotted(call.func) == "_wave51_configure_dashboard_chart_dependencies":
                configure_calls.append(node.lineno)
    for call in (node for node in ast.walk(desktop_tree) if isinstance(node, ast.Call)):
        kw = {item.arg: dotted(item.value) for item in call.keywords if item.arg}
        if kw.get("draw_v18_charts") == "_spina_v18_draw_dashboard_charts" and kw.get("draw_v20_charts") == "_spina_v20_draw_dashboard_charts":
            bridge_calls.append((call.lineno, dotted(call.func), kw))
    assert actual_rebinds == expected_rebinds, actual_rebinds
    assert len(configure_calls) == 1, configure_calls
    assert len(bridge_calls) == 1, bridge_calls
    assert imports[0].lineno < configure_calls[0] < bridge_calls[0][0]

    verify_bridge_sources()
    print("Wave 51 dashboard-chart regression passed: 3 functions, 274 lines.")


if __name__ == "__main__":
    main()
