"""Guarded high-volume extraction for Collectors editor/view helpers, Wave 26."""

from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE = Path("spina_app/tabs/collectors.py")
TEST = Path("tools/test_collectors_editor_wave_26.py")
PERMANENT_WORKFLOW = Path(".github/workflows/collectors-editor-wave-26.yml")
INVENTORY_WORKFLOW = Path(".github/workflows/high-volume-wave-26-inventory.yml")
TEMP_WORKFLOW = Path(".github/workflows/apply-collectors-editor-wave-26.yml")
INVENTORY_TOOL = Path("tools/inventory_high_volume_wave_26.py")
SELF = Path("tools/apply_collectors_editor_wave_26.py")

EXPECTED_SOURCE_SHA256 = "5d404960b1b5d5c765ef6fc0b3035cd7b52ddba30234a9318a3aac957af4892b"
EXPECTED_MODULE_BLOB = "4241bf04735dc0428ecec719cc33935860d75d59"
TARGET_HASHES = {
    "_collectors_get_selected_name": "d431c947c01198cf7bc03c0f9533ac6acc0c4eb045af371c520d6ca361193a9e",
    "_collectors_toggle_sections": "03ac9066e7972f1fcab9f9bb7515a368a3b37455ec84cf40a9cce8ae6d4e97c3",
    "_collectors_apply_markers": "0bf9ecfe194cbef9f0c953ebc324cb3a670793ad60f49ae2c8f85886b3fe93b7",
    "_collectors_refresh_bulk_bar": "442f94d51835ee90bfb31e71a820ac19f70629d3181a142fbd5589495a4ad975",
    "_collectors_clear_checked": "69823e476fd4683cd6320d9399c5033ed7fa1c36dff109cceb8dbf3552e5a3f2",
    "_collectors_start_inline_edit": "e7d46cd0d56b2ea703105990bfd3c4857e0c2592801c16dc9b96710b0ad27892",
    "_collectors_load_inline_edit_fields": "daf666be310c4bb6ba18c420aec29a8d9c68090986a295e7b1e3538c3c4126f3",
    "_collectors_cancel_inline_edit": "ad60d1d8661cfc674dace7b6f1301144b9fad48bc4ef5241321913bc2bc857b9",
    "_collectors_choose_areas": "7a1172a6ff1b73fd26b9c0937c32ef8e3ffce33813f0ea5c56023580e96bcd50",
    "_collectors_add_area_text": "4f1d5cfa151f0b7a77fba1d162722b5374b4b4649caa81c5e95e3b4039fe8256",
    "_collectors_remove_area": "750014ee2d619533734522bb7678516b7d8c9265151c368c8b27117767da637c",
    "_collectors_move_area": "aa5e59d6f0b927c7cefb3b94f006db3ecb4015d91b53b0c636f8ea80e37d52ba",
}
TARGETS = tuple(TARGET_HASHES)
PROTECTED_CALLERS = (
    "_collectors_name_from_values",
    "_on_collectors_tree_click",
    "_on_collectors_multi_toggle",
    "_build_collectors_tab",
    "_edit_selected_collector",
    "_spina_v25_build_collectors_tab",
    "_collectors_save_inline_edit",
    "_populate_collector_details",
    "_save_selected_collector_notes",
)
MARKER = "\n# Collectors editor and view-state helpers extracted in Wave 26.\n\n"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_for(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def top_nodes(text: str, filename: str) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    tree = ast.parse(text, filename=filename)
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def function_hashes(text: str, filename: str) -> dict[str, str]:
    lines = text.splitlines()
    return {
        name: sha256_text(source_for(lines, node))
        for name, node in top_nodes(text, filename).items()
    }


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def build_import() -> list[str]:
    return [
        "from spina_app.tabs.collectors import (",
        *[f"    {name}," for name in TARGETS],
        ")",
        "",
    ]


def build_test_content(module_base_sha: str, protected_hashes: dict[str, str]) -> str:
    return f'''"""Focused regression checks for Collectors editor high-volume Wave 26."""

from __future__ import annotations

import ast
import hashlib
import importlib
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE = Path("spina_app/tabs/collectors.py")
TARGET_HASHES = {TARGET_HASHES!r}
TARGETS = tuple(TARGET_HASHES)
PROTECTED_HASHES = {protected_hashes!r}
MARKER = {MARKER!r}
MODULE_BASE_SHA256 = {module_base_sha!r}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_for(lines: list[str], node: ast.AST) -> str:
    return "\\n".join(lines[node.lineno - 1 : node.end_lineno])


def nodes(text: str, filename: str):
    tree = ast.parse(text, filename=filename)
    return {{
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }}, tree


class Var:
    def __init__(self, value=None):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


class Widget:
    def __init__(self, mapped=True):
        self.mapped = mapped
        self.options = {{}}
    def pack(self, **kwargs):
        self.mapped = True
        self.options.update(kwargs)
    def pack_forget(self):
        self.mapped = False
    def grid(self, **kwargs):
        self.mapped = True
        self.options.update(kwargs)
    def grid_remove(self):
        self.mapped = False
    def winfo_ismapped(self):
        return self.mapped
    def configure(self, **kwargs):
        self.options.update(kwargs)


class FakeTree(Widget):
    def __init__(self):
        super().__init__(True)
        self.rows = {{
            "a": ["○", "Alice"],
            "b": ["○", "Bob"],
        }}
        self.selected = ("a",)
        self.focused = "a"
    def selection(self):
        return self.selected
    def focus(self):
        return self.focused
    def get_children(self):
        return tuple(self.rows)
    def item(self, iid, option=None, **kwargs):
        if "values" in kwargs:
            self.rows[iid] = list(kwargs["values"])
        if option == "values":
            return tuple(self.rows[iid])
        return {{"values": tuple(self.rows[iid])}}


class FakeListbox:
    def __init__(self, items=None):
        self.items = list(items or [])
        self.selection = []
    def size(self):
        return len(self.items)
    def get(self, index):
        return self.items[int(index)]
    def insert(self, index, value):
        if index == "end":
            self.items.append(value)
        else:
            self.items.insert(int(index), value)
    def delete(self, first, last=None):
        if first == 0 and last == "end":
            self.items.clear()
            self.selection.clear()
            return
        del self.items[int(first)]
        self.selection = [i for i in self.selection if i != int(first)]
    def curselection(self):
        return tuple(self.selection)
    def selection_clear(self, first, last):
        self.selection.clear()
    def selection_set(self, index):
        self.selection = [int(index)]


class FakeText:
    def __init__(self):
        self.value = ""
    def delete(self, first, last):
        self.value = ""
    def insert(self, index, value):
        self.value = str(value)


class Dummy:
    pass


def bind(obj, module):
    import types
    for name in TARGETS:
        setattr(obj, name, types.MethodType(getattr(module, name), obj))
    obj._collectors_name_from_values = lambda values: str(values[1]).strip() if len(values) > 1 else ""
    obj._populate_collector_details_calls = []
    obj._populate_collector_details = lambda name=None: obj._populate_collector_details_calls.append(name)


def static_checks(module):
    source_text = SOURCE.read_text(encoding="utf-8")
    source_lines = source_text.splitlines()
    source_nodes, source_tree = nodes(source_text, str(SOURCE))
    for name in TARGETS:
        assert name not in source_nodes, f"Target definition remains in desktop source: {{name}}"

    imported = set()
    for node in source_tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.tabs.collectors":
            imported.update(alias.name for alias in node.names)
    assert set(TARGETS) <= imported, f"Missing Collectors imports: {{sorted(set(TARGETS) - imported)}}"

    for name, expected in PROTECTED_HASHES.items():
        assert name in source_nodes, f"Protected caller missing: {{name}}"
        digest = sha256_text(source_for(source_lines, source_nodes[name]))
        assert digest == expected, f"Protected caller changed: {{name}} {{digest}}"

    module_text = MODULE.read_text(encoding="utf-8")
    assert module_text.count(MARKER) == 1, "Wave 26 module marker missing or duplicated"
    base_text, _ = module_text.split(MARKER, 1)
    assert sha256_text(base_text) == MODULE_BASE_SHA256, "Pre-existing Collectors module changed"
    module_lines = module_text.splitlines()
    module_nodes, _ = nodes(module_text, str(MODULE))
    for name, expected in TARGET_HASHES.items():
        assert name in module_nodes, f"Extracted target missing: {{name}}"
        digest = sha256_text(source_for(module_lines, module_nodes[name]))
        assert digest == expected, f"Extracted target changed: {{name}} {{digest}}"
        assert callable(getattr(module, name))


def behavior_checks(module):
    obj = Dummy()
    bind(obj, module)
    obj.collectors_tree = FakeTree()
    obj._selected_collector_name = "Alice"
    obj.collector_route_multi_var = Var(False)
    obj._collectors_checked = set()
    obj.collectors_bulk_bar = Widget(False)
    obj.collectors_bulk_count_var = Var("")

    assert obj._collectors_get_selected_name() == "Alice"
    obj._collectors_apply_markers()
    assert obj.collectors_tree.rows["a"][0] == "●"
    assert obj.collectors_tree.rows["b"][0] == "○"

    obj.collector_route_multi_var.set(True)
    obj._collectors_checked = {{"Bob"}}
    obj._collectors_apply_markers()
    assert obj.collectors_tree.rows["a"][0] == "☐"
    assert obj.collectors_tree.rows["b"][0] == "☑"
    assert obj.collectors_bulk_bar.mapped
    assert obj.collectors_bulk_count_var.get() == "Selected: 1"
    obj._collectors_clear_checked()
    assert obj._collectors_checked == set()
    assert not obj.collectors_bulk_bar.mapped

    obj.collector_route_show_areas_var = Var(False)
    obj.collector_route_show_notes_var = Var(True)
    obj.collector_route_areas_box = Widget(True)
    obj.collector_route_notes_box = Widget(False)
    obj._collectors_toggle_sections()
    assert not obj.collector_route_areas_box.mapped
    assert obj.collector_route_notes_box.mapped

    obj.collector_route_selected_name_lbl = Widget(True)
    obj.collector_route_selected_name_ent = Widget(False)
    obj.collector_route_edit_name_var = Var("")
    obj.collector_route_btn_edit = Widget(True)
    obj.collector_route_btn_save = Widget(False)
    obj.collector_route_btn_cancel = Widget(False)
    obj.collector_route_area_tree = Widget(True)
    obj.collector_route_areas_edit_frm = Widget(False)
    obj.collector_route_areas_lb = FakeListbox()
    obj.collector_route_notes_txt = FakeText()
    obj._collectors_data_cache = {{"Alice": {{"areas": ["North", "South"], "notes": "Priority"}}}}
    obj._collectors_inline_editing = False

    obj._collectors_start_inline_edit()
    assert obj._collectors_inline_editing
    assert obj.collector_route_edit_name_var.get() == "Alice"
    assert obj.collector_route_areas_lb.items == ["North", "South"]
    assert obj.collector_route_notes_txt.value == "Priority"
    assert not obj.collector_route_area_tree.mapped
    assert obj.collector_route_areas_edit_frm.mapped

    obj._collectors_cancel_inline_edit()
    assert not obj._collectors_inline_editing
    assert obj.collector_route_area_tree.mapped
    assert not obj.collector_route_areas_edit_frm.mapped
    assert obj._populate_collector_details_calls[-1] == "Alice"

    obj._area_picker_dialog = lambda initial, title: ["East", "West"]
    obj._collectors_choose_areas()
    assert obj.collector_route_areas_lb.items == ["East", "West"]

    obj.collector_route_area_add_var = Var("Central")
    obj._collectors_add_area_text()
    assert obj.collector_route_areas_lb.items == ["East", "West", "Central"]
    obj.collector_route_area_add_var.set("central")
    obj._collectors_add_area_text()
    assert obj.collector_route_areas_lb.items == ["East", "West", "Central"]

    obj.collector_route_areas_lb.selection = [1]
    obj._collectors_move_area(-1)
    assert obj.collector_route_areas_lb.items == ["West", "East", "Central"]
    obj._collectors_remove_area()
    assert obj.collector_route_areas_lb.items == ["East", "Central"]


def main():
    module = importlib.import_module("spina_app.tabs.collectors")
    static_checks(module)
    behavior_checks(module)
    print("Collectors editor high-volume Wave 26 regression passed.")


if __name__ == "__main__":
    main()
'''


PERMANENT_WORKFLOW_CONTENT = r'''name: Collectors editor Wave 26

on:
  pull_request:

permissions:
  contents: read

jobs:
  validate:
    if: github.head_ref == 'agent/high-volume-wave-26'
    runs-on: [self-hosted, Windows, X64]
    timeout-minutes: 30
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Verify local Python
        shell: cmd
        run: |
          where python
          python --version

      - name: Compile application, Collectors module, and test
        shell: cmd
        run: |
          python -m py_compile OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py
          python -m py_compile spina_app\tabs\collectors.py
          python -m py_compile tools\test_collectors_editor_wave_26.py
          python -m compileall -q spina_app

      - name: Run Collectors editor regression
        shell: cmd
        run: python -m tools.test_collectors_editor_wave_26

      - name: Run redundancy audit
        shell: cmd
        run: python tools\redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json redundancy-report.json

      - name: Run SPINA quality audit
        shell: cmd
        run: python tools\spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json quality-report.json

      - name: Upload audit reports
        uses: actions/upload-artifact@v4
        with:
          name: collectors-editor-wave-26-audits
          path: |
            redundancy-report.json
            quality-report.json
          if-no-files-found: error
'''


def main() -> None:
    source_text = SOURCE.read_text(encoding="utf-8")
    if sha256_text(source_text) != EXPECTED_SOURCE_SHA256:
        raise SystemExit(f"Unexpected desktop source SHA: {sha256_text(source_text)}")

    current_blob = git_output("rev-parse", f"HEAD:{MODULE.as_posix()}")
    if current_blob != EXPECTED_MODULE_BLOB:
        raise SystemExit(f"Unexpected Collectors module blob: {current_blob}")

    module_base_text = MODULE.read_text(encoding="utf-8")
    if MARKER in module_base_text:
        raise SystemExit("Wave 26 marker already exists in Collectors module")

    source_lines = source_text.splitlines()
    nodes = top_nodes(source_text, str(SOURCE))
    before_hashes = function_hashes(source_text, str(SOURCE))

    extracted: list[str] = []
    ranges: dict[int, tuple[int, str]] = {}
    for name in TARGETS:
        node = nodes.get(name)
        if node is None:
            raise SystemExit(f"Missing target function: {name}")
        body = source_for(source_lines, node)
        digest = sha256_text(body)
        if digest != TARGET_HASHES[name]:
            raise SystemExit(f"Target source hash mismatch for {name}: {digest}")
        extracted.append(body)
        ranges[node.lineno] = (node.end_lineno, name)

    protected_hashes: dict[str, str] = {}
    for name in PROTECTED_CALLERS:
        if name not in before_hashes:
            raise SystemExit(f"Missing protected caller: {name}")
        protected_hashes[name] = before_hashes[name]

    output: list[str] = []
    line_no = 1
    first_start = min(ranges)
    while line_no <= len(source_lines):
        if line_no == first_start:
            output.extend(build_import())
        if line_no in ranges:
            end_line, _name = ranges[line_no]
            line_no = end_line + 1
            continue
        output.append(source_lines[line_no - 1])
        line_no += 1

    new_source_text = "\n".join(output) + "\n"
    after_hashes = function_hashes(new_source_text, str(SOURCE))
    expected_names = set(before_hashes) - set(TARGETS)
    if set(after_hashes) != expected_names:
        missing = sorted(expected_names - set(after_hashes))
        extra = sorted(set(after_hashes) - expected_names)
        raise SystemExit(f"Non-target function set changed; missing={missing}, extra={extra}")
    for name in expected_names:
        if before_hashes[name] != after_hashes[name]:
            raise SystemExit(f"Non-target function changed: {name}")

    module_base_sha = sha256_text(module_base_text)
    module_new_text = module_base_text + MARKER + "\n\n".join(extracted) + "\n"

    SOURCE.write_text(new_source_text, encoding="utf-8")
    MODULE.write_text(module_new_text, encoding="utf-8")
    TEST.write_text(build_test_content(module_base_sha, protected_hashes), encoding="utf-8")
    PERMANENT_WORKFLOW.write_text(PERMANENT_WORKFLOW_CONTENT, encoding="utf-8")

    INVENTORY_WORKFLOW.unlink(missing_ok=True)
    INVENTORY_TOOL.unlink(missing_ok=True)
    TEMP_WORKFLOW.unlink(missing_ok=True)
    SELF.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
