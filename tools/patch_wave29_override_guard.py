"""Correct the temporary Wave 29 late-toolbar override expectation."""

from pathlib import Path

PATH = Path(__file__).resolve().with_name("apply_navigation_databank_shell_wave_29.py")
text = PATH.read_text(encoding="utf-8")
old = "Name(id='_spina_dayclose_update_data_toolbar', ctx=Load())"
new = "Name(id='_spina_v15_update_data_toolbar', ctx=Load())"
assert text.count(old) == 1, "Wave 29 toolbar override guard changed"
PATH.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
print("Wave 29 toolbar override guard corrected")
