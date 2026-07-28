from __future__ import annotations

import ast
import hashlib
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "client_statement_generation.py"
STRUCT_TEST = ROOT / "tools" / "test_client_statement_generation_wave_67.py"
BEHAVIOR_TEST = ROOT / "tools" / "test_client_statement_generation_behavior_wave_67.py"

EXPECTED_LINES = 258
EXPECTED_SOURCE_SHA = "8225a64ebbaf150af577a34f185fafbef8d4310d56132a45a86e53acebe5e2df"
EXPECTED_SIGNATURE = "self"
EXPECTED_DB_CALLS = ["self.db.get_client_info", "self.db.get_client_link_meta"]
BINDING_BLOCK = """# Wave 67: Client statement generation orchestration.\nfrom spina_app.client_statement_generation import (\n    configure_client_statement_generation_dependencies as _configure_wave67_client_statement_generation,\n    generate_pdf_selected as _wave67_generate_pdf_selected,\n)\n_configure_wave67_client_statement_generation(globals())\nApp.generate_pdf_selected = _wave67_generate_pdf_selected\n\n\n"""


def sha(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def dotted(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return dotted(node.func)
    if isinstance(node, ast.Subscript):
        return dotted(node.value)
    return ""


def find_method(text: str):
    tree = ast.parse(text)
    app = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "App")
    node = next(
        n for n in app.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name == "generate_pdf_selected"
    )
    lines = text.splitlines(keepends=True)
    source = "".join(lines[node.lineno - 1:node.end_lineno])
    return node, source, lines


def build_module(node: ast.FunctionDef, source: str) -> str:
    dedented = textwrap.dedent(source)
    calls = sorted({dotted(c.func) for c in ast.walk(node) if isinstance(c, ast.Call) and dotted(c.func)})
    db_calls = sorted(c for c in calls if c.startswith("self.db") or ".db." in c)
    metadata = {
        "lines": node.end_lineno - node.lineno + 1,
        "source_sha256": sha(source),
        "dedented_sha256": sha(dedented),
        "signature": ast.unparse(node.args),
        "calls": calls,
        "db_calls": db_calls,
    }
    return (
        '"""Client statement generation orchestration extracted in Wave 67."""\n'
        "from __future__ import annotations\n\n"
        "_CLIENT_STATEMENT_GENERATION_DEPENDENCIES = {}\n"
        "_PROTECTED_GLOBALS = {\n"
        "    '__name__', '__doc__', '__package__', '__loader__', '__spec__',\n"
        "    '__file__', '__cached__', '__builtins__',\n"
        "    '_CLIENT_STATEMENT_GENERATION_DEPENDENCIES', '_PROTECTED_GLOBALS',\n"
        "    'CLIENT_STATEMENT_GENERATION_METHODS',\n"
        "    'configure_client_statement_generation_dependencies',\n"
        "    'generate_pdf_selected',\n"
        "}\n\n"
        "def configure_client_statement_generation_dependencies(namespace):\n"
        "    _CLIENT_STATEMENT_GENERATION_DEPENDENCIES.clear()\n"
        "    _CLIENT_STATEMENT_GENERATION_DEPENDENCIES.update(namespace)\n"
        "    for name, value in namespace.items():\n"
        "        if name not in _PROTECTED_GLOBALS:\n"
        "            globals()[name] = value\n\n"
        f"CLIENT_STATEMENT_GENERATION_METHODS = {json.dumps({'generate_pdf_selected': metadata}, ensure_ascii=False, sort_keys=True)}\n\n"
        + dedented.rstrip() + "\n"
    )


def build_structural_test() -> str:
    return r'''from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "client_statement_generation.py"
EXPECTED_LINES = 258
EXPECTED_SOURCE_SHA = "8225a64ebbaf150af577a34f185fafbef8d4310d56132a45a86e53acebe5e2df"
EXPECTED_SIGNATURE = "self"
EXPECTED_DB_CALLS = ["self.db.get_client_info", "self.db.get_client_link_meta"]


def sha(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def dotted(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return dotted(node.func)
    if isinstance(node, ast.Subscript):
        return dotted(node.value)
    return ""


def main() -> None:
    module_text = MODULE.read_text(encoding="utf-8")
    module_tree = ast.parse(module_text)
    function = next(
        n for n in module_tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "generate_pdf_selected"
    )
    lines = module_text.splitlines(keepends=True)
    source = "".join(lines[function.lineno - 1:function.end_lineno])

    namespace = {}
    exec(compile(module_text, str(MODULE), "exec"), namespace)
    metadata = namespace["CLIENT_STATEMENT_GENERATION_METHODS"]["generate_pdf_selected"]

    assert function.end_lineno - function.lineno + 1 == EXPECTED_LINES
    assert metadata["lines"] == EXPECTED_LINES
    assert metadata["source_sha256"] == EXPECTED_SOURCE_SHA
    assert sha(source) == metadata["dedented_sha256"]
    assert ast.unparse(function.args) == EXPECTED_SIGNATURE == metadata["signature"]

    calls = sorted({dotted(c.func) for c in ast.walk(function) if isinstance(c, ast.Call) and dotted(c.func)})
    db_calls = sorted(c for c in calls if c.startswith("self.db") or ".db." in c)
    assert calls == metadata["calls"]
    assert db_calls == EXPECTED_DB_CALLS == metadata["db_calls"]
    assert not any(term in call.lower() for call in db_calls for term in (
        "add", "insert", "update", "delete", "save", "commit", "rollback",
    ))

    app_text = APP.read_text(encoding="utf-8")
    app_tree = ast.parse(app_text)
    app = next(n for n in app_tree.body if isinstance(n, ast.ClassDef) and n.name == "App")
    assert not any(
        isinstance(n, ast.FunctionDef) and n.name == "generate_pdf_selected"
        for n in app.body
    )
    assert app_text.count(
        "configure_client_statement_generation_dependencies as _configure_wave67_client_statement_generation"
    ) == 1
    assert app_text.count("_configure_wave67_client_statement_generation(globals())") == 1
    assert app_text.count("App.generate_pdf_selected = _wave67_generate_pdf_selected") == 1

    remaining = {n.name for n in app.body if isinstance(n, ast.FunctionDef)}
    assert "_run_long_task" in remaining
    print("Wave 67 client-statement generation structural regression passed")


if __name__ == "__main__":
    main()
'''


def build_behavior_test() -> str:
    return r'''from __future__ import annotations

import json
import os
import tempfile
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import ttk

from spina_app import client_statement_generation as generation


class MessageboxStub:
    def __init__(self):
        self.warnings = []
        self.errors = []

    def showwarning(self, title, message, **kwargs):
        self.warnings.append((title, message))

    def showerror(self, title, message, **kwargs):
        self.errors.append((title, message))


class FakeDB:
    def __init__(self):
        self.info_calls = []
        self.meta_calls = []

    def get_client_info(self, name, loan_type=None):
        self.info_calls.append((name, loan_type))
        return {
            "client_uid": "CLIENT-1234567890",
            "date_released": "2026-07-01",
            "payment_start_date": "2026-07-02",
            "pay_start_offset_days": 1,
        }

    def get_client_link_meta(self, name, loan_type=None):
        self.meta_calls.append((name, loan_type))
        return {
            "client_uid": "CLIENT-1234567890",
            "person_uid": "PERSON-ABC",
        }


class FakeApp:
    def __init__(self, root):
        self.db = FakeDB()
        self.reports_tree = ttk.Treeview(root, columns=("name",), show="headings")
        self.reports_tree.heading("name", text="Client")
        iid = self.reports_tree.insert("", "end", values=("Juan Dela Cruz",))
        self.reports_tree.selection_set(iid)
        self.start_date_var = tk.StringVar(root, value="2026-07-03")
        self.end_date_var = tk.StringVar(root, value="2026-07-05")
        self.report_page_size_var = tk.StringVar(root, value="Folio 8x13")
        self.status_var = tk.StringVar(root, value="")
        self.long_task_labels = []

    def _mode_filter(self):
        return "Regular"

    def _run_long_task(self, label, work, on_success=None, on_error=None):
        self.long_task_labels.append(label)
        try:
            result = work()
        except Exception as exc:
            if on_error:
                on_error(exc)
            return
        if on_success:
            on_success(result)


def safe_component(value, fallback="item", max_len=80):
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(value or "")).strip("_")
    return (cleaned or fallback)[:max_len]


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    messages = MessageboxStub()
    pdf_calls = []
    notes_calls = []
    opened_paths = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        def fake_notes(name, start_date, end_date, **kwargs):
            notes_calls.append((name, start_date, end_date, kwargs))
            return [("2026-07-04", "Collector note")]

        def fake_generate(db, name, start_date, end_date, out, **kwargs):
            pdf_calls.append((db, name, start_date, end_date, out, kwargs))
            Path(out).write_bytes(b"%PDF-1.4\n")

        generation.configure_client_statement_generation_dependencies({
            "messagebox": messages,
            "date": date,
            "os": os,
            "PDF_DIR": str(tmp_path / "fallback"),
            "load_settings": lambda: {"reports_root": str(tmp_path / "reports")},
            "_can_use_dir": lambda path: True,
            "_safe_filename_component": safe_component,
            "get_client_notes_in_range": fake_notes,
            "generate_client_pdf": fake_generate,
            "_open_path": lambda path: opened_paths.append(path),
            "_log_suppressed_once": lambda *args, **kwargs: None,
            "_log_exc": lambda *args, **kwargs: None,
        })

        app = FakeApp(root)
        generation.generate_pdf_selected(app)

        assert not messages.warnings
        assert not messages.errors
        assert app.db.info_calls == [("Juan Dela Cruz", "Regular")]
        assert len(app.db.meta_calls) >= 2
        assert app.long_task_labels == ["Generating PDF for Juan Dela Cruz..."]
        assert len(pdf_calls) == 1

        db, name, start_date, end_date, out, kwargs = pdf_calls[0]
        assert db is app.db
        assert name == "Juan Dela Cruz"
        assert (start_date, end_date) == ("2026-07-03", "2026-07-05")
        assert kwargs["loan_type"] == "Regular"
        assert kwargs["page_size_name"] == "Folio 8x13"
        assert kwargs["note_text"] == "2026-07-04: Collector note"
        assert Path(out).exists()
        assert "Regular" in Path(out).parts
        assert "Juan_Dela_Cruz__CLIENT-1234567890" in Path(out).parts
        assert app.status_var.get() == "Report generated successfully."
        assert opened_paths == [out]

        assert len(notes_calls) == 1
        _, note_start, note_end, note_kwargs = notes_calls[0]
        assert (note_start, note_end) == ("2026-07-03", "2026-07-05")
        assert note_kwargs["include_shared"] is False
        assert note_kwargs["include_type"] is True
        assert note_kwargs["include_other_type"] is False
        assert note_kwargs["client_uid"] == "CLIENT-1234567890"
        assert note_kwargs["person_uid"] == "PERSON-ABC"

        index_path = Path(out).parent / "reports_index.jsonl"
        assert index_path.exists()
        records = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(records) == 1
        record = records[0]
        assert record["client_name"] == "Juan Dela Cruz"
        assert record["loan_type"] == "Regular"
        assert record["start_date"] == "2026-07-03"
        assert record["end_date"] == "2026-07-05"
        assert record["page_size"] == "Folio 8x13"
        assert record["pdf_path"] == out

        app.reports_tree.selection_remove(app.reports_tree.selection())
        generation.generate_pdf_selected(app)
        assert messages.warnings[-1][0] == "Select"

    root.destroy()
    print("Wave 67 client-statement generation behavior regression passed")


if __name__ == "__main__":
    main()
'''


def main() -> None:
    text = APP.read_text(encoding="utf-8")
    if "App.generate_pdf_selected = _wave67_generate_pdf_selected" in text:
        print("Wave 67 client-statement generation extraction already applied")
        return

    node, source, lines = find_method(text)
    line_count = node.end_lineno - node.lineno + 1
    if line_count != EXPECTED_LINES:
        raise RuntimeError(f"Expected {EXPECTED_LINES} lines, found {line_count}")
    actual_sha = sha(source)
    if actual_sha != EXPECTED_SOURCE_SHA:
        raise RuntimeError(f"Unexpected client-statement source SHA: {actual_sha}")
    signature = ast.unparse(node.args)
    if signature != EXPECTED_SIGNATURE:
        raise RuntimeError(f"Unexpected client-statement signature: {signature}")

    calls = sorted({dotted(c.func) for c in ast.walk(node) if isinstance(c, ast.Call) and dotted(c.func)})
    db_calls = sorted(c for c in calls if c.startswith("self.db") or ".db." in c)
    if db_calls != EXPECTED_DB_CALLS:
        raise RuntimeError(f"Unexpected client-statement DB calls: {db_calls}")

    MODULE.write_text(build_module(node, source), encoding="utf-8")
    STRUCT_TEST.write_text(build_structural_test(), encoding="utf-8")
    BEHAVIOR_TEST.write_text(build_behavior_test(), encoding="utf-8")

    remaining = "".join(lines[:node.lineno - 1] + lines[node.end_lineno:])
    marker = "\ndef main():"
    insert_at = remaining.rfind(marker)
    if insert_at < 0:
        raise RuntimeError("Could not locate final main() binding point")
    updated = remaining[:insert_at + 1] + BINDING_BLOCK + remaining[insert_at + 1:]
    APP.write_text(updated, encoding="utf-8")
    print("Applied Wave 67 258-line client-statement generation extraction")


if __name__ == "__main__":
    main()
