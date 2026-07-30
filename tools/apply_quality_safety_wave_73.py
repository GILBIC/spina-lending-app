#!/usr/bin/env python3
"""Port the four focused PR #3 safety fixes onto current modularized main."""
from __future__ import annotations

import argparse
import ast
import hashlib
import re
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
LONG_TASK_PATH = ROOT / "spina_app" / "long_task_presentation.py"
WAVE42_TEST_PATH = ROOT / "tools" / "test_long_task_presentation_wave_42.py"
LEGACY_PATH = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
BIND_START = "# Bind optimized loaders after the normal app methods are installed."
BIND_END = "# --- END: LARGE DATA PERFORMANCE PATCH (clients + databank) ---"
WAVE81_INSTALL_MARKER = "# --- BEGIN: Clients feature installer Wave 81 ---"
LEGACY_CLIENT_REFRESH_BIND = '        setattr(App, "refresh_clients", _spina_perf_refresh_clients)\n'


def git_show(ref: str, path: str) -> str:
    return subprocess.check_output(
        ["git", "show", f"{ref}:{path}"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    )


def unique_function(source: str, name: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {name!r}, found {len(matches)}")
    return matches[0]


def node_text(source: str, node: ast.AST) -> str:
    lines = source.splitlines(keepends=True)
    raw = "".join(lines[node.lineno - 1 : node.end_lineno])
    return textwrap.dedent(raw).rstrip() + "\n"


def offsets(source: str, node: ast.AST) -> tuple[int, int]:
    lines = source.splitlines(keepends=True)
    start = sum(len(line) for line in lines[: node.lineno - 1])
    end = sum(len(line) for line in lines[: node.end_lineno])
    return start, end


def transplant_functions(
    current: str,
    fixed: str,
    names: list[str],
    *,
    prefix_by_name: dict[str, str] | None = None,
) -> str:
    replacements = []
    for name in names:
        current_node = unique_function(current, name)
        fixed_node = unique_function(fixed, name)
        start, end = offsets(current, current_node)
        replacement = textwrap.indent(node_text(fixed, fixed_node), " " * current_node.col_offset)
        if prefix_by_name and name in prefix_by_name:
            replacement = prefix_by_name[name] + replacement
        replacements.append((start, end, replacement))
    for start, end, replacement in sorted(replacements, reverse=True):
        current = current[:start] + replacement + current[end:]
    return current


def replace_section(current: str, fixed: str, start_marker: str, end_marker: str) -> str:
    current_start = current.find(start_marker)
    current_end = current.find(end_marker, current_start)
    fixed_start = fixed.find(start_marker)
    fixed_end = fixed.find(end_marker, fixed_start)
    if min(current_start, current_end, fixed_start, fixed_end) < 0:
        raise AssertionError(f"Could not locate section {start_marker!r}")
    fixed_section = fixed[fixed_start:fixed_end]
    return current[:current_start] + fixed_section + current[current_end:]


def patch_app(current: str, fixed: str) -> str:
    prefix = {}
    if "_SPINA_PERF_INDEXES_READY = False" not in current:
        prefix["_spina_perf_ensure_indexes"] = "_SPINA_PERF_INDEXES_READY = False\n\n\n"
    current = transplant_functions(
        current,
        fixed,
        [
            "_set_user_password",
            "_save_users_db",
            "_load_users_db",
            "_spina_perf_ensure_indexes",
        ],
        prefix_by_name=prefix,
    )
    current = replace_section(current, fixed, BIND_START, BIND_END)

    # The reviewed legacy source predates the complete Clients feature boundary and
    # therefore binds the optimized Clients refresh directly. Once Wave 81 owns the
    # final App bindings, retaining that line restores redundant runtime ownership.
    if WAVE81_INSTALL_MARKER in current:
        count = current.count(LEGACY_CLIENT_REFRESH_BIND)
        if count != 1:
            raise AssertionError(
                f"Expected one legacy Clients refresh binding under Wave 81, found {count}"
            )
        current = current.replace(LEGACY_CLIENT_REFRESH_BIND, "", 1)

    return current


def patch_long_task(current: str, fixed_app: str) -> str:
    current_node = unique_function(current, "_call_work_fn")
    fixed_node = unique_function(fixed_app, "_call_work_fn")
    start, end = offsets(current, current_node)
    replacement = textwrap.indent(node_text(fixed_app, fixed_node), " " * current_node.col_offset)
    return current[:start] + replacement + current[end:]


def replace_constant(source: str, name: str, value: str) -> str:
    pattern = rf"^{re.escape(name)}\s*=.*$"
    updated, count = re.subn(pattern, f"{name} = {value}", source, count=1, flags=re.MULTILINE)
    if count != 1:
        raise AssertionError(f"Could not update {name}")
    return updated


def refresh_wave42_metadata(module_source: str, test_source: str) -> tuple[str, str, int, str]:
    node = unique_function(module_source, "_run_long_task")
    source = node_text(module_source, node)
    line_count = node.end_lineno - node.lineno + 1
    digest = hashlib.sha256((textwrap.dedent(source).strip() + "\n").encode("utf-8")).hexdigest()

    module_source = replace_constant(module_source, "LONG_TASK_SOURCE_LINES", str(line_count))
    module_source = replace_constant(module_source, "LONG_TASK_SOURCE_SHA256", repr(digest))
    test_source = replace_constant(test_source, "EXPECTED_LINES", str(line_count))
    test_source = replace_constant(test_source, "EXPECTED_SHA256", repr(digest))
    return module_source, test_source, line_count, digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixed-ref", default="origin/review/bugs-efficiency")
    args = parser.parse_args()

    fixed_app = git_show(args.fixed_ref, LEGACY_PATH)
    app_before = APP_PATH.read_text(encoding="utf-8")
    long_before = LONG_TASK_PATH.read_text(encoding="utf-8")
    wave42_before = WAVE42_TEST_PATH.read_text(encoding="utf-8")

    app_after = patch_app(app_before, fixed_app)
    long_after = patch_long_task(long_before, fixed_app)
    long_after, wave42_after, line_count, digest = refresh_wave42_metadata(
        long_after, wave42_before
    )

    if app_after != app_before:
        APP_PATH.write_text(app_after, encoding="utf-8", newline="\n")
    if long_after != long_before:
        LONG_TASK_PATH.write_text(long_after, encoding="utf-8", newline="\n")
    if wave42_after != wave42_before:
        WAVE42_TEST_PATH.write_text(wave42_after, encoding="utf-8", newline="\n")

    print(
        "Wave 73 port complete:",
        f"app_changed={app_after != app_before}",
        f"long_task_changed={long_after != long_before}",
        f"wave42_test_changed={wave42_after != wave42_before}",
        f"long_task_lines={line_count}",
        f"long_task_sha256={digest}",
    )


if __name__ == "__main__":
    main()
