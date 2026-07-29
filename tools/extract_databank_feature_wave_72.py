from __future__ import annotations

import ast
import hashlib
import textwrap
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE = Path("spina_app/databank_feature.py")

EXPECTED = {
    ("App", "_clear_preview"): (3, "ceec5781504568791e9f3c6c2c69e4cd0ed74e5579322689b30886c372a3961e", "1aaeb1436819621d6a1417bb86ba4692e23112ef7f7cf1fe349a005a99c47a85"),
    ("App", "_get_databank_focus_date"): (23, "6853936179bc8e9117c781b9b0e090404d5be9c1cd702e48150491b278e59f96", "9cb54e2bce22610fce58ad919cae4d1a72eae40142032907c1b8154cd1ebc815"),
    ("App", "_show_system_data_tab"): (10, "cfe6ed95e42b325d6013af6f50b3bf8cf1dca11873653e4ecae6e43252c49faa", "d5f886d7634c85cd89489e36a6c319161a09e759435528a651a32b671988a63a"),
    ("App", "_hide_system_data_tab"): (6, "8e4ad9d946a60e34887574eaba9a80e23c611ef895c1eab38199efec1fd02a1d", "c530e5df7ce2cf5bfc964a7a5b54930df50f3c2a6e5485c09880517d9455dbf8"),
    ("App", "_system_data_open_close"): (11, "18ffa81613176dfeabfad8ee9e33f9ed321b632777c16725ea708f899141816e", "5bcd26a0bcb4755725b540848d05d250d6b903b4818d5533b546eabe5a07a3e0"),
    ("App", "_system_data_open_history"): (5, "8e368c4d884f48e4a0083befe34d4eea9895936904fdcae7b6316388618e1960", "b66025f9a66f9594ac0a204be928ea91633edb0839615d59f0ee271a42461bea"),
    ("App", "_system_data_open_records"): (5, "ca8b405233b8fb8620ce0538991f8a95e21ef1f3f4cb7086968e20581763cd67", "e40382d15dee10e153bcb35cefc97abfe8ea462b6f1c267102a760b8168f02c9"),
    ("App", "_system_data_print_report"): (5, "d7fc25a697b54ac400c7e7962915f386196bb677fc2692f5ab5d0b06409211ad", "15777c3a45b0c13cad9a6fe5492948032a1eed961d00ec8687eda3796745896a"),
    ("App", "_load_collectors_route_map"): (40, "6419f3957b53f8e510dcda81034e89da25dd361b3992003220515af6f6443ed7", "9d931c981d573d1895180d820a2fe8100b751a9d303048c47b6d5054314f9558"),
    ("App", "_build_databank_collector_defaults_for_date"): (70, "3db01a9c19077366aed5d91cb6ed3bdfac9fe3d95d17abc30294763b25497308", "8d4a38ffc42acb6c3139e9a011d90c2315780181def775dbc8252a7dc79d1559"),
    ("App", "print_databank_close_report"): (235, "10168b6dd965f8aa40c3c3e92efb9c1d29a5b0b229e4be1afbc51650444e6c09", "3a6e8b9a18459c0059ce1f0ef62e98d141899f5e098a04c6fe76305561d4332b"),
    ("App", "open_databank_close_dialog"): (651, "3514a2cc90bde74837e20f87dfd3e29132340e67fee5e494c1fd9ebefbdef0c2", "dfa7142b47784d35fc985efe6b68e9b81ed10d12478496ba6190cf65a2c6d83a"),
    ("App", "on_day_double"): (76, "7dd05eceb54e3d05428af899a71e663022fc8eafdfdff56e80c4b8b2f9367644", "2e25218f16a815938b0378cbcd622c3953c0ce427f9b7f5325e3952e1c48c55e"),
    ("App", "_start_edit"): (71, "b08e6af6d181544d5a43de1d5927fa1583508592243ed2c59efab54eb679c5f3", "65003a589ef532b1e0d54df81e2996e8e1325413633c39b0d093b18459901fa0"),
    ("App", "_import_from_excel_entry"): (42, "677adda5e76b95a3d9a14dbe81f9458a215d4591c43e53540af06a0d2522ad27", "2d54769393eb829d75aa08bca8b90c5d31dd91b42f2919a2e5812d1bfebad6af"),
    ("App", "_import_from_excel_entry_worker"): (397, "d37cb138944f3465847b77cdf0a0aa98c8c1e92c49dfed97864e202f8c6126e8", "8e25b5252def4a369947e2a0d9f6ba3d5c9c92ae1a8ea11c66e522905abeea65"),
    ("App", "_import_encoder_batch"): (420, "b1334b0a1f6774c972755364eeaeeb8b83fe593df7aad5a28e5eb5fe457e453b", "7cc9be4a08de8f8baaf94e5c7348edcc9ffabf6618751b0e02fdde622d327595"),
    ("App", "_import_from_excel_core"): (166, "28d38a4c5ed5551fd8a2ffd58bbe97dfceabb8a262a4ec38410956187bf21280", "df3a7995463b11fc7c1be18613d8d70293e467a6c704d72e0175fc69703bb85c"),
    (None, "import_from_excel_with_reasons"): (149, "c699ee068265c8f472184c88a35c123c810cd19d6eecb9c8424536bb78ea4623", "e3410b97f8f7584d0948426a95d65329da5dbe4d1b593b37c0e679e878d7a607"),
    (None, "_spina_perf_refresh_data_grid"): (205, "ea21f32483991a250fa34f3f5361f5ba136389745a292f7179da68280541dd9a", "f66ff2e45b5a26a90d8befd552118911692cefd817b5297722348f63e13208b3"),
    (None, "_spina_auto_close_one_day"): (43, "94c8ad5a353ed20f60becb11e92481f403888ad0414d841a90171103f66d729e", "adac133f5eb92c03471898510cdd3263a471d4ad2885465be48be780ea9d4f1d"),
    (None, "_spina_run_auto_daily_close"): (79, "ad4b577d81772a0ed97a44a47c917054e4d9d49bf7a27c31fd0e8c927696ddef", "f9f4e603800781d86433f6ae0c31add3483886448ba1bb9e2da90cf2474c073b"),
    (None, "_spina_save_closed_collector_route_copy"): (281, "64175c43544421d2dae6bb7a6b464de5260f31686220fb8ece8d500ed2c78f46", "7b96fa4e267c4d593585453c4725ee19e301f209078b46a922e92f1fa1fadd95"),
}

