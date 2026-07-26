from __future__ import annotations

import ast
import hashlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "account_permission_presentation.py"
TEST = ROOT / "tools" / "test_account_permission_presentation_wave_47.py"

TARGET = "_spina_v32_account_permission_text"
EXPECTED_LINES = 11
EXPECTED_SIGNATURE = "role"
EXPECTED_HASH = "d5505320cff939e064d9e85d4e8fc26ec4abe7d5b4f08852cf31d0b703abc6e4"
EXPECTED_CALLS = {"str", "strip"}

CALLER_HASHES = {
    "_spina_v32_account_choices": "25bbe162bb3b2d771ee913f73b9c3c2e98b73375b5737ed01bb7c5ac8334f280",
    "_spina_v32_selected_label_for_user": "8b775aa3feb95037083709047367c8fe06c485a1521906aada4fee97d0b8564c",
    "_spina_v32_account_display_name": "91d6223b1850845e6c28b1e6aae340136cb6128c93b963690ab7c69d01d18135",
    "_spina_v32_login_button": "5026d5e31401e7dc276a79f2625d117d23133e5e0da643a459e609fd99ff1d59",
}


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def normalized_hash(source: str) -> str:
    normalized = "\n".join(line.rstrip() for line in source.strip().splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def function_nodes(tree: ast.AST, name: str) -> list[ast.FunctionDef]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]


