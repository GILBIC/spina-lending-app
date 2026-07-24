"""Patch the temporary Wave 24 extractor's headless regression only."""

from __future__ import annotations

from pathlib import Path

TARGET = Path("tools/apply_dashboard_visibility_wave_24.py")
SELF = Path(__file__)

OLD = '''    module = importlib.import_module("spina_app.tabs.dashboard")
    for name in TARGETS:
'''
NEW = '''    module = importlib.import_module("spina_app.tabs.dashboard")
    module.tk.StringVar = lambda value="": Var(value)
    for name in TARGETS:
'''


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    if text.count(OLD) != 1:
        raise SystemExit("Expected Wave 24 regression insertion point was not found exactly once")
    TARGET.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    SELF.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
