from pathlib import Path

path = Path(__file__).resolve().parent / "fix_tk_shutdown_wave_46.py"
text = path.read_text(encoding="utf-8")

old_repair = '    assert updated.count("self.root.after_cancel(after_id)") == 1\n'
new_repair = (
    '    prepare_start = updated.index("    def _prepare_tk_shutdown(self):")\n'
    '    destroy_start = updated.index("    def _destroy_root_safely(self):", prepare_start)\n'
    '    prepare_source = updated[prepare_start:destroy_start]\n'
    '    assert prepare_source.count("self.root.after_cancel(after_id)") == 1\n'
)
old_test = '    assert text.count("self.root.after_cancel(after_id)") == 1\n'
new_test = (
    '    prepare_start = text.index("    def _prepare_tk_shutdown(self):")\n'
    '    destroy_start = text.index("    def _destroy_root_safely(self):", prepare_start)\n'
    '    prepare_source = text[prepare_start:destroy_start]\n'
    '    assert prepare_source.count("self.root.after_cancel(after_id)") == 1\n'
)

assert text.count(old_repair) == 1
assert text.count(old_test) == 1
text = text.replace(old_repair, new_repair)
text = text.replace(old_test, new_test)
path.write_text(text, encoding="utf-8")
print("Narrowed Wave 46 shutdown cancellation guards.")
