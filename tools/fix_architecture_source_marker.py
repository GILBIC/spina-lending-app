"""Make the architecture source marker follow only SPINA application Python files."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "generate_architecture_map.py"
EXPECTED_GENERATOR_BLOB = "0b00091ae68cf231706363c1c124b901e850ac2d"


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    header = f"blob {len(data)}\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()


def main() -> None:
    assert git_blob_sha(GENERATOR) == EXPECTED_GENERATOR_BLOB, "Generator changed since marker review"
    text = GENERATOR.read_text(encoding="utf-8-sig")
    replacement = '''def git_sha() -> str:
    """Return the latest commit that changed SPINA application Python source.

    Architecture tools and generated documents are intentionally excluded. This keeps
    the marker deterministic while still identifying the desktop/module code version
    represented by the map.
    """
    try:
        return subprocess.check_output(
            [
                "git", "log", "-1", "--format=%H", "--",
                ":(glob)OFFICIAL_SPINA_APP_*.py",
                ":(glob)spina_app/**/*.py",
            ],
            cwd=ROOT,
            text=True,
        ).strip()
    except Exception:
        return "unknown"
'''
    text, count = re.subn(
        r"def git_sha\(\) -> str:.*?(?=\ndef rel)",
        lambda _match: replacement + "\n\n",
        text,
        count=1,
        flags=re.DOTALL,
    )
    assert count == 1, f"Expected one source marker function, found {count}"
    GENERATOR.write_text(text, encoding="utf-8")
    print("Architecture source marker now tracks only SPINA application Python files.")


if __name__ == "__main__":
    main()