LEGACY_BUILD_DATA_TAB = (67, "829508e3e2ff97b7d226efabc511e233abe6055dad99ff0cd5805df8d21526a4", "37841745427053231cc253378c11dca7061be76d2b3582fad03f82427e8e5bc9")

APP_METHODS = tuple(name for class_name, name in EXPECTED if class_name == "App")
TOP_LEVEL_FUNCTIONS = tuple(name for class_name, name in EXPECTED if class_name is None)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _roots(tree: ast.Module) -> dict[tuple[str | None, str], ast.AST]:
    result = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result[(None, node.name)] = node
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    result[(node.name, child.name)] = child
    return result


def _final_main_guard(tree: ast.Module) -> ast.If:
    matches = []
    for node in tree.body:
        if not isinstance(node, ast.If):
            continue
        if any(
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == "main"
            for child in ast.walk(node)
        ):
            matches.append(node)
    assert matches, "final main guard not found"
    return matches[-1]


def main() -> None:
    original = SOURCE.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    tree = ast.parse(original)
    roots = _roots(tree)

    extracted = []
    removal_ranges = []
    for key, (expected_lines, raw_hash, ast_hash) in EXPECTED.items():
        node = roots.get(key)
        assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)), key
        start = node.lineno
        end = node.end_lineno or start
        raw = "".join(lines[start - 1:end])
        assert end - start + 1 == expected_lines, (key, end - start + 1)
        assert _sha256(raw) == raw_hash, key
        assert _sha256(ast.dump(node, include_attributes=False)) == ast_hash, key
        extracted.append((start, key, textwrap.dedent(raw) if key[0] else raw))
        removal_ranges.append((start - 1, end))

    legacy = roots.get(("App", "_build_data_tab"))
    assert isinstance(legacy, (ast.FunctionDef, ast.AsyncFunctionDef))
    legacy_start = legacy.lineno
    legacy_end = legacy.end_lineno or legacy_start
    legacy_raw = "".join(lines[legacy_start - 1:legacy_end])
    assert legacy_end - legacy_start + 1 == LEGACY_BUILD_DATA_TAB[0]
    assert _sha256(legacy_raw) == LEGACY_BUILD_DATA_TAB[1]
    assert _sha256(ast.dump(legacy, include_attributes=False)) == LEGACY_BUILD_DATA_TAB[2]
    assert "App._build_data_tab = _spina_v15_build_data_tab" in original
    removal_ranges.append((legacy_start - 1, legacy_end))

    module_parts = [
        "from __future__ import annotations\n\n",
        "def configure_databank_feature_dependencies(namespace):\n",
        "    # The preserved foundation owns shared imports, constants, logging, and DB helpers.\n",
        "    # Refresh this namespace immediately before App startup so moved functions behave unchanged.\n",
        "    for name, value in namespace.items():\n",
        "        if not str(name).startswith('__'):\n",
        "            globals()[name] = value\n",
        "\n\n",
    ]
    for _start, _key, source in sorted(extracted, key=lambda item: item[0]):
        module_parts.append(source.rstrip() + "\n\n\n")
    module_text = "".join(module_parts).rstrip() + "\n"
    ast.parse(module_text)
    MODULE.write_text(module_text, encoding="utf-8")

    cleaned_lines = list(lines)
    for start, end in sorted(removal_ranges, reverse=True):
        del cleaned_lines[start:end]
    cleaned = "".join(cleaned_lines)
    cleaned_tree = ast.parse(cleaned)
    app_node = next(node for node in cleaned_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")

    import_lines = [
        "# Wave 72: complete Data Bank feature/controller extraction.\n",
        "import spina_app.databank_feature as _wave72_databank_feature\n",
    ]
    for name in TOP_LEVEL_FUNCTIONS:
        import_lines.append(f"{name} = _wave72_databank_feature.{name}\n")
    import_lines.append("\n")
    cleaned_lines = cleaned.splitlines(keepends=True)
    cleaned_lines[app_node.lineno - 1:app_node.lineno - 1] = import_lines
    cleaned = "".join(cleaned_lines)

    rebound_tree = ast.parse(cleaned)
    rebound_app = next(node for node in rebound_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    bind_lines = ["\n# Wave 72: bind complete Data Bank App methods before later runtime patches.\n"]
    for name in APP_METHODS:
        bind_lines.append(f"App.{name} = _wave72_databank_feature.{name}\n")
    bind_lines.append("\n")
    cleaned_lines = cleaned.splitlines(keepends=True)
    cleaned_lines[rebound_app.end_lineno:rebound_app.end_lineno] = bind_lines
    cleaned = "".join(cleaned_lines)

    configured_tree = ast.parse(cleaned)
    final_guard = _final_main_guard(configured_tree)
    configure_lines = [
        "# Refresh all application-owned dependencies after runtime patches load.\n",
        "_wave72_databank_feature.configure_databank_feature_dependencies(globals())\n",
        "\n",
    ]
    cleaned_lines = cleaned.splitlines(keepends=True)
    cleaned_lines[final_guard.lineno - 1:final_guard.lineno - 1] = configure_lines
    cleaned = "".join(cleaned_lines)

    verified = ast.parse(cleaned)
    verified_roots = _roots(verified)
    for key in EXPECTED:
        assert key not in verified_roots, key
    assert ("App", "_build_data_tab") not in verified_roots
    assert cleaned.count("import spina_app.databank_feature as _wave72_databank_feature") == 1
    assert cleaned.count("_wave72_databank_feature.configure_databank_feature_dependencies(globals())") == 1
    for name in APP_METHODS:
        assert cleaned.count(f"App.{name} = _wave72_databank_feature.{name}") == 1
    for name in TOP_LEVEL_FUNCTIONS:
        assert cleaned.count(f"{name} = _wave72_databank_feature.{name}") == 1
    assert "App._build_data_tab = _spina_v15_build_data_tab" in cleaned

    SOURCE.write_text(cleaned, encoding="utf-8")
    print(f"Moved {len(EXPECTED)} complete Data Bank functions ({sum(item[0] for item in EXPECTED.values())} lines)")
    print("Removed 67-line legacy _build_data_tab; modern Wave 49 binding retained")


if __name__ == "__main__":
    main()
