from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave-50-legacy-collector-boundary.json"

LEGACY = (
    "_spina_v25_collector_button",
    "_spina_v25_build_collectors_tab",
)
ACTIVE = "_spina_v27_build_collectors_tab"
EXPECTED_HASHES = {
    "_spina_v25_collector_button": "f122f949ef4a355ec83dfa5942874f408ef3ea5fb186ad4740827df8c56eb613",
    "_spina_v25_build_collectors_tab": "f5b787f580fd4202ebbc324e70da4a8c2adee5190e959c3af01b0e2402b32e92",
}


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def normalized_hash(source: str) -> str:
    normalized = "\n".join(line.rstrip() for line in source.strip().splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def function_record(text: str, node: ast.FunctionDef) -> dict[str, object]:
    source = ast.get_source_segment(text, node) or ""
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
    tree = ast.parse(text)

    functions: dict[str, list[ast.FunctionDef]] = {name: [] for name in (*LEGACY, ACTIVE)}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in functions:
            functions[node.name].append(node)

    legacy_records = []
    for name in LEGACY:
        matches = functions[name]
        assert len(matches) == 1, (name, len(matches))
        record = function_record(text, matches[0])
        assert record["sha256"] == EXPECTED_HASHES[name], (name, record["sha256"])
        legacy_records.append(record)

    active_records = [function_record(text, node) for node in functions[ACTIVE]]

    name_loads: dict[str, list[dict[str, object]]] = {name: [] for name in LEGACY}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Name) or not isinstance(node.ctx, ast.Load):
            continue
        if node.id not in name_loads:
            continue
        owner = None
        for candidate in ast.walk(tree):
            if isinstance(candidate, ast.FunctionDef):
                if candidate.lineno <= node.lineno <= (candidate.end_lineno or candidate.lineno):
                    if owner is None or candidate.lineno >= owner.lineno:
                        owner = candidate
        name_loads[node.id].append({
            "lineno": node.lineno,
            "owner_function": owner.name if owner is not None else None,
        })

    assignments = []
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            source = ast.get_source_segment(text, node) or ""
            if any(name in source for name in (*LEGACY, ACTIVE)) or "App._build_collectors_tab" in source:
                assignments.append({
                    "lineno": node.lineno,
                    "source": source,
                })
        elif isinstance(node, ast.ImportFrom):
            imported = {alias.name for alias in node.names}
            if ACTIVE in imported or any(name in imported for name in LEGACY):
                imports.append({
                    "lineno": node.lineno,
                    "module": node.module,
                    "names": [
                        {"name": alias.name, "asname": alias.asname}
                        for alias in node.names
                    ],
                    "source": ast.get_source_segment(text, node) or "",
                })

    build_bindings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "App"
            and target.attr == "_build_collectors_tab"
        ):
            continue
        build_bindings.append({
            "lineno": node.lineno,
            "rhs": ast.unparse(node.value),
            "source": ast.get_source_segment(text, node) or "",
        })
    build_bindings.sort(key=lambda item: int(item["lineno"]))

    report = {
        "desktop": DESKTOP.name,
        "legacy_total_lines": sum(int(item["lines"]) for item in legacy_records),
        "legacy": legacy_records,
        "active_records": active_records,
        "name_loads": name_loads,
        "assignments": sorted(assignments, key=lambda item: int(item["lineno"])),
        "imports": sorted(imports, key=lambda item: int(item["lineno"])),
        "build_bindings": build_bindings,
        "final_build_binding": build_bindings[-1] if build_bindings else None,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "legacy_total_lines": report["legacy_total_lines"],
        "name_loads": name_loads,
        "build_bindings": build_bindings,
        "final_build_binding": report["final_build_binding"],
    }, ensure_ascii=True))


if __name__ == "__main__":
    main()
