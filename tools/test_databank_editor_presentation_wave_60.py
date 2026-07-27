from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "databank_editor_presentation.py"
TARGETS = ('_pick_missed_reason', '_walk_widgets', '_begin_cell_edit', '_remember_cell_click')
EXPECTED = {'_pick_missed_reason': {'lines': 145, 'source_sha256': 'e75ed29b15ad4f421b70289378b7f3d7b3a653cb712a1f6fed8cd1bcda5471ec', 'dedented_sha256': '3e40b963909160fe3887b1efa000a2f279ca830af51831fa13339bd88b6e08a3', 'signature': "self, parent, prefill_text=''", 'calls': ['_dt.strptime', '_log_suppressed_once', '_parse_any_date', '_re.fullmatch', 'adv_box.pack', 'adv_end_var.get', 'adv_end_var.set', 'adv_start_var.get', 'adv_start_var.set', 'advance_var.get', 'advance_var.trace_add', 'btns.pack', 'child.configure', 'd.strftime', 'date.today', 'enumerate', 'frm.pack', 'grid', 'hasattr', 'int', 'join', 'messagebox.showwarning', 'on_adv_toggle', 'on_cancel', 'on_ok', 'other_var.get', 'pack', 'parent.winfo_height', 'parent.winfo_rootx', 'parent.winfo_rooty', 'parent.winfo_width', 'picked.append', 's.split', 'set_enabled', 'strftime', 'strip', 't.startswith', 'tk.BooleanVar', 'tk.StringVar', 'tk.Toplevel', 'top.bind', 'top.destroy', 'top.geometry', 'top.grab_set', 'top.resizable', 'top.title', 'top.transient', 'top.update_idletasks', 'top.wait_window', 'top.winfo_height', 'top.winfo_width', 'ttk.Button', 'ttk.Checkbutton', 'ttk.Entry', 'ttk.Frame', 'ttk.Label', 'ttk.Labelframe', 'ttk.Separator', 'txt.startswith', 'v.get', 'vars_.append', 'widget.winfo_children'], 'db_calls': [], 'delegated_save': False}, '_walk_widgets': {'lines': 7, 'source_sha256': 'ebb27216245c3fa0d345c84a720dfdd79654b052024ee1c9adb9d202a051dc7c', 'dedented_sha256': '5bebfe0a0a4c45a619a630825f16c4cbc1d828f7a27bbd315af30707ad2dc6bc', 'signature': 'self, widget', 'calls': ['self._walk_widgets', 'widget.winfo_children'], 'db_calls': [], 'delegated_save': False}, '_begin_cell_edit': {'lines': 142, 'source_sha256': '7e2a682544179556392ed7f291dba538bed362d57979b0a0319115bf87b59bb7', 'dedented_sha256': 'fefbd3e586e7c5acd97aa381471ff49d898657c66af7bb550ee59a51ebb4ecba', 'signature': 'self, event=None', 'calls': ['_log_suppressed_once', 'cn.startswith', 'col_id.startswith', 'cur_txt.replace', 'cur_txt.strip', 'date', 'ent.bind', 'ent.destroy', 'ent.focus_set', 'ent.insert', 'ent.place', 'get', 'getattr', 'hasattr', 'head_txt.isdigit', 'int', 'isdigit', 'lower', 'self._mk_tk_entry', 'self._save_cell_edit', 'self.current_entry.destroy', 'self.root.bell', 'str', 'strftime', 'strip', 'tv.bbox', 'tv.get_children', 'tv.heading', 'tv.identify_column', 'tv.identify_row', 'tv.item', 'tv.see', 'tv.set', 'tv.update_idletasks'], 'db_calls': [], 'delegated_save': True}, '_remember_cell_click': {'lines': 19, 'source_sha256': 'b58c42ff67630fdaeb8a3dd8dc15392bec19a6163524db2f461fdb59ecaa1c1d', 'dedented_sha256': '5f9c3520c90f58fe98fb769fbc4547ff4d1dbe7c68b0cb969070d4898f14f156', 'signature': 'self, event', 'calls': ['col.startswith', 'getattr', 'hasattr', 'int', 'self._update_data_toolbar', 'tv.identify_column', 'tv.identify_row', 'tv.item'], 'db_calls': [], 'delegated_save': False}}
PROTECTED_HASHES = {'_save_cell_edit': '3f421b85935c6bdb2f9a5e53a689a81a362a3332889104b858d2b5e3689c7410', 'delete_selected_cell': '218ac3dadc0dfd0540b27b1cac968da8a6cf1b2197f0973b90577810e7097d6a', '_mark_missed_for_selected': 'df6545048882965daf68fca634445086426e358ca0b39fa4f319d865c648be67', 'open_delete_day_dialog': 'b41b22e7c18f2e7f391f4cd400a9f0034c9ca535d2c7b10a9045db35af3d0407'}
BINDING_MARKER = '# Wave 60: Data Bank inline editor and missed-reason presentation.'


def _norm(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def _source_map(text: str, class_name: str | None = None) -> dict[str, str]:
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    nodes = tree.body
    if class_name is not None:
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
        nodes = cls.body
    out = {}
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.end_lineno is not None:
            out[node.name] = "".join(lines[node.lineno - 1:node.end_lineno])
    return out


def main() -> None:
    app_text = _norm(APP)
    module_text = _norm(MODULE)
    app_methods = _source_map(app_text, "App")
    module_methods = _source_map(module_text)

    for name in TARGETS:
        assert name not in app_methods, f"{name} still exists on App"
        assert name in module_methods, f"{name} missing from module"
        source = module_methods[name]
        assert hashlib.sha256(source.encode("utf-8")).hexdigest() == EXPECTED[name]["dedented_sha256"]
        node = ast.parse(source).body[0]
        assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        assert ast.unparse(node.args) == EXPECTED[name]["signature"]

    for name, expected_hash in PROTECTED_HASHES.items():
        assert name in app_methods, f"protected method {name} missing"
        actual = hashlib.sha256(app_methods[name].encode("utf-8")).hexdigest()
        assert actual == expected_hash, f"protected method {name} changed"

    assert BINDING_MARKER in app_text
    assert "configure_databank_editor_dependencies" in app_text
    for name in TARGETS:
        assert f"App.{name} = _wave60{name}" in app_text

    tree = ast.parse(module_text)
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name not in TARGETS:
            continue
        calls = []
        for call in ast.walk(node):
            if isinstance(call, ast.Call):
                func = call.func
                parts = []
                while isinstance(func, ast.Attribute):
                    parts.append(func.attr)
                    func = func.value
                if isinstance(func, ast.Name):
                    parts.append(func.id)
                if parts:
                    calls.append(".".join(reversed(parts)))
        assert not [call for call in calls if call.startswith("self.db.")]
        lowered = "\n".join(calls).lower()
        for marker in ('.execute', '.executemany', '.commit', '.rollback', 'add_or_update_transaction', 'delete_transaction', 'delete_transactions_for_day', 'set_databank_day_close', 'replace_databank_day_collectors', 'close_day', 'reopen_day'):
            assert marker.lower() not in lowered, (node.name, marker)

    print("Wave 60 exact Data Bank editor extraction regression passed")


if __name__ == "__main__":
    main()
