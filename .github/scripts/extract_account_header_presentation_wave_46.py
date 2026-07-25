from __future__ import annotations

import ast
import hashlib
import re
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "account_header_presentation.py"
REGRESSION = ROOT / "tools" / "test_account_header_presentation_wave_46.py"
SMOKE = ROOT / "tools" / "test_account_header_widget_smoke_wave_46.py"

REFRESH = "_spina_v32_refresh_user_header"
BUILD = "_spina_v32_build_header"
REFRESH_LINES = 14
BUILD_LINES = 12
REFRESH_SHA256 = "01feaa575f128e605ab8bb143c208503cad6868103591d9fe72b108045c88f5a"
BUILD_SHA256 = "ff46e61d0f56a1432ca0d4e4e5257936ff3ba150a84d5b43b254e98424368bac"
PROMPT_ROLE_SHA256 = "c44e89e3f591f6c592363c6e4a21023cf1791958c210354b62219969ca288649"
SWITCH_ACCOUNT_SHA256 = "947c48a723782344e5db1027c4e3dfbe3652bc02a33adcfa5134f45e04bcd337"


def normalized(text: str) -> str:
    return "\n".join(line.rstrip() for line in textwrap.dedent(text).strip().splitlines()) + "\n"


def digest(text: str) -> str:
    return hashlib.sha256(normalized(text).encode("utf-8")).hexdigest()


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def functions(tree: ast.AST, name: str) -> list[ast.FunctionDef]:
    return [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]


