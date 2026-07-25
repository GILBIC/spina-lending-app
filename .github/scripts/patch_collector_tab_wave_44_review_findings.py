from __future__ import annotations

from pathlib import Path

MODULE = Path("spina_app/collector_tab_presentation.py")
REGRESSION_TEST = Path("tools/test_collector_tab_presentation_wave_44.py")
WIDGET_TEST = Path("tools/test_collector_tab_widget_smoke_wave_44.py")
EXPECTED_NESTED = ["_set_sort", "_select_status", "_popup", "_on_search"]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one guarded match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    replace_once(
        MODULE,
        "COLLECTOR_TAB_NESTED_CALLBACKS = []",
        f"COLLECTOR_TAB_NESTED_CALLBACKS = {EXPECTED_NESTED!r}",
    )

    replace_once(
        REGRESSION_TEST,
        "EXPECTED_SIGNATURE = 'self'\nSQL_WRITE_RE =",
        "EXPECTED_SIGNATURE = 'self'\n"
        f"EXPECTED_NESTED = {EXPECTED_NESTED!r}\n"
        "SQL_WRITE_RE =",
    )
    replace_once(
        REGRESSION_TEST,
        "    assert module.COLLECTOR_TAB_NESTED_CALLBACKS == []",
        "    assert module.COLLECTOR_TAB_NESTED_CALLBACKS == EXPECTED_NESTED",
    )
    replace_once(
        REGRESSION_TEST,
        "    assert [n.name for n in fn.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))] == []",
        "    nested = [\n"
        "        node.name\n"
        "        for node in sorted(\n"
        "            (\n"
        "                node\n"
        "                for node in ast.walk(fn)\n"
        "                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))\n"
        "                and node is not fn\n"
        "            ),\n"
        "            key=lambda node: node.lineno,\n"
        "        )\n"
        "    ]\n"
        "    assert nested == EXPECTED_NESTED",
    )

    replace_once(
        WIDGET_TEST,
        "        presentation._spina_v27_route_colors = _route_colors\n"
        "        presentation._spina_v27_route_button = _route_button\n"
        "        presentation._spina_v27_route_card = _route_card\n"
        "        presentation._spina_v27_style_route_trees = _style_route_trees\n"
        "        presentation._spina_v27_hidden_collector_widgets = _hidden_widgets\n"
        "        presentation._spina_v27_update_route_cards = _update_cards\n"
        "        presentation._log_exc = lambda context, exc: logged.append((context, str(exc)))",
        "        logged_callback = lambda context, exc: logged.append((context, str(exc)))\n"
        "        dependencies = {\n"
        "            '_spina_v27_route_colors': _route_colors,\n"
        "            '_spina_v27_route_button': _route_button,\n"
        "            '_spina_v27_route_card': _route_card,\n"
        "            '_spina_v27_style_route_trees': _style_route_trees,\n"
        "            '_spina_v27_hidden_collector_widgets': _hidden_widgets,\n"
        "            '_spina_v27_update_route_cards': _update_cards,\n"
        "            '_log_exc': logged_callback,\n"
        "        }\n"
        "        presentation.configure_collector_tab_dependencies(dependencies)\n"
        "        assert presentation._COLLECTOR_TAB_DEPENDENCIES == dependencies\n"
        "        for name, value in dependencies.items():\n"
        "            assert getattr(presentation, name) is value",
    )

    print("Wave 44 review findings patched successfully.")


if __name__ == "__main__":
    main()
