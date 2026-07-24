"""Temporarily align the Wave 25 theme hash guard with the read-only inventory."""

from pathlib import Path

TARGET = Path("tools/apply_login_palette_wave_25.py")
OLD = '''    theme_base_text = THEME_MODULE.read_text(encoding="utf-8")
    theme_sha = hashlib.sha256(theme_base_text.encode("utf-8")).hexdigest()
'''
NEW = '''    theme_bytes = THEME_MODULE.read_bytes()
    theme_sha = hashlib.sha256(theme_bytes).hexdigest()
    theme_base_text = theme_bytes.decode("utf-8").replace("\\r\\n", "\\n").replace("\\r", "\\n")
'''


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    if text.count(OLD) != 1:
        raise SystemExit("Expected Wave 25 theme hash guard was not found exactly once")
    TARGET.write_text(text.replace(OLD, NEW), encoding="utf-8")
    Path(__file__).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
