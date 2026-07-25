"""Guarded high-volume extraction for Clients read/presentation Wave 30."""

from __future__ import annotations

import ast
import hashlib
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
CLIENTS_MODULE = ROOT / "spina_app" / "tabs" / "clients.py"
CILOG_MODULE = ROOT / "spina_app" / "tabs" / "client_info_logs.py"
TEST = ROOT / "tools" / "test_clients_read_presentation_wave_30.py"

EXPECTED_BLOBS = {
    SOURCE: "8073e98ae05c89a0687dc84877024d8f81584dca",
    CLIENTS_MODULE: "8e1652e0d491a261655360e2e9b6dc0fd3a053a2",
    CILOG_MODULE: "5c02e9dac5633683a6d5926850cc49b16dbef8aa",
    TEST: "2f549071ab6f45c6d27e675a57236f54e94ee945",
}

CLIENTS_PICTURE = (
    "_db_get_client_picture",
    "_app__selected_client_name_and_lt",
    "_app_install_clients_picture_ui",
)
CLIENTS_PERF = (
    "_spina_perf_clients_rows",
    "_spina_perf_refresh_clients",
)
CLIENTS_DUE = ("_spina__client_due_meta",)
CLIENTS_ROUTE = ("_spina_route_notice_for_client",)
CILOG = (
    "_spina_build_client_info_logs_tab",
    "_spina_render_client_info_logs",
    "_spina_refresh_client_info_logs",
)
TARGETS = CLIENTS_PICTURE + CLIENTS_PERF + CLIENTS_DUE + CLIENTS_ROUTE + CILOG

EXPECTED_HASHES = {
    "_app__selected_client_name_and_lt": "14d5dc75d3e4c627c641432ca154c728947f897b689c2e3e5a018b42324db518",
    "_app_install_clients_picture_ui": "9d2db6c2bdbe687f61d8de7eb782eb88790576b9a41b88d09a34fd195fdabba2",
    "_db_get_client_picture": "211de0c11f8a4e76ddbabcf0e2ede10b7a81ed9372ea1ed637b2f46b127c9953",
    "_spina__client_due_meta": "99bbf9fc1d2c0a73e46d410ebae7ddc35da145c2600e28c1d52bef5e9013b829",
    "_spina_build_client_info_logs_tab": "b93b9cf58f9dbbb555452172ca47cd8d168eb20702ddb36b8dc32e05371bbfae",
    "_spina_perf_clients_rows": "bde1995e41f83ebb4ff0fc5f98bf35ac850b2884efd0acc08962fe7257e688df",
    "_spina_perf_refresh_clients": "30b375e6e8e6ff9a2ff71346a171eef2a0c08b9e1710aa4a534996ec4ee8bafc",
    "_spina_refresh_client_info_logs": "f16f5d152741c0abb153066419df394c85a194c187846a1ce34fad1a0a65f227",
    "_spina_render_client_info_logs": "0d1b40e55803e0f419d77f1c50d6bae8689e16d29a8e036df84cfebb55d85143",
    "_spina_route_notice_for_client": "a5112382b81d0b52df469a360bc02990c5cc73324980d8d0c470d32617857711",
}
EXPECTED_LINES = {
    "_app__selected_client_name_and_lt": 23,
    "_app_install_clients_picture_ui": 56,
    "_db_get_client_picture": 10,
    "_spina__client_due_meta": 13,
    "_spina_build_client_info_logs_tab": 132,
    "_spina_perf_clients_rows": 168,
    "_spina_perf_refresh_clients": 90,
    "_spina_refresh_client_info_logs": 11,
    "_spina_render_client_info_logs": 53,
    "_spina_route_notice_for_client": 45,
}
PRESERVED_HASHES = {
    "_app_set_selected_client_picture": "783e63fa67dafc59094539718490bba29a53d02132585c4e57c52d5656ae5ad1",
    "_app_clear_selected_client_picture": "af86d02899668feb6ca415ea19daf31d4ff1f3a88fae88cf167957bdf05c35c3",
}
BASE_DUE_HASH = "2013d3bd52b2d92d09052b3ed6385a4418d093ae2b7cc4b464da16b60a7e5f3f"

