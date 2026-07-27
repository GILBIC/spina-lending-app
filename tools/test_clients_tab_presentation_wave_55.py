from __future__ import annotations

import ast
import hashlib
from pathlib import Path

MAIN = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE = Path("spina_app/clients_tab_presentation.py")
EXPECTED_LINES = 156
EXPECTED_SHA256 = '21bd95f29f41585b1d27aea3296657e91b7a0e4dcaebb13c9820c63a7abb83b4'


def _function_source(path: Path, name: str) -> str:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    lines = src.splitlines(keepends=True)
    return "".join(lines[fn.lineno - 1:fn.end_lineno])


def main() -> None:
    module_source = _function_source(MODULE, "_build_clients_tab")
    assert len(module_source.splitlines()) == EXPECTED_LINES
    assert hashlib.sha256(module_source.encode("utf-8")).hexdigest() == EXPECTED_SHA256

    main_src = MAIN.read_text(encoding="utf-8")
    main_tree = ast.parse(main_src)
    app = next(n for n in main_tree.body if isinstance(n, ast.ClassDef) and n.name == "App")
    assert not any(isinstance(n, ast.FunctionDef) and n.name == "_build_clients_tab" for n in app.body)
    assert main_src.count("# Wave 55: Clients tab construction presentation.") == 1
    assert main_src.count("App._build_clients_tab = _wave55_build_clients_tab") == 1
    assert main_src.count("configure_clients_tab_presentation_dependencies") == 1

    import spina_app.clients_tab_presentation as module
    assert module.CLIENTS_TAB_PRESENTATION_SOURCE_LINES == EXPECTED_LINES
    assert module.CLIENTS_TAB_PRESENTATION_SOURCE_SHA256 == EXPECTED_SHA256
    assert module.CLIENTS_TAB_PRESENTATION_SIGNATURE == "self"
    forbidden = (".execute", ".executemany", ".commit", ".rollback", ".write", ".unlink", ".remove")
    assert not [c for c in module.CLIENTS_TAB_PRESENTATION_CALLS if c == "open" or c.endswith(forbidden)]
    print("Wave 55 exact Clients-tab extraction regression passed")


if __name__ == "__main__":
    main()
