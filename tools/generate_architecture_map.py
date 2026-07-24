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
SQL_RE = re.compile(
    r"\b(?:FROM|JOIN|INTO|UPDATE|TABLE|DELETE\s+FROM)\s+[\"'`\[]?([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)
FILE_LITERAL_RE = re.compile(
    r"""(?ix)
    ["']([^"'\n]+\.(?:json|db|sqlite|sqlite3|xlsx|xls|csv|pdf|docx|txt|log|png|jpg|jpeg|ini|toml|yaml|yml))["']
    """
)
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

FEATURE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("authentication", ("login", "password", "account", "permission", "role", "session", "user")),
    ("dashboard", ("dashboard", "kpi", "summary", "cash_control", "cashcontrol")),
    ("clients", ("client", "borrower", "loan_application", "application_form")),
    ("collectors", ("collector", "route", "area_assignment")),
    ("data_bank", ("data_bank", "databank", "data_grid", "payment_grid", "monthly_grid")),
    ("payments", ("payment", "transaction", "advance", "pass", "allocation")),
    ("loans", ("loan", "principal", "interest", "renew", "offset", "7x7", "x7")),
    ("reports", ("report", "statement", "receipt", "pdf", "ledger", "print")),
    ("payroll", ("payroll", "employee", "salary", "payslip", "sss", "pagibig", "philhealth")),
    ("backup", ("backup", "restore", "dump", "archive")),
    ("settings", ("setting", "maintenance", "theme", "appearance", "preference")),
    ("web_portal", ("fastapi", "router", "portal", "endpoint", "api")),
    ("utilities", ("util", "helper", "format", "parse", "normalize", "validate")),
)

