#!/usr/bin/env python3
"""Regression checks for the extracted fmt_currency utility."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spina_app.utilities.formatting import fmt_currency

APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
IMPORT_LINE = "from spina_app.utilities.formatting import fmt_currency"
CASES = [None, 0, 1, 1234.5, -42.75, '1000', 'bad', '']
EXPECTED = [{'kind': 'return', 'repr': "'PHP 0.00'"}, {'kind': 'return', 'repr': "'PHP 0.00'"}, {'kind': 'return', 'repr': "'PHP 1.00'"}, {'kind': 'return', 'repr': "'PHP 1,234.50'"}, {'kind': 'return', 'repr': "'PHP -42.75'"}, {'kind': 'return', 'repr': "'PHP 1,000.00'"}, {'kind': 'return', 'repr': "'PHP 0.00'"}, {'kind': 'return', 'repr': "'PHP 0.00'"}]


def _capture(value):
    try:
        return {"kind": "return", "repr": repr(fmt_currency(value))}
    except Exception as exc:
        return {
  "kind": "raise",
  "type": type(exc).__name__,
  "message": str(exc),
        }


def main() -> int:
    source = (REPO_ROOT / APP_FILE).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert IMPORT_LINE in source
    assert not any(
        isinstance(node, ast.FunctionDef) and node.name == "fmt_currency"
        for node in tree.body
    )
    assert [_capture(value) for value in CASES] == EXPECTED
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
