from __future__ import annotations

import base64
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from tools.prepare_android_host import (
    prepare_host,
    stage_signing_material,
    validate_api_url,
)
from tools.verify_android_artifact import inspect_artifact

ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40
CERTIFICATE = "b" * 64
API_URL = "https://spina-test.example"


@pytest.fixture
def generated_host(tmp_path):
    source = tmp_path / "source"
    mobile = source / "gilbic_mobile"
    (mobile / "lib").mkdir(parents=True)
    (mobile / "lib/main.dart").write_text("void main() {}", encoding="utf-8")
    (mobile / "pubspec.yaml").write_text(
        "name: gilbic_mobile\nversion: 0.4.0+4\n", encoding="utf-8"
    )
    (mobile / "pubspec.lock").write_text(
        "# synthetic locked dependencies\n", encoding="utf-8"
    )
    host = tmp_path / "host"
    (host / "android/app/src/main").mkdir(parents=True)
    (host / "android/app/build.gradle.kts").write_text(
        """android {
    namespace = "com.spinalending.gilbic_mobile"
    defaultConfig { applicationId = "com.spinalending.gilbic_mobile" }
    buildTypes {
        release { signingConfig = signingConfigs.getByName("debug") }
    }
}""",
        encoding="utf-8",
    )
    (host / "android/app/src/main/AndroidManifest.xml").write_text(
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android">'
        '<application android:label="gilbic_mobile" /></manifest>',
        encoding="utf-8",
    )
    return source, host


def prepare(source, host, *, mode="debug", environment=None):
    return prepare_host(
        source,
        host,
        source_sha=SHA,
        mode=mode,
        api_url=API_URL,
        environment=environment or {},
    )


def signing_inputs():
    return {
        "SPINA_ANDROID_KEY_ALIAS": "synthetic-alias",
        "SPINA_ANDROID_STORE_PASSWORD": "synthetic-store-password",
        "SPINA_ANDROID_KEY_PASSWORD": "synthetic-key-password",
        "SPINA_ANDROID_CERT_SHA256": CERTIFICATE,
        "SPINA_ANDROID_KEYSTORE_BASE64": base64.b64encode(
            b"synthetic owner-supplied fixture"
        ).decode(),
    }


