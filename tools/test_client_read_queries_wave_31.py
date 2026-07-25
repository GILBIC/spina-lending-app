from __future__ import annotations

import ast
import hashlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "client_queries.py"
TARGETS = ('get_all_clients', 'get_client_info', 'get_client_link_meta', 'find_clients_by_person_uid', 'get_client_uid', 'get_client_by_uid', 'get_client_history', 'get_person_uid_for_client_uid')
EXPECTED_SHA256 = {'get_all_clients': 'b17c794fb32b23ce1f1bc123ec8c6a12ae14649c57f6b1d1c4d9b8c92a302764', 'get_client_info': 'ee7fe970ef0a989a9cf9b24454caaccee1395ef98d1a37eca4253bf53b7b3798', 'get_client_link_meta': 'ab15065272cd8aeb8ee58cec1a0e878a53a9baceaf5d36a622b38c14378bfe4d', 'find_clients_by_person_uid': '853d18b473c58c7a267139b9f32c9512860bccabb2839a14fa9a80319b8392ea', 'get_client_uid': '2259282ec01dce8bf5efe8b555b8bc69836a8858786ffe0ef9fbf29666733bd1', 'get_client_by_uid': '47fdc53527a5c617c6e38462c31e6f4ff6cafd1e4dd52c9189a897f595a37d52', 'get_client_history': '8fc2038a3fe26c01399802fe4e91fc35b0263b46b83f14ca4d0f3c27b3f02418', 'get_person_uid_for_client_uid': 'dc102ae9f96de61a26cb5b161f9430bfd248a0e921d555ae9e67bbbf97b9d14c'}
EXPECTED_TOTAL_LINES = 423


def normalized_source(text: str) -> str:
    return textwrap.dedent(text).strip() + "\n"


def source_hash(text: str) -> str:
    return hashlib.sha256(normalized_source(text).encode("utf-8")).hexdigest()


def direct_functions(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def main() -> None:
    module_text = MODULE.read_text(encoding="utf-8")
    module_tree = ast.parse(module_text, filename=str(MODULE))
    functions = direct_functions(module_tree)

    missing = [name for name in TARGETS if name not in functions]
    assert not missing, f"Missing extracted functions: {missing}"

    actual_total = 0
    for name in TARGETS:
        node = functions[name]
        segment = ast.get_source_segment(module_text, node)
        assert segment is not None
        actual = source_hash(segment)
        assert actual == EXPECTED_SHA256[name], (name, actual, EXPECTED_SHA256[name])
        actual_total += (node.end_lineno or node.lineno) - node.lineno + 1
    assert actual_total == EXPECTED_TOTAL_LINES, (actual_total, EXPECTED_TOTAL_LINES)

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text, filename=str(DESKTOP))
    loandb = next(
        node for node in desktop_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "LoanDB"
    )
    remaining = {
        node.name for node in loandb.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert not (set(TARGETS) & remaining), set(TARGETS) & remaining

    class_end = loandb.end_lineno or loandb.lineno
    wiring_positions = []
    for node in ast.walk(desktop_tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "LoanDB"
            and target.attr in TARGETS
        ):
            wiring_positions.append((target.attr, node.lineno))
    assert {name for name, _ in wiring_positions} == set(TARGETS)
    assert all(line > class_end for _, line in wiring_positions)

    forbidden_sql = (
        "INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE",
        "ALTER TABLE", "DROP TABLE",
    )
    forbidden_calls = (
        ".commit(", ".rollback(", "write_text(", "write_bytes(",
        ".unlink(", ".replace(",
    )
    for name in TARGETS:
        segment = ast.get_source_segment(module_text, functions[name]) or ""
        upper = segment.upper()
        for token in forbidden_sql:
            assert token not in upper, (name, token)
        for token in forbidden_calls:
            assert token not in segment, (name, token)

    print(
        f"Wave 31 client read-query regression passed: "
        f"{len(TARGETS)} methods / {EXPECTED_TOTAL_LINES} lines."
    )


if __name__ == "__main__":
    main()
