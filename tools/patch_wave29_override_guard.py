"""Correct temporary Wave 29 guards and exact method dedenting."""

from pathlib import Path

PATH = Path(__file__).resolve().with_name("apply_navigation_databank_shell_wave_29.py")
text = PATH.read_text(encoding="utf-8")

old_override = "Name(id='_spina_dayclose_update_data_toolbar', ctx=Load())"
new_override = "Name(id='_spina_v15_update_data_toolbar', ctx=Load())"
assert text.count(old_override) == 1, "Wave 29 toolbar override guard changed"
text = text.replace(old_override, new_override)

old_builder = '''def build_module(header: str, sources: list[str]) -> str:
    functions = [textwrap.dedent(source) for source in sources]
    return header.rstrip() + "\\n\\n\\n" + "\\n\\n\\n".join(functions) + "\\n"
'''
new_builder = '''def dedent_method_source(source: str) -> str:
    """Remove class indentation while preserving whitespace-only lines exactly."""
    result = []
    for line in source.splitlines():
        if line.strip():
            assert line.startswith("    "), repr(line)
            result.append(line[4:])
        else:
            result.append(line)
    return "\\n".join(result)


def build_module(header: str, sources: list[str]) -> str:
    functions = [dedent_method_source(source) for source in sources]
    return header.rstrip() + "\\n\\n\\n" + "\\n\\n\\n".join(functions) + "\\n"
'''
assert text.count(old_builder) == 1, "Wave 29 module builder changed"
text = text.replace(old_builder, new_builder)

PATH.write_text(text, encoding="utf-8", newline="\n")
print("Wave 29 override guard and exact dedenting corrected")
