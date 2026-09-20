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


def test_delivery_requires_explicit_manual_candidate_endpoints() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "SPINA_API_URL: ${{ inputs.api_url }}" in source
    assert "SPINA_PORTAL_URL: ${{ inputs.portal_url }}" in source
    assert "mvp/cross-platform-four-role" not in source
    assert "\n  push:" not in source
    assert source.count("ref: ${{ github.sha }}") == 3
    assert '--dart-define=GILBIC_API_URL="$SPINA_API_URL"' in source
    assert "--dart-define=GILBIC_API_BASE_URL" not in source
    assert "--dart-define=SPINA_API_BASE_URL" not in source


def test_android_delivery_uses_an_isolated_generated_host() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert 'HOST="$RUNNER_TEMP/spina-android-host"' in source
    assert (
        "flutter create --platforms=android --org com.spinalending "
        '--project-name gilbic_mobile --no-pub "$HOST"'
    ) in source
    assert (
        "flutter create --platforms=android --org com.spinalending "
        "--project-name gilbic_mobile ."
    ) not in source
    assert 'python tools/prepare_android_host.py prepare --host "$HOST"' in source
    assert "flutter pub get --enforce-lockfile" in source
    assert "python tools/verify_android_artifact.py" in source
    assert "SPINA_ANDROID_CERT_SHA256" in source
    assert "Remove temporary signing material\n        if: always()" in source
    assert source.index("Validate Spina Flutter source") < source.index(
        "Generate isolated Android host"
    )


def test_delivery_workflow_has_an_independent_concurrency_group() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "group: spina-artifact-delivery-${{ github.ref }}" in source
    assert "group: spina-delivery-${{ github.ref }}" not in source
