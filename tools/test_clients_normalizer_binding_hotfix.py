#!/usr/bin/env python3
"""Regression for the Wave 81 Clients loan-type normalizer binding."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEATURE_PATH = ROOT / "spina_app" / "features" / "clients.py"


def main() -> None:
    source = FEATURE_PATH.read_text(encoding="utf-8")
    assert '_set(ns, "_app__norm_lt_value", client_services._app__norm_lt_value)' in source
    assert '_set(ns, "_app__other_lt", client_services._app__other_lt)' in source

    from spina_app.services import clients as client_services
    from spina_app.tabs import clients as clients_tab

    # Reproduce the post-Wave-81 environment: no legacy desktop implementation is
    # injected. The modular service must provide the normalizer to the tab.
    clients_tab.configure_clients_dependencies(
        {
            "_app__norm_lt_value": client_services._app__norm_lt_value,
        }
    )

    class FakeTree:
        def __init__(self, selected=True):
            self.selected = selected

        def selection(self):
            return ("row-1",) if self.selected else ()

        def item(self, _iid, option):
            if option == "values":
                return ("Alice Borrower",)
            if option == "tags":
                return ("lt:7x7",)
            return ()

    class FakeApp:
        def __init__(self, selected=True):
            self.clients_tree = FakeTree(selected=selected)

        def _mode_filter(self):
            return "Regular"

    selected = clients_tab._spina_v23_selected_name_lt(FakeApp(selected=True))
    assert selected == ("Alice Borrower", "7x7"), selected

    empty = clients_tab._spina_v23_selected_name_lt(FakeApp(selected=False))
    assert empty == ("", "Regular"), empty

    print("Clients normalizer binding hotfix regression passed.")


if __name__ == "__main__":
    main()
