#!/usr/bin/env python3
"""Guarded extractor for small batches of pure top-level helpers.

The extractor is dry-run by default. It only applies a manifest when every
helper exactly matches its expected source hash, signature, dependencies, and
module destination. Mixed source/extracted states are rejected.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import hashlib
import json
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST = Path("tools/fixtures/pure_helper_batch_01_manifest.json")


def _load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("helpers"), list):
        raise RuntimeError("Manifest must contain a helpers list")
    if not data.get("app"):
        raise RuntimeError("Manifest must contain an app path")
    return data


def _source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _external_names(node: ast.FunctionDef) -> list[str]:
    local_names = {
        arg.arg
        for arg in (
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        )
    }
    if node.args.vararg:
        local_names.add(node.args.vararg.arg)
    if node.args.kwarg:
        local_names.add(node.args.kwarg.arg)
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
            local_names.add(child.id)
    loaded = {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
    }
    return sorted(loaded - local_names - set(dir(builtins)) - {node.name})


def _matching_imports(tree: ast.Module, module: str, name: str) -> list[ast.ImportFrom]:
    matches: list[ast.ImportFrom] = []
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.module != module:
            continue
        for alias in node.names:
            if alias.name == name and (alias.asname is None or alias.asname == name):
                matches.append(node)
    return matches


def _module_definitions(module_path: Path, name: str) -> list[ast.FunctionDef]:
    if not module_path.exists():
        raise RuntimeError(f"Destination module does not exist: {module_path}")
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    return [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]


def inspect(manifest_path: Path) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    app_path = Path(manifest["app"])
    app_source = app_path.read_text(encoding="utf-8")
    app_tree = ast.parse(app_source, filename=str(app_path))

    results: list[dict[str, Any]] = []
    states: set[str] = set()

    for item in manifest["helpers"]:
        name = str(item["name"])
        module = str(item["module"])
        module_path = Path(item["module_path"])
        expected_signature = str(item["signature"])
        expected_hash = str(item["expected_source_sha256"])
        allowed_external = sorted(str(x) for x in item.get("allowed_external_names", []))

        definitions = [
            node
            for node in app_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        ]
        imports = _matching_imports(app_tree, module, name)
        module_defs = _module_definitions(module_path, name)

        if len(definitions) == 1 and not imports:
            state = "source"
            node = definitions[0]
            source = ast.get_source_segment(app_source, node)
            if source is None:
                raise RuntimeError(f"Could not recover exact source for {name}")
            if ast.unparse(node.args) != expected_signature:
                raise RuntimeError(
                    f"Unexpected signature for {name}: {ast.unparse(node.args)!r}"
                )
            if node.decorator_list:
                raise RuntimeError(f"Decorated helper is not eligible: {name}")
            if any(isinstance(child, (ast.Global, ast.Nonlocal)) for child in ast.walk(node)):
                raise RuntimeError(f"Global/nonlocal state is not eligible: {name}")
            actual_external = _external_names(node)
            if actual_external != allowed_external:
                raise RuntimeError(
                    f"Unexpected dependencies for {name}: {actual_external!r}; "
                    f"expected {allowed_external!r}"
                )
            actual_hash = _source_hash(source)
            if actual_hash != expected_hash:
                raise RuntimeError(
                    f"Source hash changed for {name}: {actual_hash}; expected {expected_hash}"
                )
            if module_defs:
                raise RuntimeError(
                    f"Mixed state for {name}: source definition and destination definition both exist"
                )
            details = {
                "line": node.lineno,
                "end_line": node.end_lineno,
                "source": source,
                "source_sha256": actual_hash,
            }
        elif not definitions and len(imports) == 1:
            state = "extracted"
            if len(module_defs) != 1:
                raise RuntimeError(
                    f"Expected one destination definition for {name}, found {len(module_defs)}"
                )
            module_source = module_path.read_text(encoding="utf-8")
            source = ast.get_source_segment(module_source, module_defs[0])
            if source is None:
                raise RuntimeError(f"Could not recover destination source for {name}")
            actual_hash = _source_hash(source)
            if actual_hash != expected_hash:
                raise RuntimeError(
                    f"Destination source hash changed for {name}: {actual_hash}; expected {expected_hash}"
                )
            if ast.unparse(module_defs[0].args) != expected_signature:
                raise RuntimeError(f"Destination signature changed for {name}")
            actual_external = _external_names(module_defs[0])
            if actual_external != allowed_external:
                raise RuntimeError(
                    f"Destination dependencies changed for {name}: {actual_external!r}"
                )
            details = {
                "import_line": imports[0].lineno,
                "source": source,
                "source_sha256": actual_hash,
            }
        else:
            raise RuntimeError(
                f"Invalid state for {name}: definitions={len(definitions)}, imports={len(imports)}, "
                f"destination_definitions={len(module_defs)}"
            )

        states.add(state)
        results.append(
            {
                "name": name,
                "module": module,
                "module_path": str(module_path),
                "state": state,
                "signature": expected_signature,
                "external_names": allowed_external,
                **details,
            }
        )

    if len(states) > 1:
        raise RuntimeError(f"Mixed batch state is not allowed: {sorted(states)}")

    return {
        "batch": manifest.get("batch"),
        "manifest": str(manifest_path),
        "app": str(app_path),
        "state": next(iter(states), "empty"),
        "helper_count": len(results),
        "helpers": results,
    }


def apply(manifest_path: Path) -> dict[str, Any]:
    report = inspect(manifest_path)
    if report["state"] == "extracted":
        report["changed"] = False
        return report
    if report["state"] != "source":
        raise RuntimeError(f"Cannot apply batch from state {report['state']!r}")

    manifest = _load_manifest(manifest_path)
    app_path = Path(manifest["app"])
    app_source = app_path.read_text(encoding="utf-8")
    app_lines = app_source.splitlines(keepends=True)

    replacements: list[tuple[int, int, str]] = []
    module_additions: dict[Path, list[str]] = {}

    for helper in report["helpers"]:
        start = int(helper["line"]) - 1
        end = int(helper["end_line"])
        import_line = f"from {helper['module']} import {helper['name']}\n"
        replacements.append((start, end, import_line))
        module_additions.setdefault(Path(helper["module_path"]), []).append(helper["source"])

    for start, end, replacement in sorted(replacements, reverse=True):
        app_lines[start:end] = [replacement]
    new_app_source = "".join(app_lines)

    new_module_sources: dict[Path, str] = {}
    for module_path, additions in module_additions.items():
        current = module_path.read_text(encoding="utf-8").rstrip()
        addition_text = "\n\n\n".join(additions)
        new_module_sources[module_path] = current + "\n\n\n" + addition_text + "\n"

    compile(new_app_source, str(app_path), "exec")
    for module_path, module_source in new_module_sources.items():
        compile(module_source, str(module_path), "exec")

    app_path.write_text(new_app_source, encoding="utf-8")
    for module_path, module_source in new_module_sources.items():
        module_path.write_text(module_source, encoding="utf-8")

    final_report = inspect(manifest_path)
    if final_report["state"] != "extracted":
        raise RuntimeError("Post-apply validation did not reach extracted state")
    final_report["changed"] = True
    return final_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    report = apply(args.manifest) if args.apply else inspect(args.manifest)
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.json:
        args.json.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
