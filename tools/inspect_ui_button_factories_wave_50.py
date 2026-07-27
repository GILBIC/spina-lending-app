from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
COLLECTOR_MODULE = ROOT / "spina_app" / "collector_tab_presentation.py"
LOGIN_MODULE = ROOT / "spina_app" / "login_dialog_presentation.py"
UI_CONTROLS = ROOT / "spina_app" / "ui_controls.py"
OUT = ROOT / "artifacts" / "wave-50-ui-button-factories-boundary.json"

TARGETS = (
    "_spina_v25_collector_button",
    "_spina_v27_route_button",
    "_spina_v32_login_button",
)
FORBIDDEN = (
    "connect_db(", "self.db", ".execute(", ".executemany(", ".commit(",
    ".rollback(", "run_write(", "open(", "json.load", "json.dump",
    "_write_json_atomic", "write_text(", "write_bytes(", "os.makedirs",
    "os.remove", "os.rename", "os.replace", "shutil.", "subprocess.",
    "threading.", "INSERT INTO", "UPDATE ", "DELETE FROM ",
    "_verify_login", "_load_users_db", "password", "permission",
)


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def normalized(source: str) -> str:
    return "\n".join(line.rstrip() for line in source.strip().splitlines()) + "\n"


def top_function(text: str, tree: ast.Module, name: str) -> tuple[ast.FunctionDef, str]:
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(matches) == 1, (name, len(matches))
    source = ast.get_source_segment(text, matches[0])
    assert source is not None
    return matches[0], source


def calls_for(node: ast.FunctionDef) -> list[str]:
    return sorted({
        dotted(call.func)
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and dotted(call.func)
    })


def caller_uses(path: Path, function_name: str, target: str) -> bool:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    return target in calls_for(fn)


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    records = []
    for name in TARGETS:
        node, source = top_function(text, tree, name)
        hits = sorted({token for token in FORBIDDEN if token.lower() in source.lower()})
        assert not hits, (name, hits)
        records.append({
            "name": name,
            "lineno": node.lineno,
            "end_lineno": node.end_lineno,
            "lines": (node.end_lineno or node.lineno) - node.lineno + 1,
            "signature": ast.unparse(node.args),
            "sha256": hashlib.sha256(normalized(source).encode("utf-8")).hexdigest(),
            "calls": calls_for(node),
            "source": source,
        })

    usage = {
        "legacy_v25_builder_uses_collector_button": caller_uses(
            DESKTOP, "_spina_v25_build_collectors_tab", "_spina_v25_collector_button"
        ),
        "active_v27_builder_uses_route_button": caller_uses(
            COLLECTOR_MODULE, "_spina_v27_build_collectors_tab", "_spina_v27_route_button"
        ),
        "active_login_dialog_uses_login_button": caller_uses(
            LOGIN_MODULE, "_spina_v32_prompt_login", "_spina_v32_login_button"
        ),
    }
    assert all(usage.values()), usage

    ui_text = UI_CONTROLS.read_text(encoding="utf-8")
    ui_tree = ast.parse(ui_text)
    existing = sorted({
        node.name for node in ui_tree.body
        if isinstance(node, ast.FunctionDef) and node.name in TARGETS
    })
    assert not existing, existing

    assignments = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        mentioned = sorted({
            part.id for part in ast.walk(node)
            if isinstance(part, ast.Name) and part.id in TARGETS
        })
        if mentioned:
            assignments.append({
                "lineno": getattr(node, "lineno", None),
                "mentioned": mentioned,
                "source": ast.get_source_segment(text, node) or "",
            })

    report = {
        "desktop": DESKTOP.name,
        "target_count": len(records),
        "total_target_lines": sum(int(item["lines"]) for item in records),
        "targets": records,
        "usage": usage,
        "existing_in_ui_controls": existing,
        "assignments": sorted(assignments, key=lambda item: int(item["lineno"] or 0)),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "target_count": report["target_count"],
        "total_target_lines": report["total_target_lines"],
        "target_names": list(TARGETS),
        "usage": usage,
    }, ensure_ascii=True))


if __name__ == "__main__":
    main()
