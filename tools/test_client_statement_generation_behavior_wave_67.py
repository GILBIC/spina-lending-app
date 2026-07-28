from __future__ import annotations

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
