from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    ROOT / "tools" / "extract_ui_button_factories_wave_50.py",
    ROOT / "tools" / "test_ui_button_factories_wave_50.py",
)
OLD = "f5b787feb012af35a41a6976af63684e01e958694d5b75e91df8d0b7a2af1c8"
NEW = "f5b787f580fd4202ebbc324e70da4a8c2adee5190e959c3af01b0e2402b32e92"


def main() -> None:
    for path in FILES:
        text = path.read_text(encoding="utf-8")
        assert text.count(OLD) == 1, (path, text.count(OLD))
        assert NEW not in text, path
        path.write_text(text.replace(OLD, NEW), encoding="utf-8")
        print(f"Updated protected caller hash in {path.name}")


if __name__ == "__main__":
    main()
