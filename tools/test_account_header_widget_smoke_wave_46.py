from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spina_app import account_header_presentation as presentation


class Harness:
    pass


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    try:
        harness = Harness()
        harness.user_name = "admin"
        harness.user_role_label = tk.Label(root, text="Old")
        harness.theme_refreshes = 0
        harness._refresh_header_theme = lambda: setattr(
            harness, "theme_refreshes", harness.theme_refreshes + 1
        )

        presentation.configure_account_header_dependencies({
            "_spina_v32_account_display_name": lambda self, username: "Owner Account" if username == "admin" else username,
            "_log_suppressed_once": lambda *args, **kwargs: None,
        })
        presentation._spina_v32_refresh_user_header(harness)
        assert harness.user_role_label.cget("text") == "Account: Owner Account"
        assert harness.theme_refreshes == 1

        harness.header_refreshes = 0
        harness._refresh_user_header = lambda: setattr(
            harness, "header_refreshes", harness.header_refreshes + 1
        )

        def original_build_header(self, *args, **kwargs):
            self.switch_account_btn = tk.Button(root, text="Switch Account")
            return {"args": args, "kwargs": kwargs}

        presentation.configure_account_header_dependencies({
            "_spina_v32_orig_build_header": original_build_header,
            "_spina_v32_account_display_name": lambda self, username: username,
            "_log_suppressed_once": lambda *args, **kwargs: None,
        })
        result = presentation._spina_v32_build_header(harness, "sample", mode="test")
        assert result == {"args": ("sample",), "kwargs": {"mode": "test"}}
        assert harness.header_refreshes == 1
        assert harness.switch_account_btn.cget("text") == "Account"

        print("Wave 46 account header Tkinter smoke test passed.")
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
