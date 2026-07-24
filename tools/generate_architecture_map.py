"""Generate SPINA architecture maps from repository Python source.

The generator is deterministic and uses only the Python standard library. It scans
application and support modules, builds symbol and dependency indexes, detects UI
callbacks, monkey patches, SQL/table access, file access, duplicate definitions,
risk areas, and suggested modularization groups, then writes JSON and Markdown maps.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "architecture"
JSON_OUT = ROOT / "architecture-map.json"
SKIP_DIRS = {
    ".git", ".github", ".venv", "venv", "env", "__pycache__", "node_modules",
    "site-packages", "dist", "build",
}
SKIP_FILES = {
    "tools/generate_architecture_map.py",
}
APP_PREFIXES = (
    "spina_app/",
    "OFFICIAL_SPINA_APP_",
)
SQL_TABLE_PATTERNS = (
    re.compile(
        r"\b(?:FROM|JOIN|INTO|UPDATE)\s+[\"'`\[]?([A-Za-z_][A-Za-z0-9_]*)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bDELETE\s+FROM\s+[\"'`\[]?([A-Za-z_][A-Za-z0-9_]*)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:CREATE|ALTER|DROP)\s+TABLE"
        r"(?:\s+IF\s+(?:NOT\s+)?EXISTS)?\s+"
        r"[\"'`\[]?([A-Za-z_][A-Za-z0-9_]*)",
        re.IGNORECASE,
    ),
)
SQL_READ_RE = re.compile(r"\b(?:SELECT|WITH|FROM|JOIN)\b", re.IGNORECASE)
SQL_WRITE_RE = re.compile(
    r"\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|CREATE\s+TABLE|"
    r"ALTER\s+TABLE|DROP\s+TABLE)\b",
    re.IGNORECASE,
)
SQL_STOPWORDS = {
    "a", "an", "all", "any", "client", "data", "excel", "generate", "if",
    "postgresql", "reports", "routes", "row", "set", "spina", "sqlite",
    "variance", "workflow",
}
FILE_LITERAL_RE = re.compile(
    r"""(?ix)
    ["']([^"'\n]+\.(?:json|db|sqlite|sqlite3|xlsx|xls|csv|pdf|docx|txt|log|png|jpg|jpeg|ini|toml|yaml|yml))["']
    """
)
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

FEATURE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("dashboard", ("dashboard", "kpi", "summary_card")),
    ("cash_control", ("cash_control", "cashcontrol", "cashctl")),
    ("navigation", (
        "side_nav", "sidebar", "navigation", "build_header", "header_button",
        "header_palette", "mode_toggle", "toolbar", "mousewheel", "vscroll",
        "month_label", "tab_selector",
    )),
    ("clients", ("client", "borrower", "application_form", "client_info", "cilog")),
    ("collectors", (
        "collector", "route", "area_assignment", "show_conflict", "unassigned_area",
    )),
    ("data_bank", (
        "data_bank", "databank", "data_grid", "payment_grid", "monthly_grid",
        "system_data", "delete_day", "close_day", "databank_day", "build_data_tab",
        "data_tree", "selected_cell", "cell_edit", "audit_tab", "clear_preview",
        "import_from_excel", "resize_databank", "refresh_data_grid",
    )),
    ("payments", (
        "payment", "transaction", "advance", "pass", "allocation", "paid_",
        "missed_reason",
    )),
    ("loans", ("loan", "principal", "interest", "renew", "offset", "7x7", "x7")),
    ("reports", ("report", "statement", "receipt", "pdf", "ledger", "print")),
    ("payroll", ("payroll", "employee", "salary", "payslip", "sss", "pagibig", "philhealth")),
    ("backup", ("backup", "restore", "pg_dump", "archive")),
    ("settings", ("setting", "maintenance", "theme", "appearance", "preference")),
    ("database", ("postgres", "postgresql", "pg_", "sql", "database", "loandb", "cursor", "connection")),
    ("notes", ("note_editor", "noteeditor", "client_notes", "collector_notes", "notes", "note")),
    ("web_portal", ("fastapi", "router", "portal", "endpoint", "api")),
    ("utilities", (
        "util", "helper", "format", "parse", "normalize", "validate", "date_range",
        "open_path", "getv", "wrap_to_width", "walk_widgets",
    )),
    ("authentication", (
        "login", "password", "account", "permission", "role_access", "apply_role",
        "session", "users_db", "user_role", "switch_account", "account_based",
        "role", "make_salt", "access_prefs",
    )),
)

AUTH_TERMS = (
    "password", "login", "authenticate", "authentication", "permission",
    "role_access", "apply_role", "session", "users_db", "user_role",
    "switch_account", "account_based",
)
FINANCIAL_TERMS = (
    "balance", "principal", "interest", "allocation", "renew", "offset",
    "7x7", "x7", "amort", "due_amount",
)
REPORT_TERMS = ("report", "pdf", "receipt", "statement", "ledger", "print")
BACKUP_TERMS = ("backup", "restore", "pg_dump", "archive")
NETWORK_TERMS = ("requests", "urlopen", "httpx", "urllib", "socket")
UI_CALL_SUFFIXES = {
    "pack", "grid", "place", "configure", "config", "bind", "bind_all",
    "protocol", "after", "after_idle", "heading", "column", "tag_configure",
    "selection_set", "selection_remove", "focus", "focus_set", "see",
}
DB_READ_SUFFIXES = {"fetchone", "fetchall", "fetchmany", "cursor"}
DB_WRITE_SUFFIXES = {"commit", "rollback", "executemany"}

CALLBACK_KEYWORDS = {
    "command", "validatecommand", "invalidcommand", "postcommand",
    "xscrollcommand", "yscrollcommand",
}
BIND_METHODS = {"bind", "bind_all", "protocol", "after", "after_idle"}
DB_CALLS = {"execute", "executemany", "commit", "rollback", "cursor"}
FILE_CALLS = {
    "open", "read_text", "read_bytes", "write_text", "write_bytes", "unlink",
    "rename", "replace", "mkdir", "rmdir", "remove", "copy", "copy2", "move",
}


def git_sha() -> str:
    """Return the latest commit that changed non-architecture Python source.

    The generator and its validator are excluded from this marker, keeping generated
    documentation deterministic when architecture tooling itself is improved.
    """
    try:
        return subprocess.check_output(
            [
                "git", "log", "-1", "--format=%H", "--",
                "*.py",
                ":(exclude)tools/generate_architecture_map.py",
                ":(exclude)tools/test_architecture_map.py",
            ],
            cwd=ROOT,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def dotted(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return dotted(node.func)
    if isinstance(node, ast.Subscript):
        return dotted(node.value)
    return ""


def unparse(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def clean_doc(text: str | None) -> str:
    if not text:
        return ""
    first = " ".join(text.strip().split())
    return first[:300]


def infer_feature(name: str, file_path: str, source: str) -> str:
    """Infer feature ownership from symbol identity, not implementation-body text.

    Leaf function names receive the strongest weight, module paths receive medium
    weight, and parent qualified names provide context for nested/generic helpers.
    Rule order resolves ties in favor of domain features before authentication.
    """
    full = name.lower()
    leaf = full.rsplit(".", 1)[-1]
    parent = full.rsplit(".", 1)[0] if "." in full else ""
    path = file_path.lower() if file_path.startswith("spina_app/") else ""
    ranked: list[tuple[int, int, str]] = []
    for order, (feature, terms) in enumerate(FEATURE_RULES):
        score = 0
        for term in terms:
            if term in leaf:
                score = max(score, 12)
            elif term in parent:
                score = max(score, 4)
            if term in path:
                score = max(score, 8)
        if score:
            ranked.append((score, -order, feature))
    return max(ranked)[2] if ranked else "other"



def explain_symbol(kind: str, name: str, doc: str, feature: str, calls: list[str]) -> str:
    if doc:
        return doc
    words = " ".join(part for part in re.split(r"[_\W]+", name) if part)
    action = "Defines"
    if kind in {"function", "method", "nested_function"}:
        action = "Handles"
        if name.startswith(("get_", "_get_", "find_", "_find_")):
            action = "Retrieves"
        elif name.startswith(("set_", "_set_", "update_", "_update_")):
            action = "Updates"
        elif name.startswith(("build_", "_build_", "create_", "_create_")):
            action = "Builds"
        elif name.startswith(("load_", "_load_", "fetch_", "_fetch_")):
            action = "Loads"
        elif name.startswith(("save_", "_save_", "write_", "_write_")):
            action = "Saves"
        elif name.startswith(("delete_", "_delete_", "remove_", "_remove_")):
            action = "Removes"
        elif name.startswith(("refresh_", "_refresh_")):
            action = "Refreshes"
        elif name.startswith(("print_", "_print_", "generate_", "_generate_")):
            action = "Generates"
        elif name.startswith(("validate_", "_validate_")):
            action = "Validates"
    elif kind == "class":
        action = "Groups"
    return f"{action} {words or name} for the {feature.replace('_', ' ')} feature."



def _signature_has(signature: str, terms: Iterable[str]) -> bool:
    return any(term in signature for term in terms)


def risk_for(
    name: str,
    source: str,
    calls: Iterable[str],
    tables: set[str],
    *,
    sql_read: bool = False,
    sql_write: bool = False,
) -> tuple[str, list[str]]:
    call_list = list(calls)
    signature = f"{name} {' '.join(call_list)}".lower()
    suffixes = {call.rsplit(".", 1)[-1].lower() for call in call_list}
    hits: list[str] = []

    if _signature_has(signature, AUTH_TERMS):
        hits.append("authentication")
    if _signature_has(signature, FINANCIAL_TERMS):
        hits.append("financial_calculation")
    if sql_write or suffixes & DB_WRITE_SUFFIXES:
        hits.append("database_write")
    elif sql_read or tables or suffixes & DB_READ_SUFFIXES or "execute" in suffixes:
        hits.append("database_read")
    if suffixes & FILE_CALLS or _signature_has(signature, ("pathlib", "shutil")):
        hits.append("filesystem")
    if _signature_has(signature, REPORT_TERMS):
        hits.append("reports")
    if _signature_has(signature, BACKUP_TERMS):
        hits.append("backup")
    if _signature_has(signature, NETWORK_TERMS):
        hits.append("network")

    ui_detected = bool(suffixes & UI_CALL_SUFFIXES) or any(
        token in source for token in ("tk.", "ttk.", "StringVar", "BooleanVar", "Treeview")
    )
    if ui_detected:
        hits.append("ui_only")

    ordered = [
        "authentication", "financial_calculation", "database_write", "backup",
        "filesystem", "network", "reports", "database_read", "ui_only",
    ]
    level = next((item for item in ordered if item in hits), "support")
    return level, sorted(set(hits))



def discover_python_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*.py"):
        parts = set(path.relative_to(ROOT).parts)
        if parts & SKIP_DIRS:
            continue
        r = rel(path)
        if r in SKIP_FILES:
            continue
        files.append(path)
    return sorted(files, key=lambda p: rel(p).lower())


@dataclass
class Symbol:
    id: str
    name: str
    qualified_name: str
    kind: str
    file: str
    line: int
    end_line: int
    lines: int
    parent: str | None
    class_name: str | None
    args: list[str]
    docstring: str
    purpose: str
    feature: str
    risk: str
    risk_flags: list[str]
    calls_raw: list[str]
    calls_resolved: list[str] = field(default_factory=list)
    callers: list[str] = field(default_factory=list)
    callbacks: list[dict[str, Any]] = field(default_factory=list)
    monkey_patches: list[dict[str, Any]] = field(default_factory=list)
    imports_used: list[str] = field(default_factory=list)
    globals_read: list[str] = field(default_factory=list)
    globals_written: list[str] = field(default_factory=list)
    database_tables: list[str] = field(default_factory=list)
    file_paths: list[str] = field(default_factory=list)
    source_sha256: str = ""


def static_string(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:
                parts.append("{}")
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = static_string(node.left)
        right = static_string(node.right)
        return left + right if left or right else ""
    return ""


def extract_sql_tables(text: str) -> set[str]:
    tables: set[str] = set()
    for pattern in SQL_TABLE_PATTERNS:
        for value in pattern.findall(text):
            name = str(value).strip().lower()
            if len(name) > 1 and name not in SQL_STOPWORDS:
                tables.add(name)
    cte_names = {
        value.lower()
        for value in re.findall(r"\b(?:WITH|,)\s*([A-Za-z_][A-Za-z0-9_]*)\s+AS\s*\(", text, re.IGNORECASE)
    }
    return tables - cte_names


class FunctionScanner(ast.NodeVisitor):
    def __init__(self, module: str, qualname: str, local_names: set[str]) -> None:
        self.module = module
        self.qualname = qualname
        self.local_names = local_names
        self.calls: set[str] = set()
        self.callbacks: list[dict[str, Any]] = []
        self.monkey_patches: list[dict[str, Any]] = []
        self.loads: set[str] = set()
        self.stores: set[str] = set()
        self.tables: set[str] = set()
        self.files: set[str] = set()
        self.sql_read = False
        self.sql_write = False

    def record_sql(self, text: str) -> None:
        if not text:
            return
        self.tables.update(extract_sql_tables(text))
        if SQL_READ_RE.search(text):
            self.sql_read = True
        if SQL_WRITE_RE.search(text):
            self.sql_write = True

    def visit_Name(self, node: ast.Name) -> Any:
        if isinstance(node.ctx, ast.Load):
            self.loads.add(node.id)
        elif isinstance(node.ctx, (ast.Store, ast.Del)):
            self.stores.add(node.id)

    def visit_Call(self, node: ast.Call) -> Any:
        call = dotted(node.func)
        suffix = call.rsplit(".", 1)[-1] if call else ""
        if call:
            self.calls.add(call)
        for kw in node.keywords:
            if kw.arg in CALLBACK_KEYWORDS:
                target = dotted(kw.value)
                if target:
                    self.callbacks.append({
                        "kind": kw.arg,
                        "target": target,
                        "line": getattr(node, "lineno", 0),
                    })
        if suffix in BIND_METHODS and node.args:
            target_node = node.args[-1]
            target = dotted(target_node)
            if target:
                self.callbacks.append({
                    "kind": suffix,
                    "target": target,
                    "line": getattr(node, "lineno", 0),
                    "event": unparse(node.args[0]) if len(node.args) > 1 else "",
                })
        if suffix in {"execute", "executemany"} and node.args:
            self.record_sql(static_string(node.args[0]))
        for arg in [*node.args, *(kw.value for kw in node.keywords)]:
            value = static_string(arg)
            if value:
                self.files.update(FILE_LITERAL_RE.findall(repr(value)))
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> Any:
        value_name = dotted(node.value)
        value_text = static_string(node.value)
        for target in node.targets:
            target_name = dotted(target)
            base = target_name.split(".", 1)[0]
            if value_text and any(term in target_name.lower() for term in ("sql", "query", "statement")):
                self.record_sql(value_text)
            if (
                value_name
                and isinstance(target, ast.Attribute)
                and IDENT.match(target.attr)
                and "." in target_name
                and base not in {"self", "cls"}
                and base not in self.local_names
            ):
                self.monkey_patches.append({
                    "target": target_name,
                    "source": value_name,
                    "line": getattr(node, "lineno", 0),
                })
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:
        target_name = dotted(node.target)
        value_text = static_string(node.value)
        if value_text and any(term in target_name.lower() for term in ("sql", "query", "statement")):
            self.record_sql(value_text)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> Any:
        if isinstance(node.value, str):
            self.files.update(FILE_LITERAL_RE.findall(repr(node.value)))



def module_name(path: Path) -> str:
    r = rel(path)
    if r.endswith("/__init__.py"):
        r = r[:-12]
    elif r.endswith(".py"):
        r = r[:-3]
    return r.replace("/", ".")


def source_segment(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def function_args(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    args = [
        *(a.arg for a in node.args.posonlyargs),
        *(a.arg for a in node.args.args),
        *(a.arg for a in node.args.kwonlyargs),
    ]
    if node.args.vararg:
        args.append("*" + node.args.vararg.arg)
    if node.args.kwarg:
        args.append("**" + node.args.kwarg.arg)
    return args


def collect_symbols(path: Path, tree: ast.Module, text: str) -> tuple[list[Symbol], dict[str, Any]]:
    file_path = rel(path)
    module = module_name(path)
    lines = text.splitlines()
    module_globals = {
        node.id
        for stmt in tree.body
        for node in (
            ([stmt.target] if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) else [])
            + ([t for t in stmt.targets if isinstance(t, ast.Name)] if isinstance(stmt, ast.Assign) else [])
        )
        if isinstance(node, ast.Name)
    }
    imports: dict[str, str] = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                imports[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(stmt, ast.ImportFrom):
            base = "." * stmt.level + (stmt.module or "")
            for alias in stmt.names:
                imports[alias.asname or alias.name] = f"{base}.{alias.name}".strip(".")

    module_monkey_patches: list[dict[str, Any]] = []
    for stmt in tree.body:
        if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            continue
        value_node = stmt.value
        value = dotted(value_node)
        targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
        for target in targets:
            target_name = dotted(target)
            if value and isinstance(target, ast.Attribute) and "." in target_name:
                module_monkey_patches.append({
                    "owner": f"{file_path}:module",
                    "target": target_name,
                    "source": value,
                    "line": getattr(stmt, "lineno", 0),
                })

    symbols: list[Symbol] = []
    duplicate_counter: Counter[str] = Counter()

    def add_function(
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        parent: str | None,
        class_name: str | None,
        nested: bool,
    ) -> None:
        qual = ".".join(part for part in (module, class_name, parent, node.name) if part)
        kind = "method" if class_name and not nested else ("nested_function" if nested else "function")
        src = source_segment(lines, node)
        scanner = FunctionScanner(module, qual, set(function_args(node)))
        for statement in node.body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            scanner.visit(statement)
        globals_read = sorted(
            name for name in scanner.loads
            if name in module_globals and name not in scanner.stores
        )
        globals_written = sorted(name for name in scanner.stores if name in module_globals)
        imports_used = sorted(imports[name] for name in scanner.loads if name in imports)
        feature_identity = ".".join(
            part for part in (class_name, parent, node.name) if part
        )
        feature = infer_feature(feature_identity, file_path, "")
        risk, flags = risk_for(
            node.name,
            src,
            scanner.calls,
            scanner.tables,
            sql_read=scanner.sql_read,
            sql_write=scanner.sql_write,
        )
        symbol_id = f"{file_path}:{node.lineno}:{qual}"
        duplicate_counter[f"{class_name or ''}.{node.name}"] += 1
        symbol = Symbol(
            id=symbol_id,
            name=node.name,
            qualified_name=qual,
            kind=kind,
            file=file_path,
            line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            lines=(node.end_lineno or node.lineno) - node.lineno + 1,
            parent=parent,
            class_name=class_name,
            args=function_args(node),
            docstring=clean_doc(ast.get_docstring(node)),
            purpose="",
            feature=feature,
            risk=risk,
            risk_flags=flags,
            calls_raw=sorted(scanner.calls),
            callbacks=scanner.callbacks,
            monkey_patches=scanner.monkey_patches,
            imports_used=imports_used,
            globals_read=globals_read,
            globals_written=globals_written,
            database_tables=sorted(scanner.tables),
            file_paths=sorted(scanner.files),
            source_sha256=hashlib.sha256(src.encode("utf-8")).hexdigest(),
        )
        symbol.purpose = explain_symbol(
            symbol.kind, symbol.name, symbol.docstring, symbol.feature, symbol.calls_raw
        )
        symbols.append(symbol)

        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                add_function(child, node.name if not parent else f"{parent}.{node.name}", class_name, True)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add_function(node, None, None, False)
        elif isinstance(node, ast.ClassDef):
            class_src = source_segment(lines, node)
            feature = infer_feature(node.name, file_path, "")
            risk, flags = "container", []
            class_id = f"{file_path}:{node.lineno}:{module}.{node.name}"
            symbols.append(Symbol(
                id=class_id,
                name=node.name,
                qualified_name=f"{module}.{node.name}",
                kind="class",
                file=file_path,
                line=node.lineno,
                end_line=node.end_lineno or node.lineno,
                lines=(node.end_lineno or node.lineno) - node.lineno + 1,
                parent=None,
                class_name=node.name,
                args=[],
                docstring=clean_doc(ast.get_docstring(node)),
                purpose=explain_symbol("class", node.name, clean_doc(ast.get_docstring(node)), feature, []),
                feature=feature,
                risk=risk,
                risk_flags=flags,
                calls_raw=[],
                source_sha256=hashlib.sha256(class_src.encode("utf-8")).hexdigest(),
            ))
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    add_function(child, None, node.name, False)

    module_record = {
        "file": file_path,
        "module": module,
        "lines": len(lines),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "imports": imports,
        "module_globals": sorted(module_globals),
        "syntax_ok": True,
        "application_file": file_path.startswith(APP_PREFIXES),
        "monkey_patches": module_monkey_patches,
    }
    return symbols, module_record


def resolve_dependencies(symbols: list[Symbol]) -> None:
    by_name: dict[str, list[Symbol]] = defaultdict(list)
    by_qualified: dict[str, Symbol] = {}
    for symbol in symbols:
        by_name[symbol.name].append(symbol)
        by_qualified[symbol.qualified_name] = symbol

    for symbol in symbols:
        resolved: set[str] = set()
        for call in symbol.calls_raw:
            last = call.rsplit(".", 1)[-1]
            candidates = by_name.get(last, [])
            if len(candidates) == 1:
                resolved.add(candidates[0].id)
            else:
                same_file = [c for c in candidates if c.file == symbol.file]
                if len(same_file) == 1:
                    resolved.add(same_file[0].id)
                elif symbol.class_name:
                    same_class = [c for c in candidates if c.class_name == symbol.class_name]
                    if len(same_class) == 1:
                        resolved.add(same_class[0].id)
        symbol.calls_resolved = sorted(resolved)

    by_id = {s.id: s for s in symbols}
    for symbol in symbols:
        for callee_id in symbol.calls_resolved:
            callee = by_id.get(callee_id)
            if callee:
                callee.callers.append(symbol.id)
    for symbol in symbols:
        symbol.callers = sorted(set(symbol.callers))


def is_application_file(file_path: str) -> bool:
    return file_path.startswith(APP_PREFIXES)


def owner_is_application(owner: str, by_id: dict[str, dict[str, Any]]) -> bool:
    symbol = by_id.get(owner)
    if symbol:
        return is_application_file(symbol["file"])
    file_path = owner.split(":", 1)[0]
    return is_application_file(file_path)


def scan_repository() -> dict[str, Any]:
    symbols: list[Symbol] = []
    modules: list[dict[str, Any]] = []
    parse_errors: list[dict[str, Any]] = []
    for path in discover_python_files():
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        try:
            tree = ast.parse(text, filename=rel(path))
        except SyntaxError as exc:
            parse_errors.append({
                "file": rel(path),
                "line": exc.lineno,
                "message": exc.msg,
            })
            modules.append({
                "file": rel(path),
                "module": module_name(path),
                "lines": len(text.splitlines()),
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "syntax_ok": False,
                "application_file": is_application_file(rel(path)),
            })
            continue
        found, module_record = collect_symbols(path, tree, text)
        symbols.extend(found)
        modules.append(module_record)

    resolve_dependencies(symbols)
    symbol_dicts = [s.__dict__ for s in symbols]
    by_feature: dict[str, list[str]] = defaultdict(list)
    by_risk: dict[str, list[str]] = defaultdict(list)
    duplicate_names: dict[str, list[str]] = defaultdict(list)
    table_users: dict[str, list[str]] = defaultdict(list)
    file_users: dict[str, list[str]] = defaultdict(list)
    app_by_feature: dict[str, list[str]] = defaultdict(list)
    app_by_risk: dict[str, list[str]] = defaultdict(list)
    app_duplicate_names: dict[str, list[str]] = defaultdict(list)
    app_table_users: dict[str, list[str]] = defaultdict(list)
    app_file_users: dict[str, list[str]] = defaultdict(list)
    monkey_patches: list[dict[str, Any]] = []
    callbacks: list[dict[str, Any]] = []

    for s in symbols:
        by_feature[s.feature].append(s.id)
        by_risk[s.risk].append(s.id)
        duplicate_names[s.name].append(s.id)
        for table in s.database_tables:
            table_users[table].append(s.id)
        for file_path in s.file_paths:
            file_users[file_path].append(s.id)
        for patch in s.monkey_patches:
            monkey_patches.append({"owner": s.id, **patch})
        for callback in s.callbacks:
            callbacks.append({"owner": s.id, **callback})

        if is_application_file(s.file):
            app_by_feature[s.feature].append(s.id)
            app_by_risk[s.risk].append(s.id)
            app_duplicate_names[s.name].append(s.id)
            for table in s.database_tables:
                app_table_users[table].append(s.id)
            for file_path in s.file_paths:
                app_file_users[file_path].append(s.id)

    for module in modules:
        monkey_patches.extend(module.get("monkey_patches", []))

    duplicates = {
        name: ids for name, ids in sorted(duplicate_names.items())
        if len(ids) > 1
    }
    app_duplicates = {
        name: ids for name, ids in sorted(app_duplicate_names.items())
        if len(ids) > 1
    }

    def possible_orphans(items: Iterable[Symbol]) -> list[str]:
        return sorted(
            s.id for s in items
            if s.kind in {"function", "method"}
            and not s.callers
            and not any(cb.get("target", "").endswith(s.name) for cb in callbacks)
            and not any(p.get("source", "").endswith(s.name) for p in monkey_patches)
            and s.name not in {"main", "__init__"}
        )

    orphans = possible_orphans(symbols)
    app_symbols = [s for s in symbols if is_application_file(s.file)]
    app_orphans = possible_orphans(app_symbols)

    suggestions: list[dict[str, Any]] = []
    by_feature_file: dict[tuple[str, str], list[Symbol]] = defaultdict(list)
    for s in app_symbols:
        if s.kind in {"function", "method"}:
            by_feature_file[(s.feature, s.file)].append(s)
    for (feature, file_path), items in sorted(by_feature_file.items()):
        safe = [
            s for s in items
            if feature != "other"
            and s.risk in {"ui_only", "support", "database_read"}
            and s.lines <= 300
        ]
        safe.sort(key=lambda s: s.line)
        batch: list[Symbol] = []
        total = 0
        for s in safe:
            if batch and (total + s.lines > 800 or len(batch) >= 18):
                if total >= 150:
                    suggestions.append({
                        "feature": feature,
                        "file": file_path,
                        "risk": sorted({x.risk for x in batch}),
                        "lines": total,
                        "functions": [x.id for x in batch],
                    })
                batch, total = [], 0
            batch.append(s)
            total += s.lines
        if batch and total >= 150:
            suggestions.append({
                "feature": feature,
                "file": file_path,
                "risk": sorted({x.risk for x in batch}),
                "lines": total,
                "functions": [x.id for x in batch],
            })
    suggestions.sort(key=lambda item: (-item["lines"], item["feature"], item["file"]))

    app_callbacks = [
        item for item in callbacks
        if owner_is_application(item["owner"], {s.id: s.__dict__ for s in symbols})
    ]
    app_monkey_patches = [
        item for item in monkey_patches
        if owner_is_application(item["owner"], {s.id: s.__dict__ for s in symbols})
    ]

    return {
        "schema_version": 2,
        "generated_from_commit": git_sha(),
        "summary": {
            "python_files": len(modules),
            "application_python_files": sum(1 for m in modules if m.get("application_file")),
            "total_python_lines": sum(m.get("lines", 0) for m in modules),
            "symbols": len(symbols),
            "application_symbols": len(app_symbols),
            "classes": sum(1 for s in symbols if s.kind == "class"),
            "functions": sum(1 for s in symbols if s.kind == "function"),
            "methods": sum(1 for s in symbols if s.kind == "method"),
            "nested_functions": sum(1 for s in symbols if s.kind == "nested_function"),
            "resolved_call_edges": sum(len(s.calls_resolved) for s in symbols),
            "application_resolved_call_edges": sum(len(s.calls_resolved) for s in app_symbols),
            "ui_callback_edges": len(callbacks),
            "application_ui_callback_edges": len(app_callbacks),
            "monkey_patches": len(monkey_patches),
            "application_monkey_patches": len(app_monkey_patches),
            "database_tables": len(app_table_users),
            "repository_database_tables": len(table_users),
            "duplicate_names": len(app_duplicates),
            "repository_duplicate_names": len(duplicates),
            "possible_orphans": len(app_orphans),
            "repository_possible_orphans": len(orphans),
            "parse_errors": len(parse_errors),
        },
        "modules": modules,
        "symbols": symbol_dicts,
        "indexes": {
            "features": {k: sorted(v) for k, v in sorted(by_feature.items())},
            "risks": {k: sorted(v) for k, v in sorted(by_risk.items())},
            "duplicates": duplicates,
            "database_tables": {k: sorted(v) for k, v in sorted(table_users.items())},
            "file_paths": {k: sorted(v) for k, v in sorted(file_users.items())},
            "application_features": {k: sorted(v) for k, v in sorted(app_by_feature.items())},
            "application_risks": {k: sorted(v) for k, v in sorted(app_by_risk.items())},
            "application_duplicates": app_duplicates,
            "application_database_tables": {k: sorted(v) for k, v in sorted(app_table_users.items())},
            "application_file_paths": {k: sorted(v) for k, v in sorted(app_file_users.items())},
            "callbacks": callbacks,
            "application_callbacks": app_callbacks,
            "monkey_patches": monkey_patches,
            "application_monkey_patches": app_monkey_patches,
            "possible_orphans": orphans,
            "application_possible_orphans": app_orphans,
            "modularization_suggestions": suggestions,
        },
        "parse_errors": parse_errors,
        "limitations": [
            "Dynamic imports and runtime-generated attribute names may not resolve.",
            "Callback and monkey-patch detection is static and may include false positives.",
            "SQL assembled from runtime fragments may not reveal every table.",
            "Possible orphan symbols may still be called by reflection, Tkinter, plugins, or external code.",
            "Risk labels are conservative planning hints, not proof of runtime behavior.",
            "Desktop smoke testing remains required before merging modularization changes.",
        ],
    }



def symbol_label(symbol: dict[str, Any]) -> str:
    return f"`{symbol['qualified_name']}` — {symbol['file']}:{symbol['line']}"


def md_header(title: str, data: dict[str, Any]) -> list[str]:
    s = data["summary"]
    return [
        f"# {title}",
        "",
        f"Generated from commit `{data['generated_from_commit']}`.",
        "",
        (
            f"Scanned **{s['python_files']} Python files**, **{s['total_python_lines']:,} lines**, "
            f"and **{s['symbols']:,} symbols**."
        ),
        "",
        "> This is a static architecture map. Runtime callbacks and dynamic monkey patches can still require desktop testing.",
        "",
    ]


def render_feature_map(data: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> str:
    out = md_header("SPINA Application Feature Map", data)
    out += [
        "> Primary sections below include only the desktop application and `spina_app/` modules. Tooling remains indexed in `function-index.md` and `architecture-map.json`.",
        "",
    ]
    for feature, ids in data["indexes"]["application_features"].items():
        symbols = [by_id[i] for i in ids]
        out += [
            f"## {feature.replace('_', ' ').title()}",
            "",
            f"**{len(symbols)} symbols · {sum(s['lines'] for s in symbols if s['kind'] != 'class'):,} non-overlapping function lines**",
            "",
        ]
        files = Counter(s["file"] for s in symbols)
        out.append("Main files: " + ", ".join(f"`{f}` ({n})" for f, n in files.most_common(8)))
        out.append("")
        for s in sorted(symbols, key=lambda x: (-x["lines"], x["file"], x["line"]))[:20]:
            out.append(f"- {symbol_label(s)} — {s['purpose']} Risk: **{s['risk']}**.")
        if len(symbols) > 20:
            out.append(f"- …and {len(symbols) - 20} more application symbols in `architecture-map.json`.")
        out.append("")
    return "\n".join(out).rstrip() + "\n"



def render_function_index(data: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> str:
    out = md_header("SPINA Function and Class Index", data)
    for file_path in sorted({s["file"] for s in data["symbols"]}):
        symbols = [s for s in data["symbols"] if s["file"] == file_path]
        out += [f"## `{file_path}`", ""]
        for s in sorted(symbols, key=lambda x: x["line"]):
            out.append(
                f"- **{s['qualified_name']}** ({s['kind']}, lines {s['line']}–{s['end_line']}, "
                f"{s['lines']} lines, risk `{s['risk']}`): {s['purpose']}"
            )
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def render_dependency_map(data: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> str:
    out = md_header("SPINA Application Dependency Map", data)
    out += [
        "> Connections shown here are limited to SPINA application files. The complete repository graph remains in `architecture-map.json`.",
        "",
        "## Resolved call connections",
        "",
    ]
    app_ids = {sid for ids in data["indexes"]["application_features"].values() for sid in ids}
    connected = [
        s for s in data["symbols"]
        if s["id"] in app_ids and (s["calls_resolved"] or s["callers"])
    ]
    for s in sorted(connected, key=lambda x: (-len(x["callers"]) - len(x["calls_resolved"]), x["qualified_name"]))[:300]:
        calls = [by_id[i]["qualified_name"] for i in s["calls_resolved"][:8] if i in app_ids]
        callers = [by_id[i]["qualified_name"] for i in s["callers"][:8] if i in app_ids]
        out.append(f"### `{s['qualified_name']}`")
        out.append("")
        out.append("Calls: " + (", ".join(f"`{x}`" for x in calls) if calls else "none resolved in application files"))
        out.append("")
        out.append("Called by: " + (", ".join(f"`{x}`" for x in callers) if callers else "none resolved in application files"))
        out.append("")
    out += ["## Tkinter and callback connections", ""]
    for item in data["indexes"]["application_callbacks"][:300]:
        owner = by_id.get(item["owner"], {})
        out.append(
            f"- `{owner.get('qualified_name', item['owner'])}` → `{item['target']}` "
            f"through **{item['kind']}** at line {item['line']}."
        )
    out += ["", "## Monkey-patch and runtime assignment connections", ""]
    for item in data["indexes"]["application_monkey_patches"][:300]:
        owner = by_id.get(item["owner"], {})
        out.append(
            f"- `{owner.get('qualified_name', item['owner'])}` assigns `{item['source']}` "
            f"to `{item['target']}` at line {item['line']}."
        )
    out += ["", "## Possible unreferenced application symbols", ""]
    for sid in data["indexes"]["application_possible_orphans"][:300]:
        if sid in by_id:
            out.append(f"- {symbol_label(by_id[sid])}")
    out.append("")
    return "\n".join(out).rstrip() + "\n"



def render_database_map(data: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> str:
    out = md_header("SPINA Application Database and File Access Map", data)
    out += [
        "> SQL tables are detected only from strings used by `execute`/`executemany` or variables named like SQL/query statements. Ordinary prose is excluded.",
        "",
        "## Detected application database tables",
        "",
    ]
    for table, ids in data["indexes"]["application_database_tables"].items():
        out += [f"### `{table}`", ""]
        for sid in ids:
            s = by_id.get(sid)
            if s:
                out.append(f"- {symbol_label(s)} — risk `{s['risk']}`.")
        out.append("")
    out += ["## Detected application file paths and file types", ""]
    for file_path, ids in data["indexes"]["application_file_paths"].items():
        out += [f"### `{file_path}`", ""]
        for sid in ids[:40]:
            s = by_id.get(sid)
            if s:
                out.append(f"- {symbol_label(s)}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"



def render_risk_map(data: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> str:
    out = md_header("SPINA Application Risk and Modularization Map", data)
    out += [
        "> Risk groups and batches below include only application functions and methods. Container classes are excluded from line totals so method lines are not counted twice.",
        "",
        "## Application risk groups",
        "",
    ]
    for risk, ids in data["indexes"]["application_risks"].items():
        symbols = [by_id[i] for i in ids if i in by_id and by_id[i]["kind"] != "class"]
        if not symbols:
            continue
        out += [
            f"### {risk.replace('_', ' ').title()}",
            "",
            f"**{len(symbols)} symbols · {sum(s['lines'] for s in symbols):,} function lines**",
            "",
        ]
        for s in sorted(symbols, key=lambda x: (-x["lines"], x["file"], x["line"]))[:40]:
            out.append(f"- {symbol_label(s)} — {s['purpose']}")
        if len(symbols) > 40:
            out.append(f"- …and {len(symbols) - 40} more.")
        out.append("")
    out += ["## Suggested larger application modularization batches", ""]
    for index, item in enumerate(data["indexes"]["modularization_suggestions"][:40], start=1):
        out.append(
            f"### Batch {index}: {item['feature'].replace('_', ' ').title()} "
            f"({item['lines']} lines)"
        )
        out.append("")
        out.append(f"Source file: `{item['file']}`")
        out.append("")
        out.append("Risk mix: " + ", ".join(f"`{r}`" for r in item["risk"]))
        out.append("")
        for sid in item["functions"]:
            s = by_id.get(sid)
            if s:
                out.append(f"- {symbol_label(s)} — {s['purpose']}")
        out.append("")
    out += ["## Duplicate application symbol names", ""]
    for name, ids in list(data["indexes"]["application_duplicates"].items())[:300]:
        out.append(f"- `{name}`: " + ", ".join(f"`{by_id[i]['file']}:{by_id[i]['line']}`" for i in ids if i in by_id))
    out += ["", "## Static-analysis limitations", ""]
    out.extend(f"- {item}" for item in data["limitations"])
    out.append("")
    return "\n".join(out).rstrip() + "\n"



def write_outputs(data: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    by_id = {s["id"]: s for s in data["symbols"]}
    JSON_OUT.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    outputs = {
        OUT_DIR / "feature-map.md": render_feature_map(data, by_id),
        OUT_DIR / "function-index.md": render_function_index(data, by_id),
        OUT_DIR / "dependency-map.md": render_dependency_map(data, by_id),
        OUT_DIR / "database-access-map.md": render_database_map(data, by_id),
        OUT_DIR / "risk-map.md": render_risk_map(data, by_id),
    }
    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8")


def main() -> None:
    data = scan_repository()
    write_outputs(data)
    summary = data["summary"]
    print(
        "Architecture map generated:",
        f"{summary['python_files']} files,",
        f"{summary['symbols']} symbols,",
        f"{summary['resolved_call_edges']} resolved calls,",
        f"{summary['ui_callback_edges']} callbacks,",
        f"{summary['monkey_patches']} monkey patches.",
    )
    if data["parse_errors"]:
        raise SystemExit(f"Architecture map found {len(data['parse_errors'])} Python parse error(s).")


if __name__ == "__main__":
    main()
