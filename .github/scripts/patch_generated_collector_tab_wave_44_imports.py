from __future__ import annotations

from pathlib import Path

TEST = Path('tools/test_collector_tab_presentation_wave_44.py')
WORKFLOW = Path('.github/workflows/collector-tab-presentation-wave-44.yml')


def patch_test() -> None:
    text = TEST.read_text(encoding='utf-8')
    old = """import re
from pathlib import Path

DESKTOP = Path('OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py')
MODULE_PATH = Path('spina_app/collector_tab_presentation.py')
"""
    new = """import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DESKTOP = ROOT / 'OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py'
MODULE_PATH = ROOT / 'spina_app/collector_tab_presentation.py'
"""
    if new in text:
        return
    if old not in text:
        raise SystemExit('Wave 44 generated test import block not found')
    TEST.write_text(text.replace(old, new, 1), encoding='utf-8')


def patch_workflow() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    old = 'run: python tools/test_collector_tab_presentation_wave_44.py'
    new = 'run: python -m tools.test_collector_tab_presentation_wave_44'
    if new in text:
        return
    if old not in text:
        raise SystemExit('Wave 44 generated workflow regression command not found')
    WORKFLOW.write_text(text.replace(old, new, 1), encoding='utf-8')


def main() -> None:
    patch_test()
    patch_workflow()
    print('Wave 44 generated test and workflow import paths patched.')


if __name__ == '__main__':
    main()
