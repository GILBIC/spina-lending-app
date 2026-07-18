#!/usr/bin/env python3
"""Audit and optionally remove stale generated Data Bank export cleanup blocks.

This tool is intentionally two-step:

1. Run without flags to show candidate generated cleanup/hide block ranges.
2. Run with --apply only after reviewing the printed ranges.

It refuses to remove anything unless every remaining reference to the removed
Data Bank export callback names is inside a generated Data Bank cleanup/hide
block, and the candidate block does not contain protected lending/report logic.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

APP_FILE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
TARGET_NAMES = (
    "export_jsonl_month",
    "export_daily_collection_template",
)

# The first tool version limited ranges to 520 lines. One older generated
# fallback block has been observed at 587 lines, so allow a slightly larger
# range only when all strict generated-block checks pass.
STANDARD_RANGE_LIMIT = 520
EXTENDED_GENERATED_RANGE_LIMIT = 700

# Markers that identify generated Data Bank cleanup/hide/destroy blocks.
# Some older generated blocks only contain the removed callback names plus helper
# labels, so the recognizable surface is intentionally broader than the first
# version of this tool. Safety checks below still require generated hide/destroy
# behavior and refuse protected lending/report logic.
GENERATED_MARKERS = (
    "data bank export",
    "databank export",
    "visible data bank export widgets",
    "databank_exports_removed",
    "_spina_databank",
    "_spina_remove_databank",
    "_spina_parent_has_databank_export_buttons",
    "_spina_original_app_init_for_databank_exports",
    "hide-only",
    "hide/destroy",
    "date range template",
    "jsonl month",
    "daily excel template",
    "daily collection excel template",
    "export_jsonl_month",
    "export_daily_collection_template",
)

EXPECTED_GENERATED_CODE_MARKERS = (
    "pack_forget",
    "grid_forget",
    "place_forget",
    "destroy",
    "winfo_children",
    "winfo_parent",
    "App.__init__",
    "_spina_original_app_init",
    "configure(command=",
    "cget(\"command\")",
    "cget('command')",
)

PROTECTED_TERMS = (
    "balance",
    "7x7",
    "interest",
    "payment allocation",
    "principal",
    "collector route",
    "client statement",
    "statement pdf",
    "note storage",
    "note rendering",
    "loan balance",
    "daily ledger total",
    "database writes",
    "insert into",
    "update ",
    "delete from",
    "create table",
)


def _line_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def _find_callback_definitions(lines: list[str]) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        for name in TARGET_NAMES:
            if re.match(rf"^[ \t]*def\s+{re.escape(name)}\s*\(", line):
                hits.append((i + 1, line.rstrip("\n")))
    return hits


def _target_reference_lines(lines: list[str]) -> list[int]:
    pattern = re.compile(r"\b(" + "|".join(re.escape(name) for name in TARGET_NAMES) + r")\b")
    return [i for i, line in enumerate(lines) if pattern.search(line)]


def _has_marker(text: str) -> bool:
    lower = text.lower()
    return any(marker.lower() in lower for marker in GENERATED_MARKERS)


def _has_expected_generated_code(text: str) -> bool:
    lower = text.lower()
    return any(marker.lower() in lower for marker in EXPECTED_GENERATED_CODE_MARKERS)


def _protected_hits(text: str) -> list[str]:
    lower = text.lower()
    return [term for term in PROTECTED_TERMS if term.lower() in lower]


def _split_comment_and_code_lines(lines: list[str]) -> tuple[list[str], list[str]]:
    """Split Python source lines into comment-only lines and everything else.

    Protected terms in comments are safety notes, not executable lending/report
    logic. Protected terms in strings or executable code still count as code and
    keep the cleanup blocked.
    """
    comment_lines: list[str] = []
    code_lines: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#"):
            comment_lines.append(line)
        else:
            code_lines.append(line)
    return comment_lines, code_lines


def _protected_hits_in_code(lines: list[str]) -> list[str]:
    _comment_lines, code_lines = _split_comment_and_code_lines(lines)
    return _protected_hits("".join(code_lines))


def _protected_hits_in_comments(lines: list[str]) -> list[str]:
    comment_lines, _code_lines = _split_comment_and_code_lines(lines)
    return _protected_hits("".join(comment_lines))


def _looks_like_generated_databank_cleanup_block(text: str) -> bool:
    """Return True only for generated cleanup/hide block shapes."""
    lower = text.lower()
    target_present = any(name in text for name in TARGET_NAMES)
    old_ui_label_present = any(
        phrase in lower
        for phrase in (
            "exports",
            "date range template",
            "jsonl month",
            "daily excel template",
            "daily collection excel template",
        )
    )
    generated_helper_present = any(
        phrase in lower
        for phrase in (
            "_spina_",
            "winfo_children",
            "pack_forget",
            "grid_forget",
            "place_forget",
            "destroy",
            "configure(command=",
            "cget(\"command\")",
            "cget('command')",
        )
    )
    return target_present and generated_helper_present and (_has_marker(text) or old_ui_label_present)


def _is_possible_block_start(line: str) -> bool:
    stripped = line.strip()
    lower = stripped.lower()
    if not stripped:
        return False
    if _line_indent(line) != 0:
        return False
    return (
        stripped.startswith("#")
        or stripped.startswith("def _spina")
        or stripped.startswith("try:")
        or stripped.startswith("App.__init__")
        or stripped.startswith("_spina")
        or stripped.startswith("DATA_BANK")
        or stripped.startswith("DATABANK")
        or "data bank export" in lower
        or "databank export" in lower
    )


def _is_possible_block_boundary(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _line_indent(line) != 0:
        return False
    if stripped.startswith("if __name__ =="):
        return True
    if stripped.startswith("class "):
        return True
    if stripped.startswith("def ") and not stripped.startswith("def _spina"):
        return True
    return False


def _next_boundary_after(lines: list[str], start: int, ref_index: int, limit: int = 900) -> int | None:
    n = len(lines)
    for i in range(ref_index + 1, min(n, ref_index + limit)):
        if _is_possible_block_boundary(lines[i]):
            return i
    for i in range(ref_index + 1, min(n, ref_index + limit)):
        if i + 1 < n and not lines[i].strip() and lines[i + 1].strip() and _line_indent(lines[i + 1]) == 0:
            probe = "".join(lines[start : i + 1])
            if _looks_like_generated_databank_cleanup_block(probe):
                return i + 1
    return None


def _candidate_range_for_reference(lines: list[str], ref_index: int) -> tuple[int, int] | None:
    """Return 0-based [start, end) candidate range for a stale generated block."""
    # Prefer an explicit nearby Data Bank export marker before the reference.
    start = None
    for i in range(ref_index, max(-1, ref_index - 900), -1):
        if _has_marker(lines[i]) and _is_possible_block_start(lines[i]):
            start = i
        elif start is None and _is_possible_block_start(lines[i]):
            window = "".join(lines[i : ref_index + 1])
            if _looks_like_generated_databank_cleanup_block(window):
                start = i
    if start is not None:
        # Include adjacent generated setup/comment lines directly above the detected start.
        while start > 0:
            prev = lines[start - 1]
            if not prev.strip():
                start -= 1
                continue
            if _line_indent(prev) == 0 and (_has_marker(prev) or prev.strip().startswith("#")):
                start -= 1
                continue
            break
        end = _next_boundary_after(lines, start, ref_index)
        if end is not None:
            return start, end

    # Fallback for older generated blocks whose first reference is inside a
    # plain list/tuple and whose comments lack the newer marker phrases.
    top_level_starts: list[int] = []
    for i in range(ref_index, max(-1, ref_index - 900), -1):
        if lines[i].strip() and _line_indent(lines[i]) == 0:
            top_level_starts.append(i)

    for candidate_start in top_level_starts:
        end = _next_boundary_after(lines, candidate_start, ref_index)
        if end is None:
            continue
        block_text = "".join(lines[candidate_start:end])
        if _looks_like_generated_databank_cleanup_block(block_text):
            return candidate_start, end

    return None


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not ranges:
        return []
    ranges = sorted(ranges)
    merged = [ranges[0]]
    for start, end in ranges[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _remove_ranges(lines: list[str], ranges: list[tuple[int, int]]) -> list[str]:
    remove = [False] * len(lines)
    for start, end in ranges:
        for i in range(start, end):
            remove[i] = True
    return [line for i, line in enumerate(lines) if not remove[i]]


def _format_terms(terms: list[str]) -> str:
    return ", ".join(terms[:8])


def _safety_check_range(lines: list[str], start: int, end: int) -> tuple[bool, str | None]:
    block_lines = lines[start:end]
    text = "".join(block_lines)
    length = end - start
    protected = _protected_hits_in_code(block_lines)
    ignored_comment_terms = _protected_hits_in_comments(block_lines)

    if length > EXTENDED_GENERATED_RANGE_LIMIT:
        return False, f"range {start + 1}-{end}: too large ({length} lines; limit {EXTENDED_GENERATED_RANGE_LIMIT})"
    if length > STANDARD_RANGE_LIMIT:
        # Larger ranges are allowed only when all strict generated-block checks
        # pass. The dry run prints a review note before --apply is used.
        if not _looks_like_generated_databank_cleanup_block(text):
            return False, f"range {start + 1}-{end}: large range missing generated Data Bank cleanup markers"
        if not _has_expected_generated_code(text):
            return False, f"range {start + 1}-{end}: large range missing expected hide/destroy generated code marker"
        if protected:
            return False, f"range {start + 1}-{end}: protected terms found in code: {_format_terms(protected)}"
        if ignored_comment_terms:
            return True, (
                f"large recognized generated cleanup range ({length} lines); "
                f"ignored protected terms in comments: {_format_terms(ignored_comment_terms)}"
            )
        return True, f"large recognized generated cleanup range ({length} lines)"

    if not _looks_like_generated_databank_cleanup_block(text):
        return False, f"range {start + 1}-{end}: missing generated Data Bank cleanup markers"
    if not _has_expected_generated_code(text):
        return False, f"range {start + 1}-{end}: missing expected hide/destroy generated code marker"
    if protected:
        return False, f"range {start + 1}-{end}: protected terms found in code: {_format_terms(protected)}"
    if ignored_comment_terms:
        return True, f"ignored protected terms in comments: {_format_terms(ignored_comment_terms)}"
    return True, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Remove the printed safe candidate ranges.")
    args = parser.parse_args(argv)

    print("[SPINA] Stale Data Bank generated-block cleanup starting...", flush=True)

    if not APP_FILE.exists():
        print(f"[SPINA][ERROR] Missing app file: {APP_FILE}", flush=True)
        return 2

    source = APP_FILE.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)

    callback_defs = _find_callback_definitions(lines)
    if callback_defs:
        print("[SPINA][STOP] Data Bank export callbacks still exist. Run cleanup_databank_export_callbacks.py first.", flush=True)
        for line_no, text in callback_defs[:20]:
            print(f"  line {line_no}: {text}", flush=True)
        return 1

    ref_indexes = _target_reference_lines(lines)
    if not ref_indexes:
        print("[SPINA] No leftover Data Bank export callback references found. Nothing to remove.", flush=True)
        return 0

    print(f"[SPINA] Remaining target-name references found: {len(ref_indexes)}", flush=True)
    for idx in ref_indexes[:20]:
        print(f"  line {idx + 1}: {lines[idx].rstrip()}", flush=True)
    if len(ref_indexes) > 20:
        print(f"  ... {len(ref_indexes) - 20} more", flush=True)

    candidate_ranges: list[tuple[int, int]] = []
    unresolved: list[int] = []
    for idx in ref_indexes:
        candidate = _candidate_range_for_reference(lines, idx)
        if candidate is None:
            unresolved.append(idx)
        else:
            candidate_ranges.append(candidate)

    candidate_ranges = _merge_ranges(candidate_ranges)

    safe_ranges: list[tuple[int, int]] = []
    review_notes: list[str] = []
    unsafe_messages: list[str] = []
    for start, end in candidate_ranges:
        ok, message = _safety_check_range(lines, start, end)
        if ok:
            safe_ranges.append((start, end))
            if message:
                review_notes.append(f"range {start + 1}-{end}: {message}")
        else:
            unsafe_messages.append(message or f"range {start + 1}-{end}: failed safety checks")

    for start, end in safe_ranges:
        print(f"[SPINA] Safe candidate range: lines {start + 1}-{end} ({end - start} lines)", flush=True)
        print(f"  first: {lines[start].rstrip()}", flush=True)
        print(f"  last : {lines[end - 1].rstrip()}", flush=True)

    for note in review_notes:
        print(f"[SPINA][REVIEW] {note}", flush=True)

    if unresolved:
        print("[SPINA][STOP] Some references are not inside a recognized generated Data Bank cleanup block.", flush=True)
        for idx in unresolved[:20]:
            print(f"  line {idx + 1}: {lines[idx].rstrip()}", flush=True)
        return 1

    if unsafe_messages:
        print("[SPINA][STOP] Candidate block failed safety checks.", flush=True)
        for message in unsafe_messages:
            print(f"  {message}", flush=True)
        return 1

    covered = set()
    for start, end in safe_ranges:
        covered.update(range(start, end))
    outside = [idx for idx in ref_indexes if idx not in covered]
    if outside:
        print("[SPINA][STOP] Some target references are outside safe candidate ranges.", flush=True)
        for idx in outside[:20]:
            print(f"  line {idx + 1}: {lines[idx].rstrip()}", flush=True)
        return 1

    if not safe_ranges:
        print("[SPINA] No safe generated block ranges found. Nothing changed.", flush=True)
        return 0

    if not args.apply:
        print("[SPINA] Dry run only. Review the ranges above.", flush=True)
        print("[SPINA] To remove them, run: python tools\\cleanup_stale_databank_generated_blocks.py --apply", flush=True)
        return 0

    new_lines = _remove_ranges(lines, safe_ranges)
    removed_lines = len(lines) - len(new_lines)
    APP_FILE.write_text("".join(new_lines), encoding="utf-8")
    print(f"[SPINA] Removed generated stale Data Bank cleanup ranges: {len(safe_ranges)}", flush=True)
    print(f"[SPINA] Removed source lines: {removed_lines}", flush=True)
    print("[SPINA] Done. Run py_compile and test Data Bank.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
