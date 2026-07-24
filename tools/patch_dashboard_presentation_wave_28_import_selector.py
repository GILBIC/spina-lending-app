"""Patch the temporary Wave 28 extractor for import and callback ordering."""

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

old_ordering = '''    main_node = source_nodes.get("main")
    assert main_node is not None, "Desktop main() function is missing"
    assert source_nodes["_spina_v18_draw_dashboard_charts"].lineno < main_node.lineno
    assert source_nodes["_spina_v20_draw_dashboard_charts"].lineno < main_node.lineno
'''
new_ordering = '''    launch_guards = [
        node for node in source_tree.body
        if isinstance(node, ast.If)
        and ast.unparse(node.test).replace('"', "'") == "__name__ == '__main__'"
    ]
    assert len(launch_guards) == 1, len(launch_guards)
    launch_guard = launch_guards[0]
    assert source_nodes["_spina_v18_draw_dashboard_charts"].lineno < launch_guard.lineno
    assert source_nodes["_spina_v20_draw_dashboard_charts"].lineno < launch_guard.lineno
'''
assert text.count(old_ordering) == 1, "Wave 28 callback ordering guard changed"
text = text.replace(old_ordering, new_ordering)

old_insertion = '''            main_node.lineno - 1,
            main_node.lineno - 1,
            f"# Dashboard presentation callback bridge configured in Wave 28.\n{configure_alias}(\n    draw_v18_charts=_spina_v18_draw_dashboard_charts,\n    draw_v20_charts=_spina_v20_draw_dashboard_charts,\n)\n\n",
'''
new_insertion = '''            launch_guard.lineno - 1,
            launch_guard.lineno - 1,
            f"# Dashboard presentation callback bridge configured in Wave 28.\n{configure_alias}(\n    draw_v18_charts=_spina_v18_draw_dashboard_charts,\n    draw_v20_charts=_spina_v20_draw_dashboard_charts,\n)\n\n",
'''
assert text.count(old_insertion) == 1, "Wave 28 callback insertion point changed"
text = text.replace(old_insertion, new_insertion)

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
print("Wave 28 Dashboard import and callback-order patches applied")