RISK_TERMS: dict[str, tuple[str, ...]] = {
    "authentication": ("password", "login", "auth", "permission", "role", "session", "account"),
    "financial_calculation": (
        "balance", "principal", "interest", "allocation", "renew", "offset",
        "7x7", "x7", "amort", "due_amount",
    ),
    "database_write": (
        "insert", "update", "delete", "execute", "executemany", "commit", "rollback",
        "save_", "_save", "create table", "alter table", "drop table",
    ),
    "database_read": ("select", "fetch", "query", "cursor", "load_", "_load"),
    "filesystem": (
        "open(", "write_text", "write_bytes", "unlink", "rename", "replace(",
        "mkdir", "rmdir", "shutil", "pathlib",
    ),
    "reports": ("report", "pdf", "receipt", "statement", "ledger", "print"),
    "backup": ("backup", "restore", "pg_dump", "archive"),
    "network": ("requests.", "urlopen", "httpx", "urllib", "socket"),
    "ui_only": (
        "tk.", "ttk.", ".pack(", ".grid(", ".place(", ".configure(",
        ".config(", ".bind(", "stringvar", "booleanvar", "treeview",
    ),
}

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
    """Return the latest commit that changed scanned Python source.

    The generator itself is excluded from the map, so committing generated maps does
    not change this marker. That keeps regeneration deterministic for CI.
    """
    try:
        return subprocess.check_output(
            [
                "git", "log", "-1", "--format=%H", "--",
                "*.py", ":(exclude)tools/generate_architecture_map.py",
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
    hay = f"{name} {file_path} {source[:2000]}".lower()
    for feature, terms in FEATURE_RULES:
        if any(term in hay for term in terms):
            return feature
    return "other"


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
        action = "Represents"
    detail = f"{action} {words or name} for the {feature.replace('_', ' ')} feature."
    if calls:
        detail += f" Main detected dependency: {calls[0]}."
    return detail


def risk_for(name: str, source: str, calls: Iterable[str], tables: set[str]) -> tuple[str, list[str]]:
    hay = f"{name}\n{source}".lower()
    call_text = " ".join(calls).lower()
    hits: list[str] = []
    for risk, terms in RISK_TERMS.items():
        if any(term in hay or term in call_text for term in terms):
            hits.append(risk)
    if tables and "database_read" not in hits and "database_write" not in hits:
        hits.append("database_read")
    ordered = [
        "authentication", "financial_calculation", "database_write", "backup",
        "filesystem", "network", "reports", "database_read", "ui_only",
    ]
    level = "support"
    for item in ordered:
        if item in hits:
            level = item
            break
    if level == "ui_only" and any(
        item in hits for item in ("database_read", "database_write", "filesystem", "financial_calculation")
    ):
        level = next(
            item for item in ordered if item in hits and item != "ui_only"
        )
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

    def visit_Name(self, node: ast.Name) -> Any:
        if isinstance(node.ctx, ast.Load):
            self.loads.add(node.id)
        elif isinstance(node.ctx, (ast.Store, ast.Del)):
            self.stores.add(node.id)

    def visit_Call(self, node: ast.Call) -> Any:
        call = dotted(node.func)
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
        if call.rsplit(".", 1)[-1] in BIND_METHODS and node.args:
            target_node = node.args[-1]
            target = dotted(target_node)
            if target:
                self.callbacks.append({
                    "kind": call.rsplit(".", 1)[-1],
                    "target": target,
                    "line": getattr(node, "lineno", 0),
                    "event": unparse(node.args[0]) if len(node.args) > 1 else "",
                })
        for arg in [*node.args, *(kw.value for kw in node.keywords)]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                self.tables.update(SQL_RE.findall(arg.value))
                self.files.update(FILE_LITERAL_RE.findall(repr(arg.value)))
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> Any:
        value = dotted(node.value)
        for target in node.targets:
            target_name = dotted(target)
            if (
                value
                and isinstance(target, ast.Attribute)
                and IDENT.match(target.attr)
                and "." in target_name
            ):
                self.monkey_patches.append({
                    "target": target_name,
                    "source": value,
                    "line": getattr(node, "lineno", 0),
                })
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> Any:
        if isinstance(node.value, str):
            self.tables.update(SQL_RE.findall(node.value))
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
        scanner.visit(node)
        globals_read = sorted(
            name for name in scanner.loads
            if name in module_globals and name not in scanner.stores
        )
        globals_written = sorted(name for name in scanner.stores if name in module_globals)
        imports_used = sorted(imports[name] for name in scanner.loads if name in imports)
        feature = infer_feature(node.name, file_path, src)
        risk, flags = risk_for(node.name, src, scanner.calls, scanner.tables)
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
            feature = infer_feature(node.name, file_path, class_src)
            risk, flags = risk_for(node.name, class_src, [], set())
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
                "application_file": rel(path).startswith(APP_PREFIXES),
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

    duplicates = {
        name: ids for name, ids in sorted(duplicate_names.items())
        if len(ids) > 1
    }
    orphans = [
        s.id for s in symbols
        if s.kind in {"function", "method"}
        and not s.callers
        and not any(cb.get("target", "").endswith(s.name) for cb in callbacks)
        and not any(p.get("source", "").endswith(s.name) for p in monkey_patches)
        and s.name not in {"main", "__init__"}
    ]

    suggestions: list[dict[str, Any]] = []
    by_feature_symbols: dict[str, list[Symbol]] = defaultdict(list)
    for s in symbols:
        if s.kind in {"function", "method"}:
            by_feature_symbols[s.feature].append(s)
    for feature, items in sorted(by_feature_symbols.items()):
        safe = [
            s for s in items
            if s.risk in {"ui_only", "support", "database_read"}
            and s.lines <= 300
        ]
        safe.sort(key=lambda s: (s.file, s.line))
        batch: list[Symbol] = []
        total = 0
        for s in safe:
            if batch and (total + s.lines > 800 or len(batch) >= 18):
                if total >= 150:
                    suggestions.append({
                        "feature": feature,
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
                "risk": sorted({x.risk for x in batch}),
                "lines": total,
                "functions": [x.id for x in batch],
            })
    suggestions.sort(key=lambda item: (-item["lines"], item["feature"]))

    return {
        "schema_version": 1,
        "generated_from_commit": git_sha(),
        "summary": {
            "python_files": len(modules),
            "application_python_files": sum(1 for m in modules if m.get("application_file")),
            "total_python_lines": sum(m.get("lines", 0) for m in modules),
            "symbols": len(symbols),
            "classes": sum(1 for s in symbols if s.kind == "class"),
            "functions": sum(1 for s in symbols if s.kind == "function"),
            "methods": sum(1 for s in symbols if s.kind == "method"),
            "nested_functions": sum(1 for s in symbols if s.kind == "nested_function"),
            "resolved_call_edges": sum(len(s.calls_resolved) for s in symbols),
            "ui_callback_edges": len(callbacks),
            "monkey_patches": len(monkey_patches),
            "database_tables": len(table_users),
            "duplicate_names": len(duplicates),
            "possible_orphans": len(orphans),
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
            "callbacks": callbacks,
            "monkey_patches": monkey_patches,
            "possible_orphans": sorted(orphans),
            "modularization_suggestions": suggestions,
        },
        "parse_errors": parse_errors,
        "limitations": [
            "Dynamic imports and runtime-generated attribute names may not resolve.",
            "Callback and monkey-patch detection is static and may include false positives.",
            "SQL assembled from many runtime fragments may not reveal every table.",
            "Possible orphan symbols may still be called by reflection, Tkinter, plugins, or external code.",
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
    out = md_header("SPINA Feature Map", data)
    for feature, ids in data["indexes"]["features"].items():
        symbols = [by_id[i] for i in ids]
        out += [
            f"## {feature.replace('_', ' ').title()}",
            "",
            f"**{len(symbols)} symbols · {sum(s['lines'] for s in symbols):,} source lines**",
            "",
        ]
        files = Counter(s["file"] for s in symbols)
        out.append("Main files: " + ", ".join(f"`{f}` ({n})" for f, n in files.most_common(8)))
        out.append("")
        for s in sorted(symbols, key=lambda x: (-x["lines"], x["file"], x["line"]))[:20]:
            out.append(f"- {symbol_label(s)} — {s['purpose']} Risk: **{s['risk']}**.")
        if len(symbols) > 20:
            out.append(f"- …and {len(symbols) - 20} more symbols in `architecture-map.json`.")
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
    out = md_header("SPINA Dependency Map", data)
    out += ["## Resolved call connections", ""]
    connected = [s for s in data["symbols"] if s["calls_resolved"] or s["callers"]]
    for s in sorted(connected, key=lambda x: (-len(x["callers"]) - len(x["calls_resolved"]), x["qualified_name"]))[:300]:
        calls = [by_id[i]["qualified_name"] for i in s["calls_resolved"][:8] if i in by_id]
        callers = [by_id[i]["qualified_name"] for i in s["callers"][:8] if i in by_id]
        out.append(f"### `{s['qualified_name']}`")
        out.append("")
        out.append("Calls: " + (", ".join(f"`{x}`" for x in calls) if calls else "none resolved"))
        out.append("")
        out.append("Called by: " + (", ".join(f"`{x}`" for x in callers) if callers else "none resolved"))
        out.append("")
    out += ["## Tkinter and callback connections", ""]
    for item in data["indexes"]["callbacks"][:300]:
        owner = by_id.get(item["owner"], {})
        out.append(
            f"- `{owner.get('qualified_name', item['owner'])}` → `{item['target']}` "
            f"through **{item['kind']}** at line {item['line']}."
        )
    out += ["", "## Monkey-patch and runtime assignment connections", ""]
    for item in data["indexes"]["monkey_patches"][:300]:
        owner = by_id.get(item["owner"], {})
        out.append(
            f"- `{owner.get('qualified_name', item['owner'])}` assigns `{item['source']}` "
            f"to `{item['target']}` at line {item['line']}."
        )
    out += ["", "## Possible unreferenced symbols", ""]
    for sid in data["indexes"]["possible_orphans"][:300]:
        if sid in by_id:
            out.append(f"- {symbol_label(by_id[sid])}")
    out.append("")
    return "\n".join(out).rstrip() + "\n"


def render_database_map(data: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> str:
    out = md_header("SPINA Database and File Access Map", data)
    out += ["## Detected database tables", ""]
    for table, ids in data["indexes"]["database_tables"].items():
        out += [f"### `{table}`", ""]
        for sid in ids:
            s = by_id.get(sid)
            if s:
                out.append(f"- {symbol_label(s)} — risk `{s['risk']}`.")
        out.append("")
    out += ["## Detected file paths and file types", ""]
    for file_path, ids in data["indexes"]["file_paths"].items():
        out += [f"### `{file_path}`", ""]
        for sid in ids[:40]:
            s = by_id.get(sid)
            if s:
                out.append(f"- {symbol_label(s)}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def render_risk_map(data: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> str:
    out = md_header("SPINA Risk and Modularization Map", data)
    out += ["## Risk groups", ""]
    for risk, ids in data["indexes"]["risks"].items():
        symbols = [by_id[i] for i in ids if i in by_id]
        out += [
            f"### {risk.replace('_', ' ').title()}",
            "",
            f"**{len(symbols)} symbols · {sum(s['lines'] for s in symbols):,} lines**",
            "",
        ]
        for s in sorted(symbols, key=lambda x: (-x["lines"], x["file"], x["line"]))[:40]:
            out.append(f"- {symbol_label(s)} — {s['purpose']}")
        if len(symbols) > 40:
            out.append(f"- …and {len(symbols) - 40} more.")
        out.append("")
    out += ["## Suggested larger modularization batches", ""]
    for index, item in enumerate(data["indexes"]["modularization_suggestions"][:40], start=1):
        out.append(
            f"### Batch {index}: {item['feature'].replace('_', ' ').title()} "
            f"({item['lines']} lines)"
        )
        out.append("")
        out.append("Risk mix: " + ", ".join(f"`{r}`" for r in item["risk"]))
        out.append("")
        for sid in item["functions"]:
            s = by_id.get(sid)
            if s:
                out.append(f"- {symbol_label(s)} — {s['purpose']}")
        out.append("")
    out += ["## Duplicate symbol names", ""]
    for name, ids in list(data["indexes"]["duplicates"].items())[:300]:
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
