from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "spina-delivery.yml"


def test_delivery_workflow_packages_active_platforms() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "name: Spina Delivery" in source
    assert "workflow_dispatch:" in source
    assert "Spina-Web" in source
    assert "Spina-Windows" in source
    assert "Spina-Android" in source
    assert source.count("actions/upload-artifact@v4") >= 3
    assert "flutter build apk" in source
    assert "spina_pc" in source
    assert "npm run build" in source


def test_delivery_workflow_keeps_ios_paused() -> None:
    source = WORKFLOW.read_text(encoding="utf-8").lower()

    assert "macos-latest" not in source
    assert "flutter build ios" not in source
    assert "xcodebuild" not in source


def test_android_delivery_is_not_a_debug_build() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "flutter build apk --release" in source
    assert "flutter build apk --debug" not in source
