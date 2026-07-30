#!/usr/bin/env python3
"""Run the Wave 82 extractor and print transformed source around syntax failures."""
from __future__ import annotations

import ast as _ast

import apply_databank_modularization_wave_82 as extractor

_original_parse = extractor.ast.parse


def _diagnostic_parse(source, filename="<unknown>", mode="exec", **kwargs):
    try:
        return _original_parse(source, filename=filename, mode=mode, **kwargs)
    except SyntaxError as exc:
        if filename == str(extractor.APP_PATH) and "Data Bank feature installer Wave 82" in str(source):
            lines = str(source).splitlines()
            line = int(exc.lineno or 1)
            start = max(1, line - 12)
            end = min(len(lines), line + 12)
            print(f"WAVE82_TRANSFORMED_SYNTAX_CONTEXT {start}-{end}")
            for number in range(start, end + 1):
                print(f"{number:05d}: {lines[number - 1]}")
        raise


extractor.ast.parse = _diagnostic_parse
extractor.main()
