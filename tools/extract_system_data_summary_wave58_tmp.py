from __future__ import annotations

import ast
import codecs
import hashlib
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "system_data_summary_presentation.py"
EXACT_TEST = ROOT / "tools" / "test_system_data_summary_presentation_wave_58.py"
WIDGET_TEST = ROOT / "tools" / "test_system_data_summary_widget_smoke_wave_58.py"
REPORT = ROOT / "artifacts" / "wave-58-system-data-summary-extraction.json"
TARGET_CLASS = "App"
TARGETS = {
    "_system_data_get_date": {
        "lines": 19,
        "sha256": "a6f3be4ac524d5375eb4520575cbdc0e853bb42b8ad74667d174a0b49316074d",
        "signature": "self",
        "calls": [
            "_dt.strptime", "messagebox.showerror", "self._get_databank_focus_date",
            "self.system_data_date_var.get", "self.system_data_date_var.set",
            "strftime", "strip",
        ],
    },
    "_system_data_use_focus_date": {
        "lines": 8,
        "sha256": "6c876f3607fc9b123f3be3f2af15a5157941c7208c36e2e339d0745dd134bb24",
        "signature": "self",
        "calls": [
            "_log_suppressed_once", "self._get_databank_focus_date",
            "self.system_data_date_var.set", "strip",
        ],
    },
    "_system_data_refresh_summary": {
        "lines": 60,
        "sha256": "cc5a02d884b2c30fba6f5be3f8c1424fc4e66e1e4f2f250d96661dba421313c7",
        "signature": "self",
        "calls": [
            "_fmt_amt", "abs", "bool", "float", "fmt_currency", "hasattr",
            "int", "rec.get", "round", "self._system_data_get_date",
            "self.db.get_databank_daily_total", "self.db.get_databank_day_close",
            "self.system_data_summary_var.set", "strip",
        ],
    },
}
PROTECTED_MARKERS = (
    ".execute", ".executemany", ".commit", ".rollback",
    "set_databank_day_close", "replace_databank_day_collectors",
    "delete_transactions_for_day", "delete_transaction",
    "add_or_update_transaction", "close_day", "reopen_day", "backup",
    "restore", "password", "print_databank_close_report", "write_text",
    "write_bytes", "unlink",
)


