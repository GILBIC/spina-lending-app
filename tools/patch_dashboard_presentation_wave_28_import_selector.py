"""Patch the temporary Wave 28 extractor to select the correct Dashboard import block."""

from pathlib import Path

PATH = Path(__file__).resolve().with_name("apply_dashboard_presentation_wave_28.py")
text = PATH.read_text(encoding="utf-8")

old_selector = '''    dashboard_imports = [
        node for node in ast.walk(source_tree)
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.tabs.dashboard"
    ]
    assert len(dashboard_imports) == 1, len(dashboard_imports)
    dashboard_import = dashboard_imports[0]
    configure_alias = next(
'''
new_selector = '''    dashboard_imports = [
        node for node in ast.walk(source_tree)
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.tabs.dashboard"
    ]
    configure_imports = [
        node for node in dashboard_imports
        if any(alias.name == "configure_legacy_dashboard_feature" for alias in node.names)
    ]
    assert len(configure_imports) == 1, len(configure_imports)
    dashboard_import = configure_imports[0]
    configure_alias = next(
'''
assert text.count(old_selector) == 1, "Wave 28 initial Dashboard import selector changed"
text = text.replace(old_selector, new_selector)

old_final = '''    final_tree = ast.parse(final_source_text)
    final_dashboard_import = next(
        node for node in ast.walk(final_tree)
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.tabs.dashboard"
    )
    imported = {alias.asname or alias.name for alias in final_dashboard_import.names}
    assert set(TARGET_ORDER).issubset(imported)
'''
new_final = '''    final_tree = ast.parse(final_source_text)
    final_dashboard_imports = [
        node for node in ast.walk(final_tree)
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.tabs.dashboard"
    ]
    final_dashboard_import = next(
        node for node in final_dashboard_imports
        if set(TARGET_ORDER).issubset({alias.asname or alias.name for alias in node.names})
    )
    imported = {alias.asname or alias.name for alias in final_dashboard_import.names}
    assert set(TARGET_ORDER).issubset(imported)
'''
assert text.count(old_final) == 1, "Wave 28 final Dashboard import selector changed"
text = text.replace(old_final, new_final)

PATH.write_text(text, encoding="utf-8")
print("Wave 28 Dashboard import selector patch applied")
