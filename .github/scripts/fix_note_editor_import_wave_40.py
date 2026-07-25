from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "spina_app" / "note_editor_presentation.py"
TEST = ROOT / "tools" / "test_note_editor_presentation_wave_40.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one {label} marker, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    module_text = MODULE.read_text(encoding="utf-8")
    if "import tkinter as tk" not in module_text:
        module_text = replace_once(
            module_text,
            "from __future__ import annotations\n\n",
            "from __future__ import annotations\n\n"
            "import tkinter as tk\n"
            "from tkinter import messagebox, ttk\n\n",
            "module future import",
        )
    MODULE.write_text(module_text, encoding="utf-8")

    test_text = TEST.read_text(encoding="utf-8")
    if "import importlib.util" not in test_text:
        test_text = replace_once(
            test_text,
            "import hashlib\nimport textwrap\n",
            "import hashlib\nimport importlib.util\nimport textwrap\n",
            "test imports",
        )
    if "wave40_note_editor_import_smoke" not in test_text:
        test_text = replace_once(
            test_text,
            "def main():\n    module_text = MODULE.read_text(encoding=\"utf-8\")\n",
            "def main():\n"
            "    spec = importlib.util.spec_from_file_location(\n"
            "        \"wave40_note_editor_import_smoke\", MODULE\n"
            "    )\n"
            "    assert spec is not None and spec.loader is not None\n"
            "    imported = importlib.util.module_from_spec(spec)\n"
            "    spec.loader.exec_module(imported)\n"
            "    assert issubclass(imported.NoteEditorDialog, imported.tk.Toplevel)\n\n"
            "    module_text = MODULE.read_text(encoding=\"utf-8\")\n",
            "test main import smoke",
        )
    TEST.write_text(test_text, encoding="utf-8")

    print("Applied Wave 40 Tkinter import fix and runtime import regression.")


if __name__ == "__main__":
    main()