def source_segment(text: str, node: ast.AST) -> str:
    source = ast.get_source_segment(text, node)
    assert source is not None
    return source


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    matches = function_nodes(tree, TARGET)
    assert len(matches) == 1, (TARGET, len(matches))
    node = matches[0]
    source = source_segment(text, node)

    assert node.end_lineno is not None
    assert node.end_lineno - node.lineno + 1 == EXPECTED_LINES
    assert ast.unparse(node.args) == EXPECTED_SIGNATURE
    assert normalized_hash(source) == EXPECTED_HASH

    calls = {
        dotted(call.func).split(".")[-1]
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and dotted(call.func)
    }
    assert calls == EXPECTED_CALLS, calls

    lowered = source.lower()
    for forbidden in (
        "password",
        "verify_login",
        "force_change_password",
        "psycopg",
        "sqlite3",
        ".execute(",
        ".commit(",
        "payment",
        "balance",
        "principal",
        "interest",
        "renew",
        "advance",
        "7x7",
    ):
        assert forbidden not in lowered, forbidden

    for name, expected_hash in CALLER_HASHES.items():
        caller_matches = function_nodes(tree, name)
        assert len(caller_matches) == 1, (name, len(caller_matches))
        assert normalized_hash(source_segment(text, caller_matches[0])) == expected_hash, name

    assert not MODULE.exists(), MODULE
    assert not TEST.exists(), TEST

    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    replacement = [
        "from spina_app.account_permission_presentation import (",
        "    _spina_v32_account_permission_text as _wave47_spina_v32_account_permission_text,",
        ")",
        "_spina_v32_account_permission_text = _wave47_spina_v32_account_permission_text",
    ]
    lines[node.lineno - 1 : node.end_lineno] = replacement
    updated = newline.join(lines) + (newline if text.endswith(("\n", "\r\n")) else "")
    updated_tree = ast.parse(updated)
    assert not function_nodes(updated_tree, TARGET)

    import_nodes = [
        part
        for part in ast.walk(updated_tree)
        if isinstance(part, ast.ImportFrom)
        and part.module == "spina_app.account_permission_presentation"
    ]
    assert len(import_nodes) == 1
    imported = import_nodes[0].names
    assert len(imported) == 1
    assert imported[0].name == TARGET
    assert imported[0].asname == "_wave47_spina_v32_account_permission_text"

    assignments = [
        part
        for part in ast.walk(updated_tree)
        if isinstance(part, ast.Assign)
        and len(part.targets) == 1
        and isinstance(part.targets[0], ast.Name)
        and part.targets[0].id == TARGET
    ]
    assert len(assignments) == 1
    assert isinstance(assignments[0].value, ast.Name)
    assert assignments[0].value.id == "_wave47_spina_v32_account_permission_text"

    module_source = textwrap.dedent(
        f'''\
        """Account permission summary presentation extracted in Wave 47."""
        from __future__ import annotations

        ACCOUNT_PERMISSION_TARGET = {TARGET!r}
        ACCOUNT_PERMISSION_SOURCE_LINES = {EXPECTED_LINES}
        ACCOUNT_PERMISSION_SOURCE_SHA256 = {EXPECTED_HASH!r}
        ACCOUNT_PERMISSION_SIGNATURE = {EXPECTED_SIGNATURE!r}


        {source}
        '''
    )
    ast.parse(module_source)

    test_source = textwrap.dedent(
        f'''\
        from __future__ import annotations

        import ast
        import hashlib
        from pathlib import Path

        from spina_app.account_permission_presentation import (
            ACCOUNT_PERMISSION_SIGNATURE,
            ACCOUNT_PERMISSION_SOURCE_LINES,
            ACCOUNT_PERMISSION_SOURCE_SHA256,
            ACCOUNT_PERMISSION_TARGET,
            _spina_v32_account_permission_text,
        )

        ROOT = Path(__file__).resolve().parents[1]
        DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
        MODULE = ROOT / "spina_app" / "account_permission_presentation.py"
        CALLER_HASHES = {CALLER_HASHES!r}


        def normalized_hash(source: str) -> str:
            normalized = "\\n".join(line.rstrip() for line in source.strip().splitlines())
            return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


        def function_nodes(tree: ast.AST, name: str):
            return [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == name
            ]


        def main() -> None:
            assert ACCOUNT_PERMISSION_TARGET == {TARGET!r}
            assert ACCOUNT_PERMISSION_SOURCE_LINES == {EXPECTED_LINES}
            assert ACCOUNT_PERMISSION_SOURCE_SHA256 == {EXPECTED_HASH!r}
            assert ACCOUNT_PERMISSION_SIGNATURE == {EXPECTED_SIGNATURE!r}

            module_text = MODULE.read_text(encoding="utf-8")
            module_tree = ast.parse(module_text)
            module_matches = function_nodes(module_tree, ACCOUNT_PERMISSION_TARGET)
            assert len(module_matches) == 1
            module_node = module_matches[0]
            module_source = ast.get_source_segment(module_text, module_node)
            assert module_source is not None
            assert module_node.end_lineno - module_node.lineno + 1 == ACCOUNT_PERMISSION_SOURCE_LINES
            assert ast.unparse(module_node.args) == ACCOUNT_PERMISSION_SIGNATURE
            assert normalized_hash(module_source) == ACCOUNT_PERMISSION_SOURCE_SHA256

            desktop_text = DESKTOP.read_text(encoding="utf-8")
            desktop_tree = ast.parse(desktop_text)
            assert not function_nodes(desktop_tree, ACCOUNT_PERMISSION_TARGET)

            imports = [
                node
                for node in ast.walk(desktop_tree)
                if isinstance(node, ast.ImportFrom)
                and node.module == "spina_app.account_permission_presentation"
            ]
            assert len(imports) == 1
            aliases = imports[0].names
            assert len(aliases) == 1
            assert aliases[0].name == ACCOUNT_PERMISSION_TARGET
            assert aliases[0].asname == "_wave47_spina_v32_account_permission_text"

            assignments = [
                node
                for node in ast.walk(desktop_tree)
                if isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == ACCOUNT_PERMISSION_TARGET
            ]
            assert len(assignments) == 1
            assert isinstance(assignments[0].value, ast.Name)
            assert assignments[0].value.id == "_wave47_spina_v32_account_permission_text"

            for name, expected_hash in CALLER_HASHES.items():
                matches = function_nodes(desktop_tree, name)
                assert len(matches) == 1, (name, len(matches))
                source = ast.get_source_segment(desktop_text, matches[0])
                assert source is not None
                assert normalized_hash(source) == expected_hash, name

            expected = {{
                "Admin": "Full app access",
                "Encoder": "Encoding, reports, and route access",
                "Viewer": "Reports access",
                "System": "Audit, controls, and system tools",
                "Manager": "Custom account access",
                "admin": "Custom account access",
                "": "Custom account access",
                None: "Custom account access",
            }}
            for role, summary in expected.items():
                assert _spina_v32_account_permission_text(role) == summary, (role, summary)

            print("Wave 47 account permission presentation regression passed.")


        if __name__ == "__main__":
            main()
        '''
    )
    ast.parse(test_source)

    DESKTOP.write_text(updated, encoding="utf-8", newline="")
    MODULE.write_text(module_source, encoding="utf-8")
    TEST.write_text(test_source, encoding="utf-8")
    print("Prepared guarded Wave 47 account permission extraction.")


if __name__ == "__main__":
    main()