def dotted(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def find_targets(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == TARGET_CLASS:
            found = {
                child.name: child
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and child.name in TARGETS
            }
            missing = sorted(set(TARGETS) - set(found))
            if missing:
                raise SystemExit(f"Missing Wave 58 target methods: {missing}")
            return found
    raise SystemExit(f"Missing class {TARGET_CLASS}")


def render_module(dedented_sources: dict[str, str], metadata: dict[str, dict[str, object]]) -> str:
    protected = {
        "__name__", "__file__", "__package__", "__loader__", "__spec__",
        "__builtins__", "__cached__", "__doc__",
        "_SYSTEM_DATA_SUMMARY_DEPENDENCIES", "_PROTECTED_GLOBALS",
        "configure_system_data_summary_dependencies",
        "SYSTEM_DATA_SUMMARY_PRESENTATION_METHODS",
        *TARGETS,
    }
    lines = [
        '"""System Data date and summary helpers extracted in Wave 58."""',
        "from __future__ import annotations",
        "",
        "_SYSTEM_DATA_SUMMARY_DEPENDENCIES = {}",
        f"_PROTECTED_GLOBALS = {protected!r}",
        "",
        "def configure_system_data_summary_dependencies(namespace):",
        "    _SYSTEM_DATA_SUMMARY_DEPENDENCIES.clear()",
        "    _SYSTEM_DATA_SUMMARY_DEPENDENCIES.update(namespace)",
        "    for name, value in namespace.items():",
        "        if name not in _PROTECTED_GLOBALS:",
        "            globals()[name] = value",
        "",
        f"SYSTEM_DATA_SUMMARY_PRESENTATION_METHODS = {metadata!r}",
        "",
    ]
    for name in TARGETS:
        lines.extend([dedented_sources[name].rstrip(), ""])
    return "\n".join(lines)


def render_exact_test(metadata: dict[str, dict[str, object]]) -> str:
    expected = {
        name: {
            "lines": TARGETS[name]["lines"],
            "source_sha256": TARGETS[name]["sha256"],
            "dedented_sha256": metadata[name]["dedented_sha256"],
            "signature": TARGETS[name]["signature"],
            "calls": TARGETS[name]["calls"],
            "db_calls": metadata[name]["db_calls"],
        }
        for name in TARGETS
    }
    return f'''"""Exact-source regression for Wave 58 System Data summary helpers."""
from __future__ import annotations

import ast
import hashlib
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
EXPECTED = {expected!r}
PROTECTED_MARKERS = {PROTECTED_MARKERS!r}


def dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def main() -> None:
    import spina_app.system_data_summary_presentation as module

    assert module.SYSTEM_DATA_SUMMARY_PRESENTATION_METHODS == EXPECTED
    app_text = APP.read_text(encoding="utf-8-sig")
    app_tree = ast.parse(app_text, filename=str(APP))
    app_class = next(node for node in app_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    remaining = {{child.name for child in app_class.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))}}

    for name, expected in EXPECTED.items():
        assert name not in remaining
        function = getattr(module, name)
        source = inspect.getsource(function)
        assert len(source.splitlines()) == expected["lines"]
        assert hashlib.sha256(source.encode("utf-8")).hexdigest() == expected["dedented_sha256"]
        node = ast.parse(source).body[0]
        assert ast.unparse(node.args) == expected["signature"]
        calls = sorted({{dotted(call.func) for call in ast.walk(node) if isinstance(call, ast.Call) and dotted(call.func)}})
        assert calls == expected["calls"]
        assert [call for call in calls if call.startswith("self.db.")] == expected["db_calls"]
        lowered = "\\n".join(calls).lower()
        assert not [marker for marker in PROTECTED_MARKERS if marker in lowered]

    assert app_text.count("_configure_wave58_system_data_summary(globals())") == 1
    for name in EXPECTED:
        assert app_text.count(f"App.{{name}} = _wave58{{name}}") == 1
    print("Wave 58 exact System Data summary extraction regression passed")


if __name__ == "__main__":
    main()
'''


def render_widget_test() -> str:
    return '''"""Real Tkinter behavior test for Wave 58 System Data summary helpers."""
from __future__ import annotations

import tkinter as tk

import spina_app.system_data_summary_presentation as module


class FakeDB:
    def __init__(self):
        self.calls = []
        self.record = {
            "expected_amount": 3500,
            "actual_cash": 3450,
            "variance": -50,
            "variance_status": "Short",
            "variance_workflow_status": "Reviewed",
            "is_closed": 1,
            "note": "Safe test record",
        }

    def get_databank_daily_total(self, date_s, loan_type=None):
        self.calls.append(("total", date_s, loan_type))
        return 2500 if loan_type == "Regular" else 1000

    def get_databank_day_close(self, date_s):
        self.calls.append(("close", date_s))
        return self.record


class FakeApp:
    _system_data_get_date = module._system_data_get_date
    _system_data_use_focus_date = module._system_data_use_focus_date
    _system_data_refresh_summary = module._system_data_refresh_summary

    def __init__(self, root):
        self.root = root
        self.db = FakeDB()
        self.system_data_date_var = tk.StringVar(root, value="")
        self.system_data_summary_var = tk.StringVar(root, value="")

    def _get_databank_focus_date(self):
        return "2026-07-27"


def main() -> None:
    module.configure_system_data_summary_dependencies({
        "fmt_currency": lambda value: f"${float(value):,.2f}",
        "_log_suppressed_once": lambda *args, **kwargs: None,
    })
    root = tk.Tk()
    root.withdraw()
    try:
        app = FakeApp(root)
        app._system_data_use_focus_date()
        assert app.system_data_date_var.get() == "2026-07-27"
        assert app._system_data_get_date() == "2026-07-27"

        app._system_data_refresh_summary()
        assert app.db.calls == [
            ("total", "2026-07-27", "Regular"),
            ("total", "2026-07-27", "7x7"),
            ("close", "2026-07-27"),
        ]
        assert app.system_data_summary_var.get() == (
            "Date: 2026-07-27\n"
            "Regular Expected: $2,500.00\n"
            "7x7 Expected: $1,000.00\n"
            "Total Expected: $3,500.00\n"
            "Actual Cash: $3,450.00\n"
            "Variance: $50.00 (Short)\n"
            "Workflow: Reviewed | Status: Closed\n"
            "Note: Safe test record"
        )

        app.db.calls.clear()
        app.db.record = None
        app._system_data_refresh_summary()
        assert app.system_data_summary_var.get() == (
            "Date: 2026-07-27\n"
            "Regular Expected: $2,500.00\n"
            "7x7 Expected: $1,000.00\n"
            "Total Expected: $3,500.00\n"
            "No Daily Close record yet for this date."
        )
        print("Wave 58 real Tkinter System Data summary behavior test passed")
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
'''


def main() -> None:
    raw = APP.read_bytes()
    had_bom = raw.startswith(codecs.BOM_UTF8)
    original_text = raw.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in original_text else "\n"
    text = original_text.replace("\r\n", "\n")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text, filename=str(APP))
    nodes = find_targets(tree)

    dedented_sources: dict[str, str] = {}
    metadata: dict[str, dict[str, object]] = {}
    ranges: list[tuple[int, int]] = []
    for name, expected in TARGETS.items():
        node = nodes[name]
        if node.end_lineno is None:
            raise SystemExit(f"Missing end line for {name}")
        source = "".join(lines[node.lineno - 1 : node.end_lineno])
        line_count = node.end_lineno - node.lineno + 1
        if line_count != expected["lines"]:
            raise SystemExit(f"{name} line boundary changed: {line_count}")
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        if digest != expected["sha256"]:
            raise SystemExit(f"{name} source hash changed: {digest}")
        signature = ast.unparse(node.args)
        if signature != expected["signature"]:
            raise SystemExit(f"{name} signature changed: {signature}")
        calls = sorted({
            dotted(call.func)
            for call in ast.walk(node)
            if isinstance(call, ast.Call) and dotted(call.func)
        })
        if calls != expected["calls"]:
            raise SystemExit(f"{name} call set changed: {calls}")
        lowered = "\n".join(calls).lower()
        hits = [marker for marker in PROTECTED_MARKERS if marker in lowered]
        if hits:
            raise SystemExit(f"{name} protected calls detected: {hits}")
        dedented = textwrap.dedent(source)
        dedented_sources[name] = dedented
        metadata[name] = {
            "lines": line_count,
            "source_sha256": digest,
            "dedented_sha256": hashlib.sha256(dedented.encode("utf-8")).hexdigest(),
            "signature": signature,
            "calls": calls,
            "db_calls": [call for call in calls if call.startswith("self.db.")],
        }
        ranges.append((node.lineno - 1, node.end_lineno))

    MODULE.write_text(render_module(dedented_sources, metadata), encoding="utf-8")
    EXACT_TEST.write_text(render_exact_test(metadata), encoding="utf-8")
    WIDGET_TEST.write_text(render_widget_test(), encoding="utf-8")

    new_lines = list(lines)
    for start, end in sorted(ranges, reverse=True):
        del new_lines[start:end]
    new_text = "".join(new_lines)
    marker = "\ndef main():"
    if marker not in new_text:
        raise SystemExit("Wave 58 startup marker missing")
    if "_configure_wave58_system_data_summary" in new_text:
        raise SystemExit("Wave 58 binding already exists")
    binding_lines = [
        "",
        "",
        "# Wave 58: System Data date and summary helpers.",
        "from spina_app.system_data_summary_presentation import (",
        "    configure_system_data_summary_dependencies as _configure_wave58_system_data_summary,",
    ]
    for name in TARGETS:
        binding_lines.append(f"    {name} as _wave58{name},")
    binding_lines.extend([
        ")",
        "_configure_wave58_system_data_summary(globals())",
    ])
    for name in TARGETS:
        binding_lines.append(f"App.{name} = _wave58{name}")
    binding = "\n".join(binding_lines) + "\n"
    new_text = new_text.replace(marker, binding + marker, 1)
    if newline == "\r\n":
        new_text = new_text.replace("\n", "\r\n")
    encoded = new_text.encode("utf-8")
    if had_bom:
        encoded = codecs.BOM_UTF8 + encoded
    APP.write_bytes(encoded)

    report = {
        "base_commit": "883907675bc64ede2916e7fe4ab167799f559ebf",
        "total_lines": sum(int(info["lines"]) for info in metadata.values()),
        "methods": metadata,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