CLIENT_DEPENDENCIES = (
    "_spina_v23_clients_colors",
    "_app__norm_lt_value",
    "_spina_v23_client_loan_summary",
    "_log_exc",
    "_spina__ensure_client_picture_column",
    "_spina_perf_dict_rows",
    "_spina_perf_ensure_indexes",
    "_spina_perf_norm_lt",
    "_app_refresh_clients",
    "_log_suppressed_once",
    "_spina__fmt_client_money",
    "_spina__parse_flexible_due_rule",
    "_spina__client_due_meta_base",
    "_spina_route_notice_key",
    "_spina_route_notice_load",
    "_spina_route_notice_norm_lt",
    "_spina_route_notice_norm_name",
)


def git_blob(path: Path) -> str:
    return subprocess.check_output(
        ["git", "hash-object", str(path)], cwd=ROOT, text=True
    ).strip()


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def segment(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def top_level_records(text: str) -> tuple[ast.Module, dict[str, list[tuple[ast.AST, str]]]]:
    lines = text.splitlines()
    tree = ast.parse(text)
    result: dict[str, list[tuple[ast.AST, str]]] = defaultdict(list)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result[node.name].append((node, segment(lines, node)))
    return tree, result


def replacement_lines(value: str) -> list[str]:
    if value and not value.endswith("\n"):
        value += "\n"
    return value.splitlines(keepends=True)


def apply_edits(text: str, edits: list[tuple[int, int, str]]) -> str:
    lines = text.splitlines(keepends=True)
    for start, end, value in sorted(edits, key=lambda item: item[0], reverse=True):
        lines[start:end] = replacement_lines(value)
    return "".join(lines)


def render_dependencies(names: tuple[str, ...]) -> str:
    body = "\n".join(f'    "{name}",' for name in names)
    return f"_REQUIRED_DEPENDENCIES = (\n{body}\n)"


def update_clients_dependencies(text: str) -> str:
    tree = ast.parse(text)
    target = None
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(item, ast.Name) and item.id == "_REQUIRED_DEPENDENCIES" for item in node.targets):
            target = node
            break
    assert target is not None, "Clients dependency tuple is missing"
    current = []
    if isinstance(target.value, (ast.Tuple, ast.List)):
        for item in target.value.elts:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                current.append(item.value)
    assert tuple(current) == CLIENT_DEPENDENCIES[:4], current
    return apply_edits(
        text,
        [(target.lineno - 1, target.end_lineno, render_dependencies(CLIENT_DEPENDENCIES))],
    )


def append_exact_functions(module_text: str, sources: list[str]) -> str:
    tree, records = top_level_records(module_text)
    del tree
    for source in sources:
        name = ast.parse(source).body[0].name
        assert name not in records, f"Destination already defines {name}"
    return module_text.rstrip() + "\n\n\n" + "\n\n".join(sources) + "\n"


def picture_import_block() -> str:
    return '''# Wave 30: read-only Clients picture and selection helpers.
from spina_app.tabs.clients import (
    configure_clients_dependencies as _configure_clients_wave30_dependencies,
    _db_get_client_picture,
    _app__selected_client_name_and_lt,
    _app_install_clients_picture_ui,
)
_configure_clients_wave30_dependencies(globals())
'''


def perf_import_block() -> str:
    return '''# Wave 30: bulk Clients read and refresh presentation helpers.
from spina_app.tabs.clients import (
    _spina_perf_clients_rows,
    _spina_perf_refresh_clients,
)
_configure_clients_wave30_dependencies(globals())
'''


def cilog_import_block() -> str:
    return '''# Wave 30: legacy Client Info Logs presentation wrappers.
from spina_app.tabs.client_info_logs import (
    configure_client_info_logs_dependencies as _configure_cilog_wave30_dependencies,
    _spina_build_client_info_logs_tab,
    _spina_render_client_info_logs,
    _spina_refresh_client_info_logs,
)
_configure_cilog_wave30_dependencies(globals())
'''


def due_import_block() -> str:
    return '''# Wave 30: flexible due display wrapper imported only after base capture.
from spina_app.tabs.clients import _spina__client_due_meta
_configure_clients_wave30_dependencies(globals())
'''


def route_import_block() -> str:
    return '''# Wave 30: read-only Collector Route notice lookup for Clients.
from spina_app.tabs.clients import _spina_route_notice_for_client
_configure_clients_wave30_dependencies(globals())
'''


