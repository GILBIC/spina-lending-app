from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave-49-databank-presentation-boundary.json"

TARGETS = (
    "_spina_v15_palette",
    "_spina_v15_setup_databank_styles",
    "_spina_v15_stat_card",
    "_spina_v15_build_data_tab",
    "_spina_v15_update_databank_cards",
    "_spina_v15_refresh_data_grid",
    "_spina_v15_update_data_toolbar",
    "_spina_v15_apply_ui_theme",
    "_spina_v16_apply_bigger_payment_grid",
    "_spina_v16_refresh_data_grid",
)
CAPTURES = (
    "_spina_v15_orig_refresh_data_grid",
    "_spina_v15_orig_update_data_toolbar",
    "_spina_v15_orig_apply_theme",
    "_spina_v16_prev_refresh_data_grid",
)
PROTECTED_NEIGHBORS = ("_spina_v17_on_mode_change",)


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def source_for(lines: list[str], node: ast.AST) -> str:
    end = getattr(node, "end_lineno", None) or node.lineno
    return "\n".join(lines[node.lineno - 1:end])


def normalized_hash(source: str) -> str:
    normalized = "\n".join(line.rstrip() for line in source.strip().splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def function_record(lines: list[str], node: ast.FunctionDef) -> dict[str, object]:
    source = source_for(lines, node)
    return {
        "name": node.name,
        "lineno": node.lineno,
        "end_lineno": node.end_lineno,
        "lines": (node.end_lineno or node.lineno) - node.lineno + 1,
        "signature": ast.unparse(node.args),
        "sha256": normalized_hash(source),
        "calls": sorted({
            dotted(call.func)
            for call in ast.walk(node)
            if isinstance(call, ast.Call) and dotted(call.func)
        }),
        "source": source,
    }


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text)

    functions: dict[str, list[ast.FunctionDef]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions.setdefault(node.name, []).append(node)

    targets = []
    for name in TARGETS:
        matches = functions.get(name, [])
        assert len(matches) == 1, (name, len(matches))
        targets.append(function_record(lines, matches[0]))

    neighbors = []
    for name in PROTECTED_NEIGHBORS:
        matches = functions.get(name, [])
        assert len(matches) == 1, (name, len(matches))
        neighbors.append(function_record(lines, matches[0]))

    watched = set(TARGETS) | set(CAPTURES)
    assignments = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        names = {
            part.id for part in ast.walk(node)
            if isinstance(part, ast.Name) and part.id in watched
        }
        app_attrs = sorted({
            part.attr for part in ast.walk(node)
            if isinstance(part, ast.Attribute)
            and isinstance(part.value, ast.Name)
            and part.value.id == "App"
            and part.attr in {
                "_build_data_tab", "_setup_databank_styles",
                "_update_databank_summary_cards", "refresh_data_grid",
                "_update_data_toolbar", "_apply_ui_theme",
            }
        })
        if not names and not app_attrs:
            continue
        assignments.append({
            "lineno": getattr(node, "lineno", None),
            "names": sorted(names),
            "app_attrs": app_attrs,
            "source": source_for(lines, node),
        })

    report = {
        "desktop": DESKTOP.name,
        "target_count": len(targets),
        "total_target_lines": sum(int(item["lines"]) for item in targets),
        "targets": targets,
        "captures": list(CAPTURES),
        "protected_neighbors": neighbors,
        "assignments": sorted(assignments, key=lambda item: int(item["lineno"] or 0)),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "target_count": report["target_count"],
        "total_target_lines": report["total_target_lines"],
        "target_names": list(TARGETS),
        "assignment_count": len(assignments),
    }, ensure_ascii=True))


if __name__ == "__main__":
    main()
