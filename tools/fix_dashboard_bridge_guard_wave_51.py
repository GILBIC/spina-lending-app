from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTRACTOR = ROOT / "tools" / "extract_dashboard_charts_wave_51.py"
TEST = ROOT / "tools" / "test_dashboard_chart_presentation_wave_51.py"

EXTRACTOR_OLD = '''    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        fn = dotted(call.func)
        if not fn.endswith("configure_legacy_dashboard_feature"):
            continue
        kw = {item.arg: dotted(item.value) for item in call.keywords if item.arg}
        if kw.get("draw_v18_charts") == "_spina_v18_draw_dashboard_charts" and kw.get("draw_v20_charts") == "_spina_v20_draw_dashboard_charts":
            candidates.append((call.lineno, kw))
'''
EXTRACTOR_NEW = '''    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        kw = {item.arg: dotted(item.value) for item in call.keywords if item.arg}
        if kw.get("draw_v18_charts") == "_spina_v18_draw_dashboard_charts" and kw.get("draw_v20_charts") == "_spina_v20_draw_dashboard_charts":
            candidates.append((call.lineno, dotted(call.func), kw))
'''

TEST_OLD = '''    for call in (node for node in ast.walk(desktop_tree) if isinstance(node, ast.Call)):
        if dotted(call.func).endswith("configure_legacy_dashboard_feature"):
            kw = {item.arg: dotted(item.value) for item in call.keywords if item.arg}
            if kw.get("draw_v18_charts") == "_spina_v18_draw_dashboard_charts" and kw.get("draw_v20_charts") == "_spina_v20_draw_dashboard_charts":
                bridge_calls.append((call.lineno, kw))
'''
TEST_NEW = '''    for call in (node for node in ast.walk(desktop_tree) if isinstance(node, ast.Call)):
        kw = {item.arg: dotted(item.value) for item in call.keywords if item.arg}
        if kw.get("draw_v18_charts") == "_spina_v18_draw_dashboard_charts" and kw.get("draw_v20_charts") == "_spina_v20_draw_dashboard_charts":
            bridge_calls.append((call.lineno, dotted(call.func), kw))
'''


def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one bridge-guard block in {path.name}; found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    replace_exact(EXTRACTOR, EXTRACTOR_OLD, EXTRACTOR_NEW)
    replace_exact(TEST, TEST_OLD, TEST_NEW)
    print("Wave 51 dashboard bridge guard now resolves by exact callback keywords, independent of alias name.")


if __name__ == "__main__":
    main()
