#!/usr/bin/env python3
"""Inspect protected-term hits inside stale Data Bank generated cleanup ranges.

This is a read-only helper. It does not modify the SPINA app source.
Use it when cleanup_stale_databank_generated_blocks.py stops because a
candidate generated block contains protected words such as balance, 7x7, or
collector route. The output shows the exact local line numbers and nearby
context so the block can be reviewed before any deletion rule is relaxed.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

TOOL_FILE = Path(__file__).with_name("cleanup_stale_databank_generated_blocks.py")
CONTEXT_RADIUS = 2


def _load_cleanup_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("spina_cleanup_stale_databank", TOOL_FILE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load cleanup tool: {TOOL_FILE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _matching_terms(line: str, protected_terms: tuple[str, ...]) -> list[str]:
    lower = line.lower()
    return [term for term in protected_terms if term.lower() in lower]


def main() -> int:
    cleanup = _load_cleanup_tool()
    app_file: Path = cleanup.APP_FILE

    print("[SPINA] Inspecting stale Data Bank protected-term context...", flush=True)

    if not app_file.exists():
        print(f"[SPINA][ERROR] Missing app file: {app_file}", flush=True)
        return 2

    lines = app_file.read_text(encoding="utf-8").splitlines(keepends=True)

    callback_defs = cleanup._find_callback_definitions(lines)
    if callback_defs:
        print("[SPINA][STOP] Data Bank export callbacks still exist. Run cleanup_databank_export_callbacks.py first.", flush=True)
        for line_no, text in callback_defs[:20]:
            print(f"  line {line_no}: {text}", flush=True)
        return 1

    ref_indexes = cleanup._target_reference_lines(lines)
    if not ref_indexes:
        print("[SPINA] No leftover Data Bank export callback references found. Nothing to inspect.", flush=True)
        return 0

    print(f"[SPINA] Remaining target-name references found: {len(ref_indexes)}", flush=True)
    candidate_ranges: list[tuple[int, int]] = []
    unresolved: list[int] = []
    for idx in ref_indexes:
        candidate = cleanup._candidate_range_for_reference(lines, idx)
        if candidate is None:
            unresolved.append(idx)
        else:
            candidate_ranges.append(candidate)

    candidate_ranges = cleanup._merge_ranges(candidate_ranges)
    if unresolved:
        print("[SPINA][STOP] Some references are not inside recognized generated ranges:", flush=True)
        for idx in unresolved[:20]:
            print(f"  line {idx + 1}: {lines[idx].rstrip()}", flush=True)
        return 1

    protected_terms = tuple(cleanup.PROTECTED_TERMS)
    for start, end in candidate_ranges:
        text = "".join(lines[start:end])
        protected = cleanup._protected_hits(text)
        print(f"[SPINA] Candidate range: lines {start + 1}-{end} ({end - start} lines)", flush=True)
        print(f"  generated_block: {cleanup._looks_like_generated_databank_cleanup_block(text)}", flush=True)
        print(f"  generated_code_marker: {cleanup._has_expected_generated_code(text)}", flush=True)
        print(f"  protected_terms: {', '.join(protected) if protected else 'none'}", flush=True)

        if not protected:
            continue

        print("[SPINA] Protected-term line context:", flush=True)
        hit_lines = [i for i in range(start, end) if _matching_terms(lines[i], protected_terms)]
        shown = 0
        for hit in hit_lines[:30]:
            terms = ", ".join(_matching_terms(lines[hit], protected_terms))
            context_start = max(start, hit - CONTEXT_RADIUS)
            context_end = min(end, hit + CONTEXT_RADIUS + 1)
            print(f"  --- hit line {hit + 1} | terms: {terms} ---", flush=True)
            for line_index in range(context_start, context_end):
                marker = ">" if line_index == hit else " "
                print(f"  {marker} {line_index + 1}: {lines[line_index].rstrip()}", flush=True)
            shown += 1
        if len(hit_lines) > shown:
            print(f"  ... {len(hit_lines) - shown} more protected-term hit lines not shown", flush=True)

    print("[SPINA] Inspection only. No files were changed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
