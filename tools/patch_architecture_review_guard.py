"""Temporarily correct the architecture review fixer before execution."""

from pathlib import Path

PATH = Path(__file__).with_name("fix_architecture_map_review.py")
text = PATH.read_text(encoding="utf-8-sig")
old = '''def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
'''
new = '''def git_blob_sha(path: Path) -> str:
    data = path.read_bytes().replace(b"\\r\\n", b"\\n")
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
old_sub = "updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)"
new_sub = "updated, count = re.subn(pattern, lambda _match: replacement, text, count=1, flags=re.DOTALL)"
assert text.count(old_sub) == 1, "Expected one direct re.sub replacement"
text = text.replace(old_sub, new_sub, 1)

start_marker = "name = str(value).strip().strip("
start = text.find(start_marker)
assert start >= 0, "Generated SQL identifier expression was not found"
end = text.find(".lower()", start)
assert end >= 0, "Generated SQL identifier expression has no lower() suffix"
end += len(".lower()")
text = text[:start] + "name = str(value).strip().lower()" + text[end:]

PATH.write_text(text, encoding="utf-8")
print("Corrected temporary architecture review fixer.")
