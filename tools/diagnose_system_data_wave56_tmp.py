from __future__ import annotations

import ast
import hashlib
import inspect
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave-56-diagnostic.json"


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

    inspect_hash = hashlib.sha256(module_source.encode("utf-8")).hexdigest()
    configure_count = app_text.count("_configure_wave56_system_data_presentation(globals())")
    binding_count = app_text.count("App._build_system_data_tab = _wave56_build_system_data_tab")
    checks = {
        "target": module.SYSTEM_DATA_PRESENTATION_TARGET == "_build_system_data_tab",
        "lines_metadata": module.SYSTEM_DATA_PRESENTATION_SOURCE_LINES == 46,
        "source_sha_metadata": module.SYSTEM_DATA_PRESENTATION_SOURCE_SHA256 == "b4d8ff8e73daca66a7aa4d6d5e8e08fe5d91648f04c7a2e485fb0677add79f3d",
        "signature": module.SYSTEM_DATA_PRESENTATION_SIGNATURE == "self",
        "inspect_line_count": len(module_source.splitlines()) == 46,
        "inspect_hash": inspect_hash == module.SYSTEM_DATA_PRESENTATION_DEDENTED_SHA256,
        "original_method_removed": not method_present,
        "configure_count": configure_count == 1,
        "binding_count": binding_count == 1,
    }
    failed = [name for name, passed in checks.items() if not passed]
    result = {
        "checks": checks,
        "failed": failed,
        "inspect_lines": len(module_source.splitlines()),
        "inspect_hash": inspect_hash,
        "metadata_dedented_hash": module.SYSTEM_DATA_PRESENTATION_DEDENTED_SHA256,
        "configure_count": configure_count,
        "binding_count": binding_count,
        "method_present": method_present,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if failed:
        raise SystemExit("Failed checks: " + ", ".join(failed))


if __name__ == "__main__":
    main()