def test_ci_and_delivery_share_the_same_android_application_identity() -> None:
    workflows = [
        (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
        for name in ("spina-ci.yml", "spina-delivery.yml")
    ]
    identities = [re.findall(r"--org ([a-z.]+)", source) for source in workflows]
    assert identities == [["com.spinalending"], ["com.spinalending"]]


def test_prepared_host_preserves_lock_and_carries_network_native_rules_and_provenance(
    generated_host,
):
    source, host = generated_host
    metadata = prepare(source, host)
    android = "{http://schemas.android.com/apk/res/android}"
    manifest = ET.parse(host / "android/app/src/main/AndroidManifest.xml")
    assert manifest.getroot().find("application").get(android + "label") == "Spina"
    assert [
        row.get(android + "name")
        for row in manifest.getroot().findall("uses-permission")
    ] == ["android.permission.INTERNET"]
    assert (host / "pubspec.lock").read_bytes() == (
        source / "gilbic_mobile/pubspec.lock"
    ).read_bytes()
    assert (host / "lib/main.dart").read_text(encoding="utf-8") == "void main() {}"
    assert (host / "android/app/proguard-rules.pro").read_text(
        encoding="utf-8"
    ) == "-keep class net.sqlcipher.** { *; }\n"
    gradle = (host / "android/app/build.gradle.kts").read_text(encoding="utf-8")
    assert (
        'proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")'
        in gradle
    )
    assert 'signingConfigs.getByName("debug")' not in gradle
    assert "signingConfig = null" in gradle
    assert metadata["source_sha"] == SHA
    assert metadata["application_id"] == "com.spinalending.gilbic_mobile"
    assert metadata["version_code"] == 4
    assert metadata["production_ready"] is False
    assert (
        json.loads(
            (host / "android/app/src/main/assets/spina-build.json").read_text(
                encoding="utf-8"
            )
        )
        == metadata
    )


def test_release_without_owner_material_is_blocked_before_modifying_host(
    generated_host,
):
    source, host = generated_host
    original = (host / "android/app/build.gradle.kts").read_bytes()
    with pytest.raises(ValueError, match="BLOCKED.*signing inputs"):
        prepare(source, host, mode="release")
    assert (host / "android/app/build.gradle.kts").read_bytes() == original
    assert not (host / "android/app/src/main/assets").exists()


def test_release_uses_private_environment_references_without_copying_secrets(
    generated_host, tmp_path
):
    source, host = generated_host
    environment = signing_inputs()
    path = stage_signing_material(tmp_path / "private-signing", environment)
    environment["SPINA_ANDROID_KEYSTORE_PATH"] = str(path)
    metadata = prepare(source, host, mode="release", environment=environment)
    gradle = (host / "android/app/build.gradle.kts").read_text(encoding="utf-8")
    assert 'signingConfigs.getByName("spinaRelease")' in gradle
    assert 'signingConfigs.getByName("debug")' not in gradle
    assert 'System.getenv("SPINA_ANDROID_STORE_PASSWORD")' in gradle
    assert metadata["expected_certificate_sha256"] == CERTIFICATE
    for file in host.rglob("*"):
        if file.is_file():
            content = file.read_bytes()
            assert b"synthetic-store-password" not in content
            assert b"synthetic-key-password" not in content
            assert b"synthetic owner-supplied fixture" not in content
    assert path.read_bytes() == b"synthetic owner-supplied fixture"


def test_private_signing_staging_refuses_reuse_and_missing_inputs(tmp_path):
    target = tmp_path / "private"
    with pytest.raises(ValueError, match="BLOCKED"):
        stage_signing_material(target, {})
    assert not target.exists()
    stage_signing_material(target, signing_inputs())
    with pytest.raises(FileExistsError):
        stage_signing_material(target, signing_inputs())


@pytest.mark.parametrize(
    "url",
    [
        "http://test.example",
        "https://user:password@test.example",
        "https://test.example/?token=abc",
        "https://test.example/#fragment",
        'https://test.example/"&calc',
        "https://test.example/%PATH%",
    ],
)
def test_candidate_urls_cannot_embed_secrets_or_installer_command_syntax(url):
    with pytest.raises(ValueError):
        validate_api_url(url)


def artifact_case(tmp_path, *, mode="release", metadata_changes=None, missing=None):
    metadata = {
        "source_sha": SHA,
        "build_mode": mode,
        "application_id": "com.spinalending.gilbic_mobile",
        "api_url": API_URL,
        "version_name": "0.4.0",
        "version_code": 4,
        "pubspec_lock_sha256": "c" * 64,
        "expected_certificate_sha256": CERTIFICATE if mode == "release" else None,
        "production_ready": False,
        **(metadata_changes or {}),
    }
    apk = tmp_path / "synthetic.apk"
    with zipfile.ZipFile(apk, "w") as archive:
        for name in (
            "AndroidManifest.xml",
            "classes.dex",
            "lib/arm64-v8a/libflutter.so",
            "lib/x86_64/libflutter.so",
            "lib/arm64-v8a/libsqlcipher.so",
            "lib/x86_64/libsqlcipher.so",
        ):
            if name != missing:
                archive.writestr(name, b"synthetic")
        archive.writestr("assets/spina-build.json", json.dumps(metadata))
    badging = "package: name='com.spinalending.gilbic_mobile' versionCode='4' versionName='0.4.0' platformBuildVersionName='16'\nuses-permission: name='android.permission.INTERNET'\n"
    if mode == "debug":
        badging += "application-debuggable\n"
    certificates = f"Verifies\nNumber of signers: 1\nSigner #1 certificate DN: CN=Spina Synthetic Test\nSigner #1 certificate SHA-256 digest: {CERTIFICATE}\n"
    return apk, {
        "badging": badging,
        "certificates": certificates,
        "expected_sha": SHA,
        "expected_mode": mode,
        "expected_api_url": API_URL,
        "expected_certificate": CERTIFICATE,
    }


def test_valid_signed_candidate_keeps_device_and_activation_gates_open(tmp_path):
    apk, arguments = artifact_case(tmp_path)
    result = inspect_artifact(apk, **arguments)
    assert result["status"] == "signed_candidate"
    assert result["production_ready"] is False
    assert result["certificate_sha256"] == CERTIFICATE
    assert result["apk_bytes"] == apk.stat().st_size


def test_internal_debug_artifact_is_never_labelled_a_production_release(tmp_path):
    apk, arguments = artifact_case(tmp_path, mode="debug")
    arguments["certificates"] = arguments["certificates"].replace(
        "Spina Synthetic Test", "Android Debug"
    )
    result = inspect_artifact(apk, **arguments)
    assert result["status"] == "internal_test_only"
    assert result["production_ready"] is False


def test_sdk37_scheme_specific_signer_output_is_verified(tmp_path):
    apk, arguments = artifact_case(tmp_path)
    arguments["certificates"] = arguments["certificates"].replace(
        "Signer #1 certificate", "V2 Signer: certificate"
    )
    assert inspect_artifact(apk, **arguments)["certificate_sha256"] == CERTIFICATE


@pytest.mark.parametrize(
    "change,error",
    [
        ("debug_certificate", "debug certificate"),
        ("wrong_certificate", "expected owner"),
        ("missing_expected_certificate", "BLOCKED"),
        ("debuggable", "debuggable"),
        ("no_internet", "INTERNET"),
        ("wrong_version", "package/version"),
        ("wrong_sha", "provenance"),
    ],
)
def test_artifact_rejects_untrusted_release_evidence(tmp_path, change, error):
    apk, arguments = artifact_case(tmp_path)
    if change == "debug_certificate":
        arguments["certificates"] = arguments["certificates"].replace(
            "Spina Synthetic Test", "Android Debug"
        )
    elif change == "wrong_certificate":
        arguments["expected_certificate"] = "d" * 64
    elif change == "missing_expected_certificate":
        arguments["expected_certificate"] = None
    elif change == "debuggable":
        arguments["badging"] += "application-debuggable\n"
    elif change == "no_internet":
        arguments["badging"] = arguments["badging"].replace(
            "android.permission.INTERNET", "another.permission"
        )
    elif change == "wrong_version":
        arguments["badging"] = arguments["badging"].replace(
            "versionCode='4'", "versionCode='5'"
        )
    elif change == "wrong_sha":
        arguments["expected_sha"] = "d" * 40
    with pytest.raises(ValueError, match=error):
        inspect_artifact(apk, **arguments)


def test_artifact_requires_sqlcipher_on_each_supported_abi(tmp_path):
    apk, arguments = artifact_case(tmp_path, missing="lib/x86_64/libsqlcipher.so")
    with pytest.raises(ValueError, match="native libraries"):
        inspect_artifact(apk, **arguments)
