from pathlib import Path

PATH = Path("tools/apply_cash_control_feature_wave_21.py")
text = PATH.read_text(encoding="utf-8")
old = '''    missing = [name for name in TARGETS + PROTECTED + BRIDGED if name not in functions]
    if missing:
        raise RuntimeError(f"Missing expected current-main functions: {missing}")

    first_line = min(functions[name].lineno for name in TARGETS)
    for name in BRIDGED:
        if functions[name].lineno >= first_line:
            raise RuntimeError(f"Dependency {name} is not defined before extraction point")
'''
new = '''    missing = [name for name in TARGETS + PROTECTED if name not in functions]
    if missing:
        raise RuntimeError(f"Missing expected current-main functions: {missing}")

    first_line = min(functions[name].lineno for name in TARGETS)
    binding_lines = {name: node.lineno for name, node in functions.items()}
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for item in ast.walk(target):
                    if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store):
                        binding_lines.setdefault(item.id, node.lineno)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                binding_lines.setdefault(alias.asname or alias.name.split(".")[0], node.lineno)

    missing_bindings = [name for name in BRIDGED if name not in binding_lines]
    if missing_bindings:
        raise RuntimeError(f"Missing application-owned dependency bindings: {missing_bindings}")
    for name in BRIDGED:
        if binding_lines[name] >= first_line:
            raise RuntimeError(f"Dependency {name} is not bound before extraction point")
'''
if text.count(old) != 1:
    raise RuntimeError(f"Expected one alias-guard block; found {text.count(old)}")
text = text.replace(old, new, 1)
PATH.write_text(text, encoding="utf-8")
print("Cash Control extractor alias guard corrected")
