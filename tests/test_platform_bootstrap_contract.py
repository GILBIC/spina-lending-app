from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_windows_installer_requires_portal_url_and_safe_https_boundary() -> None:
    source = _read("spina_pc/install_spina_pc.ps1")

    assert re.search(r"\[Parameter\(Mandatory\s*=\s*\$true\)\]", source)
    assert "PortalUrl" in source
    assert "https" in source.lower()
    assert "localhost" in source.lower()
    assert "127.0.0.1" in source
    assert "--app=" in source
    assert "WScript.Shell" in source


def test_windows_installer_prefers_edge_then_chrome_and_embeds_no_credentials() -> None:
    source = _read("spina_pc/install_spina_pc.ps1")
    lowered = source.lower()

    edge_position = lowered.index("msedge.exe")
    chrome_position = lowered.index("chrome.exe")
    assert edge_position < chrome_position
    assert "password=" not in lowered
    assert "access_token" not in lowered
    assert "refresh_token" not in lowered
    assert "service_role" not in lowered
    assert "postgresql://" not in lowered


def test_windows_uninstaller_removes_only_spina_owned_shortcuts() -> None:
    source = _read("spina_pc/uninstall_spina_pc.ps1")

    assert "SPINA Lending.lnk" in source
    assert "Remove-Item" in source
    assert "*.lnk" not in source
    assert "Recurse" not in source


def test_flutter_bootstrap_analyzes_and_tests_before_optional_android_build() -> None:
    source = _read("gilbic_mobile/tool/bootstrap_all_platforms.ps1")
    lowered = source.lower()

    assert "--platforms=android,ios" in lowered
    analyze = lowered.index("flutter analyze --fatal-infos")
    tests = lowered.index("flutter test")
    build = lowered.index("flutter build apk --debug")
    assert analyze < tests < build
    assert "xcode" in lowered
    assert "windows" in lowered


def test_pc_readme_describes_browser_app_mode_not_a_second_backend() -> None:
    source = _read("spina_pc/README.md").lower()

    assert "progressive web app" in source
    assert "fastapi" in source
    assert "same" in source and "backend" in source
    assert "real money" in source
