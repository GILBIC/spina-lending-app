from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "databank_feature.py"

EXPECTED_AST = {
    "_clear_preview": "1aaeb1436819621d6a1417bb86ba4692e23112ef7f7cf1fe349a005a99c47a85",
    "_get_databank_focus_date": "9cb54e2bce22610fce58ad919cae4d1a72eae40142032907c1b8154cd1ebc815",
    "_show_system_data_tab": "d5f886d7634c85cd89489e36a6c319161a09e759435528a651a32b671988a63a",
    "_hide_system_data_tab": "c530e5df7ce2cf5bfc964a7a5b54930df50f3c2a6e5485c09880517d9455dbf8",
    "_system_data_open_close": "5bcd26a0bcb4755725b540848d05d250d6b903b4818d5533b546eabe5a07a3e0",
    "_system_data_open_history": "b66025f9a66f9594ac0a204be928ea91633edb0839615d59f0ee271a42461bea",
    "_system_data_open_records": "e40382d15dee10e153bcb35cefc97abfe8ea462b6f1c267102a760b8168f02c9",
    "_system_data_print_report": "15777c3a45b0c13cad9a6fe5492948032a1eed961d00ec8687eda3796745896a",
    "_load_collectors_route_map": "9d931c981d573d1895180d820a2fe8100b751a9d303048c47b6d5054314f9558",
    "_build_databank_collector_defaults_for_date": "8d4a38ffc42acb6c3139e9a011d90c2315780181def775dbc8252a7dc79d1559",
    "print_databank_close_report": "3a6e8b9a18459c0059ce1f0ef62e98d141899f5e098a04c6fe76305561d4332b",
    "open_databank_close_dialog": "dfa7142b47784d35fc985efe6b68e9b81ed10d12478496ba6190cf65a2c6d83a",
    "on_day_double": "2e25218f16a815938b0378cbcd622c3953c0ce427f9b7f5325e3952e1c48c55e",
    "_start_edit": "65003a589ef532b1e0d54df81e2996e8e1325413633c39b0d093b18459901fa0",
    "_import_from_excel_entry": "2d54769393eb829d75aa08bca8b90c5d31dd91b42f2919a2e5812d1bfebad6af",
    "_import_from_excel_entry_worker": "8e25b5252def4a369947e2a0d9f6ba3d5c9c92ae1a8ea11c66e522905abeea65",
    "_import_encoder_batch": "7cc9be4a08de8f8baaf94e5c7348edcc9ffabf6618751b0e02fdde622d327595",
    "_import_from_excel_core": "df3a7995463b11fc7c1be18613d8d70293e467a6c704d72e0175fc69703bb85c",
    "import_from_excel_with_reasons": "e3410b97f8f7584d0948426a95d65329da5dbe4d1b593b37c0e679e878d7a607",
    "_spina_perf_refresh_data_grid": "f66ff2e45b5a26a90d8befd552118911692cefd817b5297722348f63e13208b3",
    "_spina_auto_close_one_day": "adac133f5eb92c03471898510cdd3263a471d4ad2885465be48be780ea9d4f1d",
    "_spina_run_auto_daily_close": "f9f4e603800781d86433f6ae0c31add3483886448ba1bb9e2da90cf2474c073b",
    "_spina_save_closed_collector_route_copy": "7b96fa4e267c4d593585453c4725ee19e301f209078b46a922e92f1fa1fadd95",
}

APP_METHODS = {
    "_clear_preview",
    "_get_databank_focus_date",
    "_show_system_data_tab",
    "_hide_system_data_tab",
    "_system_data_open_close",
    "_system_data_open_history",
    "_system_data_open_records",
    "_system_data_print_report",
    "_load_collectors_route_map",
    "_build_databank_collector_defaults_for_date",
    "print_databank_close_report",
    "open_databank_close_dialog",
    "on_day_double",
    "_start_edit",
    "_import_from_excel_entry",
    "_import_from_excel_entry_worker",
    "_import_encoder_batch",
    "_import_from_excel_core",
}
TOP_LEVEL_FUNCTIONS = set(EXPECTED_AST) - APP_METHODS


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _top_functions(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def main() -> None:
    source_text = SOURCE.read_text(encoding="utf-8")
    source_tree = ast.parse(source_text)
    module_text = MODULE.read_text(encoding="utf-8")
    module_tree = ast.parse(module_text)

    app = next(node for node in source_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    app_methods = {
        node.name for node in app.body if isinstance(node, ast.FunctionDef)
    }
    source_top = _top_functions(source_tree)
    module_top = _top_functions(module_tree)

    assert not (APP_METHODS & app_methods), sorted(APP_METHODS & app_methods)
    assert "_build_data_tab" not in app_methods
    assert not (TOP_LEVEL_FUNCTIONS & set(source_top)), sorted(TOP_LEVEL_FUNCTIONS & set(source_top))

    assert set(EXPECTED_AST).issubset(module_top), sorted(set(EXPECTED_AST) - set(module_top))
    for name, expected_hash in EXPECTED_AST.items():
        actual = _sha256(ast.dump(module_top[name], include_attributes=False))
        assert actual == expected_hash, (name, actual, expected_hash)

    assert "def configure_databank_feature_dependencies(namespace):" in module_text
    assert source_text.count("import spina_app.databank_feature as _wave72_databank_feature") == 1
    assert source_text.count("_wave72_databank_feature.configure_databank_feature_dependencies(globals())") == 1

    for name in APP_METHODS:
        binding = f"App.{name} = _wave72_databank_feature.{name}"
        assert source_text.count(binding) == 1, binding
    for name in TOP_LEVEL_FUNCTIONS:
        binding = f"{name} = _wave72_databank_feature.{name}"
        assert source_text.count(binding) == 1, binding

    modern_builder = "App._build_data_tab = _spina_v15_build_data_tab"
    assert source_text.count(modern_builder) == 1

    configure_pos = source_text.index("_wave72_databank_feature.configure_databank_feature_dependencies(globals())")
    final_main_pos = source_text.rindex("if __name__ == '__main__':")
    assert configure_pos < final_main_pos

    print("Wave 72 Data Bank feature structural regression passed")
    print(f"Protected complete functions: {len(EXPECTED_AST)}")


if __name__ == "__main__":
    main()
