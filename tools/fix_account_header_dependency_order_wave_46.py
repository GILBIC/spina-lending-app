from __future__ import annotations

from pathlib import Path

DESKTOP = Path(__file__).resolve().parents[1] / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
CONFIGURE = "_wave46_configure_account_header_dependencies(globals())"
ORIGINAL = '_spina_v32_orig_build_header = getattr(App, "_build_header", None)'
BINDING = "App._build_header = _spina_v32_build_header"


def main() -> None:
    with DESKTOP.open("r", encoding="utf-8", newline="") as handle:
        lines = handle.readlines()

    lines = [line for line in lines if line.strip() != CONFIGURE]

    original_index = next((i for i, line in enumerate(lines) if line.strip() == ORIGINAL), -1)
    if original_index < 0:
        raise AssertionError("Original header capture was not found")

    binding_index = next(
        (i for i in range(original_index + 1, len(lines)) if lines[i].strip() == BINDING),
        -1,
    )
    if binding_index < 0:
        raise AssertionError("Final App._build_header binding was not found after original capture")

    binding_line = lines[binding_index]
    indent = binding_line[: len(binding_line) - len(binding_line.lstrip())]
    newline = "\r\n" if binding_line.endswith("\r\n") else "\n"
    lines.insert(binding_index, f"{indent}{CONFIGURE}{newline}")

    rendered = "".join(lines)
    assert rendered.count(CONFIGURE) == 1
    assert rendered.index(ORIGINAL) < rendered.index(CONFIGURE) < rendered.index(BINDING)

    with DESKTOP.open("w", encoding="utf-8", newline="") as handle:
        handle.write(rendered)

    print("Wave 46 account-header dependency order repaired.")


if __name__ == "__main__":
    main()
