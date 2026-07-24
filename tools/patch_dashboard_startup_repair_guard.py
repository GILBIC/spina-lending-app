"""Patch the temporary Dashboard startup repair to compare post-edit line numbers."""

from pathlib import Path

PATH = Path(__file__).resolve().with_name("fix_dashboard_startup_wave_28.py")
text = PATH.read_text(encoding="utf-8")

old = '''    assert len(complete_imports) == 1
    assert complete_imports[0].lineno < first_use_line
'''
new = '''    assert len(complete_imports) == 1
    final_runtime_uses = top_level_runtime_uses(new_tree)
    assert final_runtime_uses, "Dashboard App wiring disappeared after import move"
    final_first_use_line = min(line for line, _, _ in final_runtime_uses)
    assert complete_imports[0].lineno < final_first_use_line, (
        complete_imports[0].lineno,
        final_first_use_line,
    )
'''

assert text.count(old) == 1, "Dashboard repair post-edit guard changed"
PATH.write_text(text.replace(old, new), encoding="utf-8")
print("Dashboard repair post-edit line-order guard corrected")
