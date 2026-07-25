from __future__ import annotations

import ast
import hashlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "linked_client_queries.py"
TARGETS = ('get_linked_client_uids', 'get_transaction_history_for_client_uids', 'get_transactions_for_client_uids', 'count_clients_in_area', 'get_client_by_person_uid_and_loan_type', 'get_transactions_for_client')
EXPECTED_SHA256 = {'get_linked_client_uids': 'bbc95ceef6181ec1e0b87aa6514d012e5f1913d114f880626c0a400c148a9f3c', 'get_transaction_history_for_client_uids': 'd2bf907b3da9b8af154e3e08ad878c52d6a195b7673afd29d0bf095613315995', 'get_transactions_for_client_uids': '81f1e6394a4222d2bbaea71172f7b4b2a23632bd82180c36ee80caa26818734f', 'count_clients_in_area': '56dac6dbd2ba92fdc6b1b4d08f8db6c139207e50fe4061f55ba70e9e25d85b2f', 'get_client_by_person_uid_and_loan_type': '512bb4723957fd90afe16678ee5415f75c3b08ebdd4e87a5743ab61353081f11', 'get_transactions_for_client': '2b8757250b6822f00fd37d8221653cbc08b02882c8e0aa2523343408986a713f'}
EXPECTED_TOTAL_LINES = 203


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
        f"Wave 32 linked-client read-query regression passed: "
        f"{len(TARGETS)} methods / {EXPECTED_TOTAL_LINES} lines."
    )


if __name__ == "__main__":
    main()
