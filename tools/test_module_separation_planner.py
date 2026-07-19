#!/usr/bin/env python3
"""Static smoke checks for the module-separation planner."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from plan_module_separation import build_report


SAMPLE = '''\
import json
import tkinter as tk

APP_DIR = "."
SETTING = 1


def format_label(value):
    return str(value).strip()


def save_payment(cursor, amount):
    cursor.execute("INSERT INTO payments(amount) VALUES (?)", (amount,))


class App:
    def __init__(self, root):
        self.root = root
        root.title("Sample")
'''


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "sample.py"
        path.write_text(SAMPLE, encoding="utf-8")
        report = build_report(path)

    assert report["selected_move_candidate_count"] == 0
    assert report["safety"]["read_only"] is True
    assert report["safety"]["app_source_modified"] is False
    assert report["top_level_function_count"] == 2
    assert report["top_level_class_count"] == 1
    names = {item["name"] for item in report["definitions"]}
    assert names == {"format_label", "save_payment", "App"}
    payment = next(item for item in report["definitions"] if item["name"] == "save_payment")
    assert payment["protected_or_business_critical"] is True
    assert "database" in payment["dependency_signals"]
    json.dumps(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
