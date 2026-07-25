"""Update the temporary Wave 30 extractor guard for the corrected regression test."""

from pathlib import Path

PATH = Path(__file__).resolve().with_name("apply_clients_read_presentation_wave_30.py")
text = PATH.read_text(encoding="utf-8")
old = 'TEST: "2f549071ab6f45c6d27e675a57236f54e94ee945",'
new = 'TEST: "64d44e18af4a53dcfe6b36159d4d6b9470e77856",'
assert text.count(old) == 1, "Wave 30 test blob guard changed"
PATH.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
print("Wave 30 test blob guard corrected")
