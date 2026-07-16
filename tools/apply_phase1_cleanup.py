#!/usr/bin/env python3
"""Apply the first low-risk SPINA redundancy cleanup.

This script only replaces top-level functions whose AST bodies and signatures are
identical with aliases to the earlier canonical helper. It refuses to edit when
that invariant is not true.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

APP = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
DOC = Path("docs/redundancy-audit.md")
SELF = Path("tools/apply_phase1_cleanup.py")
WORKFLOW = Path(".github/workflows/phase1-cleanup.yml")

ALIASES = {
    "_spina_restore_row_to_dict": (
        "_spina_archive_row_to_dict",
        "identical implementation shared with archive conversion",
    ),
    "_spina_v20_money": (
        "_spina_v18_fmt_money_compact",
        "use the existing compact money formatter",
    ),
    "_spina_v21_cash_money_short": (
        "_spina_v18_fmt_money_compact",
        "use the existing compact money formatter",
    ),
    "_spina_v21_cash_round_rect": (
        "_spina_v20_round_rect",
        "use the existing rounded-rectangle helper",
    ),
    "_spina_v23_clients_colors": (
        "_spina_v22_reports_colors",
        "reports and clients use the same theme palette",
    ),
    "_spina_v27_route_colors": (
        "_spina_v25_collector_colors",
        "collector overview and route editor use the same palette",
    ),
}


def normalized_hash(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    clone = ast.FunctionDef(
        name="_",
        args=node.args,
        body=node.body,
        decorator_list=[],
        returns=node.returns,
        type_comment=getattr(node, "type_comment", None),
    )
    return hashlib.sha256(
        ast.dump(clone, include_attributes=False).encode("utf-8")
    ).hexdigest()


def main() -> None:
    source = APP.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(APP))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    replacements: list[tuple[int, int, str]] = []
    for duplicate, (canonical, reason) in ALIASES.items():
        duplicate_node = functions.get(duplicate)
        canonical_node = functions.get(canonical)
        if duplicate_node is None or canonical_node is None:
            raise RuntimeError(f"Missing helper: {duplicate} or {canonical}")
        if canonical_node.lineno >= duplicate_node.lineno:
            raise RuntimeError(f"Canonical helper must appear first: {canonical}")
        if normalized_hash(duplicate_node) != normalized_hash(canonical_node):
            raise RuntimeError(
                f"Refusing cleanup because implementations differ: "
                f"{duplicate} and {canonical}"
            )
        replacement = (
            f"# Phase 1 cleanup: {reason}.\n"
            f"{duplicate} = {canonical}\n"
        )
        replacements.append(
            (duplicate_node.lineno, duplicate_node.end_lineno or duplicate_node.lineno, replacement)
        )

    lines = source.splitlines(keepends=True)
    for start, end, replacement in sorted(replacements, reverse=True):
        lines[start - 1 : end] = replacement.splitlines(keepends=True)
    updated = "".join(lines)

    compile(updated, str(APP), "exec")
    updated_tree = ast.parse(updated, filename=str(APP))
    remaining_names = {
        node.name
        for node in updated_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    still_defined = sorted(set(ALIASES) & remaining_names)
    if still_defined:
        raise RuntimeError(f"Duplicate definitions were not removed: {still_defined}")

    APP.write_text(updated, encoding="utf-8")

    heading = "## Phase 1 cleanup completed"
    doc = DOC.read_text(encoding="utf-8")
    if heading not in doc:
        doc += f"""

{heading}

The first behavioral-neutral cleanup consolidates six exact duplicate helper
definitions by keeping their public/internal names as aliases:

- archive/restore row conversion
- the v18, v20, and v21 compact money formatter names
- the v20 and v21 rounded-rectangle helper names
- the v22 reports and v23 clients palette names
- the v25 collector and v27 route palette names

The alias targets occur earlier in the module and had identical signatures and
AST bodies before replacement. No call sites or displayed output were changed.
The application is compiled and the redundancy audit is run in CI before the
cleanup commit is pushed.
"""
        DOC.write_text(doc, encoding="utf-8")

    # These files are temporary implementation machinery. Removing them keeps
    # the final pull-request diff focused on the app and audit documentation.
    SELF.unlink(missing_ok=True)
    WORKFLOW.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
