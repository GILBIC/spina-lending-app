#!/usr/bin/env python3
"""Run the Wave 82 extractor with the exact Wave 72 class-marker handoff."""
from __future__ import annotations

import apply_databank_modularization_wave_82 as extractor

_original_replace_between = extractor._replace_between


def _replace_between_without_duplicate_class(text, start_marker, next_marker, replacement):
    if (
        start_marker == "# Wave 72: complete Data Bank feature/controller extraction."
        and next_marker == "class App:"
        and replacement == "class App:"
    ):
        replacement = ""
    return _original_replace_between(text, start_marker, next_marker, replacement)


extractor._replace_between = _replace_between_without_duplicate_class
extractor.main()
