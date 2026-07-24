from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

MAIN = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
OUT = Path("artifacts/clients-wave-19-guard.json")
SELECTED = [
    "_spina_v23_button",
    "_spina_v23_card",
    "_spina_v23_selected_name_lt",
    "_spina_v23_refresh_client_profile",
    "_spina_v23_build_clients_tab",
    "_spina_v23_entry",
    "_spina_v23_update_client_cards",
]
EXPECTED = {
    "_spina_v23_button": "6494efce07479ceb08d40d3e4915e6d935a34bd142d484ab02fa2779256ba8f5",
    "_spina_v23_card": "8f652d54bfffe6bba7a6173661f52ffb586428f65c31ee0dca18755a78945119",
    "_spina_v23_selected_name_lt": "d8b06aec702eff2fba8a64e2f5cde9b5abad2547285ef5b2012a961d019aad9c",
    "_spina_v23_refresh_client_profile": "18a4893cb4cc8c08996e9e4c85d0d0ccc39a213a8246591af9fefa76c44d51a3",
    "_spina_v23_build_clients_tab": "9fd162cf2011af50b77a590e6494d1dd3fe118b3045b252f0b73e2d859a6aa47",
    "_spina_v23_entry": "7616aaf2e0dbea43205b394953ebe1098107abccc6074f99275eedff09b96949",
    "_spina_v23_update_client_cards": "d5557fe858d777ca046c6089432257596abd9d66615dba06bb737192bc2e98d5",
}

text = MAIN.read_text(encoding="utf-8")
lines = text.splitlines()
tree = ast.parse(text)
by_name = {}
for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        by_name.setdefault(node.name, []).append(node)

report = []
for name in SELECTED:
    nodes = by_name.get(name, [])
    item = {"name": name, "occurrences": len(nodes), "expected_sha256": EXPECTED[name]}
    if len(nodes) == 1:
        node = nodes[0]
        source = "\n".join(lines[node.lineno - 1 : node.end_lineno])
        actual = hashlib.sha256(source.encode("utf-8")).hexdigest()
        item.update({
            "start_line": node.lineno,
            "end_line": node.end_lineno,
            "source_lines": node.end_lineno - node.lineno + 1,
            "actual_sha256": actual,
            "matches": actual == EXPECTED[name],
            "source": source,
        })
    report.append(item)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(OUT)
