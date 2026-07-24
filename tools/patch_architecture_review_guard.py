"""Temporarily correct the review fixer's Git blob hash guard."""

from pathlib import Path

PATH = Path(__file__).with_name("fix_architecture_map_review.py")
text = PATH.read_text(encoding="utf-8-sig")
old = '''def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
'''
new = '''def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()
'''
assert text.count(old) == 1, "Expected one normal SHA-256 guard"
text = text.replace(old, new, 1)
text = text.replace(
    "assert sha256(GENERATOR) == EXPECTED_GENERATOR_SHA",
    "assert git_blob_sha(GENERATOR) == EXPECTED_GENERATOR_SHA",
    1,
)
text = text.replace(
    "assert sha256(TEST) == EXPECTED_TEST_SHA",
    "assert git_blob_sha(TEST) == EXPECTED_TEST_SHA",
    1,
)
PATH.write_text(text, encoding="utf-8")
print("Corrected temporary architecture review guard.")
