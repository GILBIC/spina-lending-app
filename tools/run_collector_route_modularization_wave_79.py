#!/usr/bin/env python3
"""Run the Wave 79 extractor against post-Wave-44 architecture."""
from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("apply_collector_route_modularization_wave_79.py")
spec = importlib.util.spec_from_file_location("collector_route_wave79_implementation", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("Unable to load the Wave 79 extractor implementation")
implementation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(implementation)

# Wave 44 already removed the legacy App._build_collectors_tab method and supplies
# the active modern builder from spina_app.collector_tab_presentation.
implementation.CLASS_METHODS.discard("_build_collectors_tab")

if __name__ == "__main__":
    implementation.main()