def verify_module_hashes(path: Path, expected_names: tuple[str, ...]) -> None:
    _tree, records = top_level_records(path.read_text(encoding="utf-8"))
    for name in expected_names:
        matches = records.get(name, [])
        assert len(matches) == 1, (path, name, len(matches))
        node, source = matches[0]
        assert sha256(source) == EXPECTED_HASHES[name], name
        lines = (node.end_lineno or node.lineno) - node.lineno + 1
        assert lines == EXPECTED_LINES[name], (name, lines)


def main() -> None:
    for path, expected in EXPECTED_BLOBS.items():
        actual = git_blob(path)
        assert actual == expected, (str(path), actual, expected)

    source_text = SOURCE.read_text(encoding="utf-8")
    source_tree, records = top_level_records(source_text)
    del source_tree

    chosen: dict[str, tuple[ast.AST, str]] = {}
    for name in TARGETS:
        matches = records.get(name, [])
        if name == "_spina__client_due_meta":
            assert len(matches) == 2, len(matches)
            assert sha256(matches[0][1]) == BASE_DUE_HASH
            chosen[name] = matches[-1]
        else:
            assert len(matches) == 1, (name, len(matches))
            chosen[name] = matches[0]
        assert sha256(chosen[name][1]) == EXPECTED_HASHES[name], name

    for name, expected_hash in PRESERVED_HASHES.items():
        matches = records.get(name, [])
        assert len(matches) == 1 and sha256(matches[0][1]) == expected_hash, name

    protected_before: dict[tuple[str, int], str] = {}
    for name, matches in records.items():
        for index, (_node, source) in enumerate(matches, start=1):
            remove = name in chosen and chosen[name][1] == source
            if not remove:
                protected_before[(name, index)] = sha256(source)

    client_sources = [chosen[name][1] for name in CLIENTS_PICTURE + CLIENTS_PERF + CLIENTS_DUE + CLIENTS_ROUTE]
    cilog_sources = [chosen[name][1] for name in CILOG]

    clients_text = update_clients_dependencies(CLIENTS_MODULE.read_text(encoding="utf-8"))
    clients_text = append_exact_functions(clients_text, client_sources)
    cilog_text = append_exact_functions(CILOG_MODULE.read_text(encoding="utf-8"), cilog_sources)

    replacements = {
        "_db_get_client_picture": picture_import_block(),
        "_app__selected_client_name_and_lt": "",
        "_app_install_clients_picture_ui": "",
        "_spina_perf_clients_rows": perf_import_block(),
        "_spina_perf_refresh_clients": "",
        "_spina_build_client_info_logs_tab": cilog_import_block(),
        "_spina_render_client_info_logs": "",
        "_spina_refresh_client_info_logs": "",
        "_spina__client_due_meta": due_import_block(),
        "_spina_route_notice_for_client": route_import_block(),
    }
    edits = []
    for name, (node, _source) in chosen.items():
        edits.append((node.lineno - 1, node.end_lineno, replacements[name]))
    new_source = apply_edits(source_text, edits)
    ast.parse(new_source, filename=str(SOURCE))
    ast.parse(clients_text, filename=str(CLIENTS_MODULE))
    ast.parse(cilog_text, filename=str(CILOG_MODULE))

    _new_tree, new_records = top_level_records(new_source)
    protected_after = {
        (name, index): sha256(source)
        for name, matches in new_records.items()
        for index, (_node, source) in enumerate(matches, start=1)
    }
    for key, expected_hash in protected_before.items():
        assert protected_after.get(key) == expected_hash, (key, protected_after.get(key), expected_hash)

    for name in TARGETS:
        if name == "_spina__client_due_meta":
            assert len(new_records.get(name, [])) == 1
            assert sha256(new_records[name][0][1]) == BASE_DUE_HASH
        else:
            assert not new_records.get(name), name

    SOURCE.write_text(new_source, encoding="utf-8", newline="\n")
    CLIENTS_MODULE.write_text(clients_text, encoding="utf-8", newline="\n")
    CILOG_MODULE.write_text(cilog_text, encoding="utf-8", newline="\n")

    verify_module_hashes(CLIENTS_MODULE, CLIENTS_PICTURE + CLIENTS_PERF + CLIENTS_DUE + CLIENTS_ROUTE)
    verify_module_hashes(CILOG_MODULE, CILOG)

    print("Wave 30 guarded extraction applied: 10 helpers, 601 lines")


if __name__ == "__main__":
    main()
