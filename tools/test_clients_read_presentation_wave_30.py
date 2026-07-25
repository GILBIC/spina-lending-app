"""Focused regression checks for Clients read/presentation Wave 30."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
CLIENTS_MODULE = ROOT / "spina_app" / "tabs" / "clients.py"
CILOG_MODULE = ROOT / "spina_app" / "tabs" / "client_info_logs.py"

EXPECTED = {
    "_app__selected_client_name_and_lt": ("14d5dc75d3e4c627c641432ca154c728947f897b689c2e3e5a018b42324db518", 23, CLIENTS_MODULE),
    "_app_install_clients_picture_ui": ("9d2db6c2bdbe687f61d8de7eb782eb88790576b9a41b88d09a34fd195fdabba2", 56, CLIENTS_MODULE),
    "_db_get_client_picture": ("211de0c11f8a4e76ddbabcf0e2ede10b7a81ed9372ea1ed637b2f46b127c9953", 10, CLIENTS_MODULE),
    "_spina__client_due_meta": ("99bbf9fc1d2c0a73e46d410ebae7ddc35da145c2600e28c1d52bef5e9013b829", 13, CLIENTS_MODULE),
    "_spina_perf_clients_rows": ("bde1995e41f83ebb4ff0fc5f98bf35ac850b2884efd0acc08962fe7257e688df", 168, CLIENTS_MODULE),
    "_spina_perf_refresh_clients": ("30b375e6e8e6ff9a2ff71346a171eef2a0c08b9e1710aa4a534996ec4ee8bafc", 90, CLIENTS_MODULE),
    "_spina_route_notice_for_client": ("a5112382b81d0b52df469a360bc02990c5cc73324980d8d0c470d32617857711", 45, CLIENTS_MODULE),
    "_spina_build_client_info_logs_tab": ("b93b9cf58f9dbbb555452172ca47cd8d168eb20702ddb36b8dc32e05371bbfae", 132, CILOG_MODULE),
    "_spina_refresh_client_info_logs": ("f16f5d152741c0abb153066419df394c85a194c187846a1ce34fad1a0a65f227", 11, CILOG_MODULE),
    "_spina_render_client_info_logs": ("0d1b40e55803e0f419d77f1c50d6bae8689e16d29a8e036df84cfebb55d85143", 53, CILOG_MODULE),
}
PRESERVED_DESKTOP = {
    "_app_set_selected_client_picture": "783e63fa67dafc59094539718490bba29a53d02132585c4e57c52d5656ae5ad1",
    "_app_clear_selected_client_picture": "af86d02899668feb6ca415ea19daf31d4ff1f3a88fae88cf167957bdf05c35c3",
}
BASE_DUE_HASH = "2013d3bd52b2d92d09052b3ed6385a4418d093ae2b7cc4b464da16b60a7e5f3f"


def top_level_functions(path: Path) -> dict[str, list[tuple[ast.AST, str]]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(path))
    result: dict[str, list[tuple[ast.AST, str]]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            source = "\n".join(lines[node.lineno - 1 : node.end_lineno])
            result.setdefault(node.name, []).append((node, source))
    return result


def source_hash(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def import_lines(tree: ast.Module) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module not in {"spina_app.tabs.clients", "spina_app.tabs.client_info_logs"}:
            continue
        for alias in node.names:
            result.setdefault(alias.asname or alias.name, []).append(node.lineno)
    return result


def runtime_reference_lines(tree: ast.Module) -> dict[str, list[int]]:
    target_set = set(EXPECTED)
    result = {name: [] for name in target_set}
    ignored = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)
    for statement in tree.body:
        if isinstance(statement, ignored):
            continue
        names = {
            item.id
            for item in ast.walk(statement)
            if isinstance(item, ast.Name) and item.id in target_set
        }
        for name in names:
            result[name].append(statement.lineno)
    return result


def assert_exact_extraction() -> None:
    desktop = top_level_functions(SOURCE)
    clients = top_level_functions(CLIENTS_MODULE)
    cilog = top_level_functions(CILOG_MODULE)

    total = 0
    for name, (expected_hash, expected_lines, destination) in EXPECTED.items():
        records = clients if destination == CLIENTS_MODULE else cilog
        matches = records.get(name, [])
        assert len(matches) == 1, f"Expected one {name} in {destination}, found {len(matches)}"
        node, source = matches[0]
        assert source_hash(source) == expected_hash, (name, source_hash(source), expected_hash)
        line_count = (node.end_lineno or node.lineno) - node.lineno + 1
        assert line_count == expected_lines, (name, line_count, expected_lines)
        total += line_count

        if name == "_spina__client_due_meta":
            remaining = desktop.get(name, [])
            assert len(remaining) == 1, "The original base due helper must remain in the desktop file"
            assert source_hash(remaining[0][1]) == BASE_DUE_HASH
        else:
            assert not desktop.get(name), f"Desktop still defines extracted helper {name}"

    assert total == 601, total

    for name, expected_hash in PRESERVED_DESKTOP.items():
        matches = desktop.get(name, [])
        assert len(matches) == 1, f"Preserved write handler missing: {name}"
        assert source_hash(matches[0][1]) == expected_hash, name
        assert not clients.get(name), f"Write handler moved into Clients module: {name}"


def assert_runtime_wiring_order() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(SOURCE))
    imports = import_lines(tree)
    references = runtime_reference_lines(tree)

    for name, lines in references.items():
        if not lines or name == "_spina__client_due_meta":
            continue
        assert imports.get(name), f"Missing Wave 30 import for runtime helper {name}"
        assert min(imports[name]) < min(lines), (name, imports[name], lines)

    base_capture = []
    for statement in tree.body:
        for node in ast.walk(statement):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == "_spina__client_due_meta_base" for target in targets):
                base_capture.append(statement.lineno)
    assert base_capture, "Flexible-due base capture is missing"
    due_import = imports.get("_spina__client_due_meta", [])
    assert due_import and max(base_capture) < min(due_import), (base_capture, due_import)

    source = text
    assert "setattr(App, \"refresh_clients\", _spina_perf_refresh_clients)" in source
    assert "setattr(App, 'render_client_info_logs', _spina_render_client_info_logs)" in source
    assert "setattr(App, '_build_client_info_logs_tab', _spina_build_client_info_logs_tab)" in source
    assert "setattr(LoanDB, 'get_client_picture', _db_get_client_picture)" in source


def assert_focused_behavior() -> None:
    from spina_app.tabs import clients

    deps = {name: (lambda *args, **kwargs: None) for name in clients._REQUIRED_DEPENDENCIES}
    deps.update(
        {
            "_app__norm_lt_value": lambda _self, value: str(value or "Regular").title(),
            "_spina__ensure_client_picture_column": lambda _self: None,
            "_spina__parse_flexible_due_rule": lambda _info, target=None: ("Flexible", True),
            "_spina__client_due_meta_base": lambda _info, as_of=None: ("Daily", False),
            "_spina_route_notice_norm_lt": lambda value: str(value or "Regular").title(),
            "_spina_route_notice_norm_name": lambda value: str(value or "").strip().lower(),
            "_spina_route_notice_key": lambda client, lt, uid="": f"{uid or str(client).strip().lower()}|{lt}",
            "_spina_route_notice_load": lambda: {
                "2026-07-25": {
                    "CID-1|Regular": {
                        "client_uid": "CID-1",
                        "client": "Alice",
                        "loan_type": "Regular",
                        "notice": "Bring ID",
                    }
                }
            },
        }
    )
    missing = clients.configure_clients_dependencies(deps)
    assert not missing, missing

    class FakeTree:
        def selection(self):
            return ("row-1",)

        def item(self, _iid, field):
            if field == "values":
                return ("Alice", "Area 1")
            if field == "tags":
                return ("lt:7x7",)
            return ()

    app = SimpleNamespace(clients_tree=FakeTree(), _mode_filter=lambda: "Regular")
    assert clients._app__selected_client_name_and_lt(app) == ("Alice", "7X7")

    db = SimpleNamespace(
        get_client_info=lambda *args, **kwargs: {"client_picture": " pictures/alice.jpg "},
        get_client_uid=lambda *args, **kwargs: "CID-1",
    )
    assert clients._db_get_client_picture(db, "Alice") == "pictures/alice.jpg"
    assert clients._spina__client_due_meta({}, as_of="2026-07-25") == ("Flexible", True)
    assert clients._spina_route_notice_for_client(db, "Alice", "Regular", "2026-07-25") == "Bring ID"

    deps["_spina__parse_flexible_due_rule"] = lambda _info, target=None: None
    clients.configure_clients_dependencies(deps)
    assert clients._spina__client_due_meta({}, as_of="2026-07-25") == ("Daily", False)


def main() -> None:
    assert_exact_extraction()
    assert_runtime_wiring_order()
    assert_focused_behavior()
    print("Clients read/presentation Wave 30 regression passed: 10 helpers, 601 lines")


if __name__ == "__main__":
    main()
