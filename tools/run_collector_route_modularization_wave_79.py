#!/usr/bin/env python3
"""Run the Wave 79 extractor against post-Wave-44 architecture."""
from __future__ import annotations

from tools import apply_collector_route_modularization_wave_79 as implementation

# Wave 44 already removed the legacy App._build_collectors_tab method and supplies
# the active modern builder from spina_app.collector_tab_presentation.
implementation.CLASS_METHODS.discard("_build_collectors_tab")

if __name__ == "__main__":
    implementation.main()