def source_for(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def call_inventory(fn: ast.FunctionDef) -> list[str]:
    return sorted({dotted(node.func) for node in ast.walk(fn) if isinstance(node, ast.Call) and dotted(node.func)})


def main() -> None:
    original = DESKTOP.read_text(encoding="utf-8")
    lines = original.splitlines()
    tree = ast.parse(original)

    refresh_defs = functions(tree, REFRESH)
    build_defs = functions(tree, BUILD)
    prompt_defs = functions(tree, "_spina_v32_prompt_user_role")
    switch_defs = functions(tree, "_spina_v32_switch_account")
    assert len(refresh_defs) == 1, len(refresh_defs)
    assert len(build_defs) == 1, len(build_defs)
    assert len(prompt_defs) == 1, len(prompt_defs)
    assert len(switch_defs) == 1, len(switch_defs)

    refresh_node = refresh_defs[0]
    build_node = build_defs[0]
    refresh_source = textwrap.dedent(source_for(lines, refresh_node))
    build_source = textwrap.dedent(source_for(lines, build_node))
    prompt_source = source_for(lines, prompt_defs[0])
    switch_source = source_for(lines, switch_defs[0])

    assert len(refresh_source.splitlines()) == REFRESH_LINES
    assert len(build_source.splitlines()) == BUILD_LINES
    assert digest(refresh_source) == REFRESH_SHA256
    assert digest(build_source) == BUILD_SHA256
    assert digest(prompt_source) == PROMPT_ROLE_SHA256
    assert digest(switch_source) == SWITCH_ACCOUNT_SHA256
    assert call_inventory(refresh_node) == [
        "_log_suppressed_once",
        "_spina_v32_account_display_name",
        "getattr",
        "self._refresh_header_theme",
        "self.user_role_label.config",
    ]
    assert call_inventory(build_node) == [
        "_spina_v32_orig_build_header",
        "getattr",
        "self._refresh_user_header",
        "self.switch_account_btn.configure",
    ]

    import_block = '''from spina_app.account_header_presentation import (
    configure_account_header_dependencies as _wave46_configure_account_header_dependencies,
    _spina_v32_refresh_user_header as _wave46_spina_v32_refresh_user_header,
    _spina_v32_build_header as _wave46_spina_v32_build_header,
)
_wave46_configure_account_header_dependencies(globals())
_spina_v32_refresh_user_header = _wave46_spina_v32_refresh_user_header
_spina_v32_build_header = _wave46_spina_v32_build_header
'''.splitlines()

    remove_ranges = [
        (refresh_node.lineno, refresh_node.end_lineno),
        (build_node.lineno, build_node.end_lineno),
    ]
    rewritten: list[str] = []
    for lineno, line in enumerate(lines, 1):
        if lineno == refresh_node.lineno:
            rewritten.extend(import_block)
        if any(start <= lineno <= end for start, end in remove_ranges):
            continue
        rewritten.append(line)
    DESKTOP.write_text("\n".join(rewritten) + "\n", encoding="utf-8")

    refresh_calls = call_inventory(refresh_node)
    build_calls = call_inventory(build_node)
    module_text = f'''"""Active account header presentation extracted in Wave 46."""
from __future__ import annotations

_ACCOUNT_HEADER_DEPENDENCIES = {{}}
_PROTECTED_GLOBALS = {{
    "__builtins__", "__cached__", "__doc__", "__file__", "__loader__",
    "__name__", "__package__", "__spec__",
    "_ACCOUNT_HEADER_DEPENDENCIES", "_PROTECTED_GLOBALS",
    "configure_account_header_dependencies",
    "ACCOUNT_HEADER_TARGETS", "ACCOUNT_HEADER_SOURCE_LINES",
    "ACCOUNT_HEADER_SOURCE_SHA256", "ACCOUNT_HEADER_SIGNATURES",
    "ACCOUNT_HEADER_NESTED_CALLBACKS", "ACCOUNT_HEADER_CALLS",
}}


def configure_account_header_dependencies(namespace):
    _ACCOUNT_HEADER_DEPENDENCIES.clear()
    _ACCOUNT_HEADER_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value


ACCOUNT_HEADER_TARGETS = [{REFRESH!r}, {BUILD!r}]
ACCOUNT_HEADER_SOURCE_LINES = {{{REFRESH!r}: {REFRESH_LINES}, {BUILD!r}: {BUILD_LINES}}}
ACCOUNT_HEADER_SOURCE_SHA256 = {{{REFRESH!r}: {REFRESH_SHA256!r}, {BUILD!r}: {BUILD_SHA256!r}}}
ACCOUNT_HEADER_SIGNATURES = {{{REFRESH!r}: "self", {BUILD!r}: "self, *args, **kwargs"}}
ACCOUNT_HEADER_NESTED_CALLBACKS = {{{REFRESH!r}: [], {BUILD!r}: []}}
ACCOUNT_HEADER_CALLS = {{{REFRESH!r}: {refresh_calls!r}, {BUILD!r}: {build_calls!r}}}

{normalized(refresh_source)}
{normalized(build_source)}'''
    MODULE.parent.mkdir(parents=True, exist_ok=True)
    MODULE.write_text(module_text, encoding="utf-8")

    regression_text = r'''from __future__ import annotations

import ast
import hashlib
import importlib
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE_PATH = ROOT / "spina_app/account_header_presentation.py"
REFRESH = "_spina_v32_refresh_user_header"
BUILD = "_spina_v32_build_header"
EXPECTED_LINES = {REFRESH: 14, BUILD: 12}
EXPECTED_HASHES = {
    REFRESH: "01feaa575f128e605ab8bb143c208503cad6868103591d9fe72b108045c88f5a",
    BUILD: "ff46e61d0f56a1432ca0d4e4e5257936ff3ba150a84d5b43b254e98424368bac",
}
EXPECTED_SIGNATURES = {REFRESH: "self", BUILD: "self, *args, **kwargs"}
EXPECTED_CALLS = {
    REFRESH: [
        "_log_suppressed_once",
        "_spina_v32_account_display_name",
        "getattr",
        "self._refresh_header_theme",
        "self.user_role_label.config",
    ],
    BUILD: [
        "_spina_v32_orig_build_header",
        "getattr",
        "self._refresh_user_header",
        "self.switch_account_btn.configure",
    ],
}
PROMPT_ROLE_SHA256 = "c44e89e3f591f6c592363c6e4a21023cf1791958c210354b62219969ca288649"
SWITCH_ACCOUNT_SHA256 = "947c48a723782344e5db1027c4e3dfbe3652bc02a33adcfa5134f45e04bcd337"
SQL_WRITE_RE = re.compile(r"\b(?:INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|ALTER\s+TABLE|DROP\s+TABLE|CREATE\s+TABLE)\b", re.I)


def normalized(text: str) -> str:
    return "\n".join(line.rstrip() for line in textwrap.dedent(text).strip().splitlines()) + "\n"


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def signature_text(fn: ast.FunctionDef) -> str:
    parts = []
    positional = list(fn.args.posonlyargs) + list(fn.args.args)
    defaults = [None] * (len(positional) - len(fn.args.defaults)) + list(fn.args.defaults)
    for arg, default in zip(positional, defaults):
        parts.append(arg.arg if default is None else f"{arg.arg}={ast.unparse(default)}")
    if fn.args.vararg:
        parts.append(f"*{fn.args.vararg.arg}")
    elif fn.args.kwonlyargs:
        parts.append("*")
    for arg, default in zip(fn.args.kwonlyargs, fn.args.kw_defaults):
        parts.append(arg.arg if default is None else f"{arg.arg}={ast.unparse(default)}")
    if fn.args.kwarg:
        parts.append(f"**{fn.args.kwarg.arg}")
    return ", ".join(parts)


def source_for(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def function_defs(tree: ast.AST, name: str):
    return [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]


def check_function(fn: ast.FunctionDef, lines: list[str], name: str) -> None:
    source = source_for(lines, fn)
    assert len(textwrap.dedent(source).splitlines()) == EXPECTED_LINES[name]
    assert hashlib.sha256(normalized(source).encode()).hexdigest() == EXPECTED_HASHES[name]
    assert signature_text(fn) == EXPECTED_SIGNATURES[name]
    nested = [
        node.name for node in ast.walk(fn)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node is not fn
    ]
    assert nested == []
    calls = sorted({dotted(node.func) for node in ast.walk(fn) if isinstance(node, ast.Call) and dotted(node.func)})
    assert calls == EXPECTED_CALLS[name]
    for node in ast.walk(fn):
        if isinstance(node, ast.Attribute):
            assert not dotted(node).startswith("self.db")
        if isinstance(node, ast.Name):
            assert node.id not in {"connect_db", "run_write", "open", "Path"}
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert not SQL_WRITE_RE.search(node.value)


def main() -> None:
    module = importlib.import_module("spina_app.account_header_presentation")
    assert module.ACCOUNT_HEADER_TARGETS == [REFRESH, BUILD]
    assert module.ACCOUNT_HEADER_SOURCE_LINES == EXPECTED_LINES
    assert module.ACCOUNT_HEADER_SOURCE_SHA256 == EXPECTED_HASHES
    assert module.ACCOUNT_HEADER_SIGNATURES == EXPECTED_SIGNATURES
    assert module.ACCOUNT_HEADER_NESTED_CALLBACKS == {REFRESH: [], BUILD: []}
    assert module.ACCOUNT_HEADER_CALLS == EXPECTED_CALLS

    module_text = MODULE_PATH.read_text(encoding="utf-8")
    module_lines = module_text.splitlines()
    module_tree = ast.parse(module_text)
    for name in (REFRESH, BUILD):
        defs = function_defs(module_tree, name)
        assert len(defs) == 1, (name, len(defs))
        check_function(defs[0], module_lines, name)

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_lines = desktop_text.splitlines()
    desktop_tree = ast.parse(desktop_text)
    assert not function_defs(desktop_tree, REFRESH)
    assert not function_defs(desktop_tree, BUILD)

    imports = [
        node for node in desktop_tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "spina_app.account_header_presentation"
    ]
    assert len(imports) == 1
    aliases = {(alias.name, alias.asname) for alias in imports[0].names}
    assert ("configure_account_header_dependencies", "_wave46_configure_account_header_dependencies") in aliases
    assert (REFRESH, "_wave46_spina_v32_refresh_user_header") in aliases
    assert (BUILD, "_wave46_spina_v32_build_header") in aliases

    symbol_rebinds = []
    runtime = []
    for node in ast.walk(desktop_tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            lhs = node.targets[0]
            if isinstance(lhs, ast.Name) and lhs.id in {REFRESH, BUILD} and isinstance(node.value, ast.Name):
                symbol_rebinds.append((lhs.id, node.value.id))
            if (
                isinstance(lhs, ast.Attribute)
                and isinstance(lhs.value, ast.Name)
                and lhs.value.id == "App"
                and lhs.attr in {"_refresh_user_header", "_build_header"}
                and isinstance(node.value, ast.Name)
            ):
                runtime.append((node.lineno, lhs.attr, node.value.id))
    assert sorted(symbol_rebinds) == sorted([
        (REFRESH, "_wave46_spina_v32_refresh_user_header"),
        (BUILD, "_wave46_spina_v32_build_header"),
    ])
    runtime.sort()
    assert [row[1:] for row in runtime if row[1] == "_refresh_user_header"][-1] == ("_refresh_user_header", REFRESH)
    assert [row[1:] for row in runtime if row[1] == "_build_header"][-1] == ("_build_header", BUILD)

    prompt_defs = function_defs(desktop_tree, "_spina_v32_prompt_user_role")
    switch_defs = function_defs(desktop_tree, "_spina_v32_switch_account")
    assert len(prompt_defs) == 1
    assert len(switch_defs) == 1
    assert hashlib.sha256(normalized(source_for(desktop_lines, prompt_defs[0])).encode()).hexdigest() == PROMPT_ROLE_SHA256
    assert hashlib.sha256(normalized(source_for(desktop_lines, switch_defs[0])).encode()).hexdigest() == SWITCH_ACCOUNT_SHA256

    print("Wave 46 account header presentation regression passed.")


if __name__ == "__main__":
    main()
'''
    REGRESSION.write_text(regression_text, encoding="utf-8")

    smoke_text = r'''from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spina_app import account_header_presentation as presentation


class Harness:
    pass


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    try:
        harness = Harness()
        harness.user_name = "admin"
        harness.user_role_label = tk.Label(root, text="Old")
        harness.theme_refreshes = 0
        harness._refresh_header_theme = lambda: setattr(
            harness, "theme_refreshes", harness.theme_refreshes + 1
        )

        presentation.configure_account_header_dependencies({
            "_spina_v32_account_display_name": lambda self, username: "Owner Account" if username == "admin" else username,
            "_log_suppressed_once": lambda *args, **kwargs: None,
        })
        presentation._spina_v32_refresh_user_header(harness)
        assert harness.user_role_label.cget("text") == "Account: Owner Account"
        assert harness.theme_refreshes == 1

        harness.header_refreshes = 0
        harness._refresh_user_header = lambda: setattr(
            harness, "header_refreshes", harness.header_refreshes + 1
        )

        def original_build_header(self, *args, **kwargs):
            self.switch_account_btn = tk.Button(root, text="Switch Account")
            return {"args": args, "kwargs": kwargs}

        presentation.configure_account_header_dependencies({
            "_spina_v32_orig_build_header": original_build_header,
            "_spina_v32_account_display_name": lambda self, username: username,
            "_log_suppressed_once": lambda *args, **kwargs: None,
        })
        result = presentation._spina_v32_build_header(harness, "sample", mode="test")
        assert result == {"args": ("sample",), "kwargs": {"mode": "test"}}
        assert harness.header_refreshes == 1
        assert harness.switch_account_btn.cget("text") == "Account"

        print("Wave 46 account header Tkinter smoke test passed.")
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
'''
    SMOKE.write_text(smoke_text, encoding="utf-8")

    generated_tree = ast.parse(DESKTOP.read_text(encoding="utf-8"))
    assert not functions(generated_tree, REFRESH)
    assert not functions(generated_tree, BUILD)
    print(
        f"Wave 46 extracted {REFRESH} ({REFRESH_LINES} lines) and {BUILD} ({BUILD_LINES} lines)."
    )


if __name__ == "__main__":
    main()
