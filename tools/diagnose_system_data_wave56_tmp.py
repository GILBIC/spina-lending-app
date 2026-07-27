from __future__ import annotations

import ast
import hashlib
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"


def main() -> None:
    import spina_app.system_data_presentation as module

    module_source = inspect.getsource(module._build_system_data_tab)
    app_text = APP.read_text(encoding="utf-8-sig")
    tree = ast.parse(app_text, filename=str(APP))
    method_present = False
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "App":
            method_present = any(
                isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and child.name == "_build_system_data_tab"
                for child in node.body
            )
            break

    checks = {
        "target": module.SYSTEM_DATA_PRESENTATION_TARGET == "_build_system_data_tab",
        "lines_metadata": module.SYSTEM_DATA_PRESENTATION_SOURCE_LINES == 46,
        "source_sha_metadata": module.SYSTEM_DATA_PRESENTATION_SOURCE_SHA256 == "b4d8ff8e73daca66a7aa4d6d5e8e08fe5d91648f04c7a2e485fb0677add79f3d",
        "signature": module.SYSTEM_DATA_PRESENTATION_SIGNATURE == "self",
        "inspect_line_count": len(module_source.splitlines()) == 46,
        "inspect_hash": hashlib.sha256(module_source.encode("utf-8")).hexdigest() == module.SYSTEM_DATA_PRESENTATION_DEDENTED_SHA256,
        "original_method_removed": not method_present,
        "configure_count": app_text.count("_configure_wave56_system_data_presentation(globals())") == 1,
        "binding_count": app_text.count("App._build_system_data_tab = _wave56_build_system_data_tab") == 1,
    }
    print("Wave 56 diagnostic values:")
    print("inspect lines:", len(module_source.splitlines()))
    print("inspect hash:", hashlib.sha256(module_source.encode("utf-8")).hexdigest())
    print("metadata dedented hash:", module.SYSTEM_DATA_PRESENTATION_DEDENTED_SHA256)
    print("configure count:", app_text.count("_configure_wave56_system_data_presentation(globals())"))
    print("binding count:", app_text.count("App._build_system_data_tab = _wave56_build_system_data_tab"))
    for name, passed in checks.items():
        print(f"{name}: {'PASS' if passed else 'FAIL'}")
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise SystemExit("Failed checks: " + ", ".join(failed))


if __name__ == "__main__":
    main()
