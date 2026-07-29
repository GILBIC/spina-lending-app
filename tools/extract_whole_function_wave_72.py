from __future__ import annotations

import ast
import hashlib
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
EXPECTED_RAW_SHA256 = "8b7155b1a9a09a4a6382ef07f49a7413a38cd00c6810a639290311751557b783"
EXPECTED_AST_SHA256 = "89c90643ea9ca729c4c7764e9784219ca96358f681c41310d8cc757035996c72"
BINDING = '''# Wave 72: complete active theme application function.\nfrom spina_app.theme_application import (\n    configure_theme_application_dependencies as _configure_wave72_theme,\n    set_theme as _wave72_set_theme,\n)\n_configure_wave72_theme(globals())\nApp.set_theme = _wave72_set_theme\n\n\n'''
MARKER = "if __name__ == '__main__':"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)

    app = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "App"
    )
    method = next(
        node for node in app.body
        if isinstance(node, ast.FunctionDef) and node.name == "set_theme"
    )
    start = method.lineno
    end = method.end_lineno or method.lineno
    raw = "".join(lines[start - 1:end])

    assert end - start + 1 == 60
    assert _sha256(raw) == EXPECTED_RAW_SHA256
    assert _sha256(ast.dump(method, include_attributes=False)) == EXPECTED_AST_SHA256
    assert text.count(MARKER) == 1
    assert "App.set_theme = _wave72_set_theme" not in text

    cleaned = "".join(lines[:start - 1] + lines[end:])
    cleaned = cleaned.replace(MARKER, BINDING + MARKER, 1)

    verified = ast.parse(cleaned)
    verified_app = next(
        node for node in verified.body
        if isinstance(node, ast.ClassDef) and node.name == "App"
    )
    assert not any(
        isinstance(node, ast.FunctionDef) and node.name == "set_theme"
        for node in verified_app.body
    )
    assert cleaned.count("App.set_theme = _wave72_set_theme") == 1
    assert cleaned.index("App.set_theme = _wave72_set_theme") < cleaned.index(MARKER)

    SOURCE.write_text(cleaned, encoding="utf-8")
    print(f"Removed complete App.set_theme lines {start}-{end} and installed Wave 72 binding")


if __name__ == "__main__":
    main()
