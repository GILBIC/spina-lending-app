"""Rank larger low-risk modularization batches for SPINA Wave 26.

This tool is read-only. It parses the giant desktop module, identifies top-level
presentation/support helpers with no obvious database, finance, authentication,
report, backup, or filesystem behavior, and proposes cohesive 150-400 line
batches. The report includes exact hashes, callers, dependencies, and source text
so the selected batch can be guarded and extracted on the same branch.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
OUTPUT = Path("high-volume-wave-26-inventory.json")
EXPECTED_BASE = "a44ccc6c0e5181e4eed36453df540b70974c0679"

BLOCKED_NAME_TERMS = {
    "payment", "balance", "principal", "interest", "renew", "renewal", "offset",
    "7x7", "loan", "transaction", "ledger", "advance", "pass", "due", "collection",
    "database", "postgres", "sqlite", "sql", "cursor", "backup", "restore", "migration",
    "password", "login", "auth", "permission", "role", "session", "account",
    "report", "pdf", "receipt", "statement", "excel", "import", "export", "print",
    "payroll", "salary", "sss", "pagibig", "philhealth", "tax", "gcash",
}

BLOCKED_CALL_NAMES = {
    "open", "exec", "eval", "compile", "__import__", "input",
    "connect", "cursor", "execute", "executemany", "commit", "rollback",
    "remove", "unlink", "rename", "replace", "rmtree", "copy", "copy2", "move",
    "dump", "dumps", "load", "loads", "write", "write_text", "write_bytes",
    "read_text", "read_bytes", "save", "savefig", "subprocess", "system", "popen",
    "urlopen", "request", "get", "post", "put", "delete",
}

BLOCKED_ATTRIBUTE_TERMS = {
    "execute", "executemany", "commit", "rollback", "cursor", "connection",
    "write_text", "write_bytes", "unlink", "rename", "replace", "mkdir", "rmdir",
    "save", "savefig", "export", "print", "backup", "restore",
}

PRESENTATION_CALLS = {
    "Frame", "Label", "Button", "Entry", "Text", "Canvas", "Scrollbar", "Toplevel",
    "LabelFrame", "Combobox", "Treeview", "Notebook", "PanedWindow", "Separator",
    "Checkbutton", "Radiobutton", "Spinbox", "Listbox", "Menu", "PhotoImage",
    "StringVar", "BooleanVar", "IntVar", "DoubleVar",
    "grid", "pack", "place", "configure", "config", "bind", "unbind", "heading",
    "column", "tag_configure", "selection_set", "selection_remove", "focus", "focus_set",
    "see", "insert", "delete", "set", "get", "after", "after_idle", "update_idletasks",
}

FEATURE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("dashboard", ("dashboard", "dash_", "kpi", "summary_card")),
    ("clients", ("client", "borrower", "application_form")),
    ("collectors", ("collector", "route")),
    ("data_bank", ("data_bank", "databank", "payment_grid", "monthly_grid")),
    ("cash_control", ("cash_control", "cashcontrol", "cash_")),
    ("payroll", ("payroll", "employee", "payslip")),
    ("reports", ("report", "statement", "receipt", "pdf")),
    ("maintenance", ("maintenance", "settings", "theme", "appearance")),
    ("navigation", ("sidebar", "tab", "navigation", "nav_")),
    ("dialogs", ("dialog", "modal", "popup", "prompt", "message")),
    ("generic_ui", ("card", "button", "label", "tree", "style", "palette", "color")),
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_for(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def dotted_name(node: ast.AST) -> str:
    parts: list[str] = []
    current: ast.AST | None = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def infer_feature(name: str, source: str) -> str:
    haystack = f"{name}\n{source[:1500]}".lower()
    for feature, terms in FEATURE_KEYWORDS:
        if any(term in haystack for term in terms):
            return feature
    return "other"


def function_facts(
    name: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    source: str,
    top_names: set[str],
) -> dict[str, Any]:
    args = {
        arg.arg
        for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    }
    if node.args.vararg:
        args.add(node.args.vararg.arg)
    if node.args.kwarg:
        args.add(node.args.kwarg.arg)

    assigned: set[str] = set()
    loaded: set[str] = set()
    calls: set[str] = set()
    attributes: set[str] = set()
    presentation_hits: list[str] = []
    literal_text: list[str] = []

    for child in ast.walk(node):
        if isinstance(child, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            targets: list[ast.AST] = []
            if isinstance(child, ast.Assign):
                targets.extend(child.targets)
            else:
                targets.append(child.target)
            for target in targets:
                for sub in ast.walk(target):
                    if isinstance(sub, ast.Name):
                        assigned.add(sub.id)
        elif isinstance(child, (ast.For, ast.AsyncFor)):
            for sub in ast.walk(child.target):
                if isinstance(sub, ast.Name):
                    assigned.add(sub.id)
        elif isinstance(child, (ast.With, ast.AsyncWith)):
            for item in child.items:
                if item.optional_vars:
                    for sub in ast.walk(item.optional_vars):
                        if isinstance(sub, ast.Name):
                            assigned.add(sub.id)
        elif isinstance(child, ast.comprehension):
            for sub in ast.walk(child.target):
                if isinstance(sub, ast.Name):
                    assigned.add(sub.id)
        elif isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
            loaded.add(child.id)
        elif isinstance(child, ast.Attribute):
            attributes.add(child.attr)
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            literal_text.append(child.value)

        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                call_name = child.func.id
            else:
                call_name = dotted_name(child.func)
            if call_name:
                calls.add(call_name)
                leaf = call_name.rsplit(".", 1)[-1]
                if leaf in PRESENTATION_CALLS:
                    presentation_hits.append(call_name)

    dependencies = sorted((loaded - args - assigned) & top_names - {name})
    called_top_level = sorted({call.rsplit(".", 1)[-1] for call in calls} & top_names - {name})

    name_lower = name.lower()
    source_lower = source.lower()
    blocked_name_hits = sorted(term for term in BLOCKED_NAME_TERMS if term in name_lower)
    blocked_source_hits = sorted(
        term for term in BLOCKED_NAME_TERMS
        if term in source_lower and term not in {"client", "collector"}
    )
    blocked_call_hits = sorted(
        call for call in calls
        if call.rsplit(".", 1)[-1].lower() in BLOCKED_CALL_NAMES
    )
    blocked_attribute_hits = sorted(attr for attr in attributes if attr.lower() in BLOCKED_ATTRIBUTE_TERMS)

    ui_score = len(set(presentation_hits))
    line_count = int(node.end_lineno - node.lineno + 1)
    has_yield = any(isinstance(child, (ast.Yield, ast.YieldFrom)) for child in ast.walk(node))
    has_async = isinstance(node, ast.AsyncFunctionDef) or any(
        isinstance(child, (ast.Await, ast.AsyncFor, ast.AsyncWith)) for child in ast.walk(node)
    )
    has_global = any(isinstance(child, (ast.Global, ast.Nonlocal)) for child in ast.walk(node))

    risk_flags: list[str] = []
    if blocked_name_hits:
        risk_flags.append("blocked-name")
    if blocked_source_hits:
        risk_flags.append("blocked-source")
    if blocked_call_hits:
        risk_flags.append("blocked-call")
    if blocked_attribute_hits:
        risk_flags.append("blocked-attribute")
    if has_yield:
        risk_flags.append("generator")
    if has_async:
        risk_flags.append("async")
    if has_global:
        risk_flags.append("global-state")
    if line_count > 180:
        risk_flags.append("oversized")

    low_risk = (
        not risk_flags
        and line_count <= 180
        and (ui_score >= 2 or line_count <= 25)
        and not any(re.search(r"(?i)(error|exception|traceback|failed)", text) for text in literal_text)
    )

    return {
        "name": name,
        "start_line": node.lineno,
        "end_line": node.end_lineno,
        "line_count": line_count,
        "sha256": sha256_text(source),
        "feature": infer_feature(name, source),
        "dependencies": dependencies,
        "called_top_level": called_top_level,
        "all_calls": sorted(calls),
        "presentation_hits": sorted(set(presentation_hits)),
        "presentation_score": ui_score,
        "risk_flags": risk_flags,
        "blocked_name_hits": blocked_name_hits,
        "blocked_source_hits": blocked_source_hits,
        "blocked_call_hits": blocked_call_hits,
        "blocked_attribute_hits": blocked_attribute_hits,
        "low_risk": low_risk,
        "source": source,
    }


def build_batches(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        grouped[item["feature"]].append(item)

    suggestions: list[dict[str, Any]] = []
    for feature, items in grouped.items():
        items.sort(key=lambda item: item["start_line"])
        for start in range(len(items)):
            total = 0
            names: list[str] = []
            selected: list[dict[str, Any]] = []
            for end in range(start, min(len(items), start + 12)):
                item = items[end]
                total += item["line_count"]
                names.append(item["name"])
                selected.append(item)
                if len(selected) < 5:
                    continue
                if 150 <= total <= 400:
                    spread = selected[-1]["end_line"] - selected[0]["start_line"] + 1
                    dependency_count = len({dep for row in selected for dep in row["dependencies"]})
                    top_calls = len({dep for row in selected for dep in row["called_top_level"]})
                    presentation = sum(row["presentation_score"] for row in selected)
                    score = presentation * 4 + len(selected) * 12 - dependency_count * 3 - top_calls * 2
                    score -= max(0, spread - total) / 50
                    suggestions.append(
                        {
                            "feature": feature,
                            "function_count": len(selected),
                            "line_count": total,
                            "start_line": selected[0]["start_line"],
                            "end_line": selected[-1]["end_line"],
                            "source_spread": spread,
                            "score": round(score, 2),
                            "functions": names.copy(),
                            "external_dependencies": sorted(
                                {dep for row in selected for dep in row["dependencies"] if dep not in names}
                            ),
                            "external_top_level_calls": sorted(
                                {dep for row in selected for dep in row["called_top_level"] if dep not in names}
                            ),
                        }
                    )
                if total > 400:
                    break

    suggestions.sort(key=lambda row: (-row["score"], abs(260 - row["line_count"]), row["source_spread"]))
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for row in suggestions:
        key = tuple(row["functions"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
        if len(unique) >= 30:
            break
    return unique


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Missing source: {SOURCE}")

    base_sha = git_output("rev-parse", "origin/main")
    if base_sha != EXPECTED_BASE:
        raise SystemExit(f"Unexpected origin/main: {base_sha}")

    changed = {
        line.strip().replace("\\", "/")
        for line in git_output("diff", "--name-only", "origin/main...HEAD").splitlines()
        if line.strip()
    }
    allowed = {
        ".github/workflows/high-volume-wave-26-inventory.yml",
        "tools/inventory_high_volume_wave_26.py",
    }
    unexpected = changed - allowed
    if unexpected:
        raise SystemExit(f"Inventory branch contains unexpected files: {sorted(unexpected)}")

    text = SOURCE.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(SOURCE))
    nodes = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    top_names = set(nodes)

    facts: dict[str, dict[str, Any]] = {}
    for name, node in nodes.items():
        source = source_for(lines, node)
        facts[name] = function_facts(name, node, source, top_names)

    callers: dict[str, list[str]] = defaultdict(list)
    for caller_name, row in facts.items():
        for called in row["called_top_level"]:
            callers[called].append(caller_name)
        for dependency in row["dependencies"]:
            callers[dependency].append(caller_name)

    for name, row in facts.items():
        row["callers"] = sorted(set(callers.get(name, [])))

    low_risk = [row for row in facts.values() if row["low_risk"]]
    low_risk.sort(key=lambda row: (row["feature"], row["start_line"]))
    batches = build_batches(low_risk)

    report = {
        "source": str(SOURCE),
        "source_sha256": sha256_text(text),
        "base_sha": base_sha,
        "branch_sha": git_output("rev-parse", "HEAD"),
        "top_level_function_count": len(nodes),
        "low_risk_candidate_count": len(low_risk),
        "target_batch_range": {"minimum_lines": 150, "maximum_lines": 400, "minimum_functions": 5, "maximum_functions": 12},
        "suggested_batches": batches,
        "low_risk_candidates": low_risk,
        "excluded_summary": {
            flag: sum(flag in row["risk_flags"] for row in facts.values())
            for flag in sorted({flag for row in facts.values() for flag in row["risk_flags"]})
        },
    }
    OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "source_sha256": report["source_sha256"],
        "top_level_function_count": report["top_level_function_count"],
        "low_risk_candidate_count": report["low_risk_candidate_count"],
        "suggested_batch_count": len(batches),
        "top_batches": batches[:8],
    }, indent=2))


if __name__ == "__main__":
    main()
