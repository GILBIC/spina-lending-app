from __future__ import annotations

import ast
import hashlib
import importlib
import json
from pathlib import Path

MAIN = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE = Path("spina_app/tabs/clients.py")
MANIFEST = Path("tools/fixtures/clients_feature_wave_19_manifest.json")


def defs(path: Path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text)
    out = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            out[node.name] = (node, "\n".join(lines[node.lineno - 1 : node.end_lineno]))
    return text, out


class FakeVar:
    def __init__(self, value=None):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


class FakeLabel:
    def __init__(self):
        self.text = None
    def configure(self, **kwargs):
        if "text" in kwargs:
            self.text = kwargs["text"]


class FakeTree:
    def __init__(self, selected=True):
        self.selected = selected
    def selection(self):
        return ("row1",) if self.selected else ()
    def item(self, iid, option):
        if option == "values":
            return ("Alice", "Area 1")
        if option == "tags":
            return ("lt:7x7",)
        return ()
    def get_children(self):
        return ("row1", "row2")


class FakeDB:
    def get_client_info(self, name, loan_type=None, include_archived=False):
        return {"name": name, "loan_type": loan_type, "principal": 1000}


class FakeApp:
    def __init__(self, selected=True):
        self.clients_tree = FakeTree(selected=selected)
        self.db = FakeDB()
        self._clients_stat_labels = {
            key: (FakeLabel(), FakeLabel())
            for key in ("rows", "view", "selected", "balance")
        }
    def _mode_filter(self):
        return "Regular"


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    main_text, main_defs = defs(MAIN)
    module_text, module_defs = defs(MODULE)

    selected = [item["name"] for item in manifest["functions"]]
    assert manifest["function_count"] == 7
    assert manifest["moved_source_lines"] == 387
    for item in manifest["functions"]:
        name = item["name"]
        assert name not in main_defs, name
        assert name in module_defs, name
        digest = hashlib.sha256(module_defs[name][1].encode("utf-8")).hexdigest()
        assert digest == item["sha256"], (name, digest)

    for name in manifest["protected_functions_kept_in_desktop"]:
        assert name in main_defs, name
    assert "from spina_app.tabs.clients import (" in main_text
    assert "configure_clients_dependencies(globals())" in main_text

    clients = importlib.import_module("spina_app.tabs.clients")
    missing = clients.configure_clients_dependencies({})
    assert set(missing) == {
        "_spina_v23_clients_colors",
        "_app__norm_lt_value",
        "_spina_v23_client_loan_summary",
        "_log_exc",
    }

    clients.configure_clients_dependencies(
        {
            "_spina_v23_clients_colors": lambda app=None: {},
            "_app__norm_lt_value": lambda app, value: str(value or "Regular"),
            "_spina_v23_client_loan_summary": lambda app, info: {"balance": 321.0},
            "_log_exc": lambda *args, **kwargs: None,
        }
    )

    app = FakeApp(selected=False)
    assert clients._spina_v23_selected_name_lt(app) == ("", "Regular")

    app = FakeApp(selected=True)
    assert clients._spina_v23_selected_name_lt(app) == ("Alice", "7x7")
    assert clients._spina_v23_update_client_cards(app) is None
    cards = app._clients_stat_labels
    assert cards["rows"][0].text == "2"
    assert cards["view"][0].text == "Regular"
    assert cards["selected"][0].text == "Alice"
    assert cards["selected"][1].text == "7x7"
    assert cards["balance"][0].text not in (None, "", "—")

    print("Clients feature Wave 19 regression passed")


if __name__ == "__main__":
    main()
