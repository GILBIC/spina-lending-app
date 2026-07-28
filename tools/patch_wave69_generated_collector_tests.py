from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WAVE43 = ROOT / "tools" / "test_collector_dialog_presentation_wave_43.py"
WAVE69 = ROOT / "tools" / "test_legacy_collector_editor_cleanup_wave_69.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"Expected one {label}; found {text.count(old)}")
    return text.replace(old, new, 1)


def main() -> None:
    wave43 = WAVE43.read_text(encoding="utf-8")
    wave43 = replace_once(
        wave43,
        '''    binding_line = desktop_text[:desktop_text.index(binding)].count("\\n") + 1
    main_index = desktop_text.rfind("\\ndef main(")
    assert main_index > 0
    main_line = desktop_text[:main_index].count("\\n") + 1
    assert binding_line < main_line
''',
        '''    binding_index = desktop_text.index(binding)
    startup_index = desktop_text.rfind('if __name__ == "__main__":')
    assert startup_index > binding_index
''',
        "Wave 43 startup assertion",
    )
    ast.parse(wave43, filename=str(WAVE43))
    WAVE43.write_text(wave43, encoding="utf-8")

    wave69 = WAVE69.read_text(encoding="utf-8")
    wave69 = replace_once(
        wave69,
        '''    binding_index = desktop_text.index(ACTIVE_BINDING)
    main_index = desktop_text.rfind("\\ndef main(")
    assert binding_index < main_index
''',
        '''    binding_index = desktop_text.index(ACTIVE_BINDING)
    startup_index = desktop_text.rfind('if __name__ == "__main__":')
    assert startup_index > binding_index
''',
        "Wave 69 startup assertion",
    )
    ast.parse(wave69, filename=str(WAVE69))
    WAVE69.write_text(wave69, encoding="utf-8")
    print("Wave 69 generated collector test startup assertions patched.")


if __name__ == "__main__":
    main()
