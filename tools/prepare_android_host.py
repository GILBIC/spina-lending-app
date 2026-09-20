"""Prepare a disposable Flutter Android host without inventing signing identity."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

APPLICATION_ID = "com.spinalending.gilbic_mobile"
ANDROID = "{http://schemas.android.com/apk/res/android}"
SIGNING_NAMES = (
    "SPINA_ANDROID_KEY_ALIAS",
    "SPINA_ANDROID_STORE_PASSWORD",
    "SPINA_ANDROID_KEY_PASSWORD",
    "SPINA_ANDROID_CERT_SHA256",
)


def validate_api_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or any(character.isspace() for character in value)
        or not re.fullmatch(r"[A-Za-z0-9.-]+(?::[0-9]+)?", parsed.netloc)
        or not re.fullmatch(r"[A-Za-z0-9/._~-]*", parsed.path)
    ):
        raise ValueError(
            "An explicit HTTPS URL without credentials or command syntax is required"
        )
    # Parsing the port also rejects malformed/out-of-range values.
    _ = parsed.port
    return value.rstrip("/")


def signing_fingerprint(environment: dict[str, str]) -> str:
    if any(not environment.get(name) for name in SIGNING_NAMES):
        raise ValueError(
            "BLOCKED: owner-provided Android signing inputs are incomplete"
        )
    value = environment["SPINA_ANDROID_CERT_SHA256"].replace(":", "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(
            "BLOCKED: expected Android signing certificate SHA-256 is invalid"
        )
    return value


def stage_signing_material(directory: Path, environment: dict[str, str]) -> Path:
    """Decode supplied material in an exclusive private directory; never log it."""
    signing_fingerprint(environment)
    encoded = environment.get("SPINA_ANDROID_KEYSTORE_BASE64", "")
    if not encoded:
        raise ValueError("BLOCKED: owner-provided Android keystore is missing")
    try:
        data = base64.b64decode(encoded, validate=True)
    except ValueError as error:
        raise ValueError("BLOCKED: Android keystore encoding is invalid") from error
    if not data or len(data) > 10 * 1024 * 1024:
        raise ValueError("BLOCKED: Android keystore is empty or exceeds the size limit")
    directory.mkdir(mode=0o700, parents=False, exist_ok=False)
    path = directory / "release.keystore"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
    except BaseException:
        path.unlink(missing_ok=True)
        directory.rmdir()
        raise
    return path.resolve()


def prepare_host(
    source: Path,
    host: Path,
    *,
    source_sha: str,
    mode: str,
    api_url: str,
    environment: dict[str, str],
) -> dict[str, object]:
    source, host = source.resolve(), host.resolve()
    if host == source or source in host.parents or host in source.parents:
        raise ValueError("Android host must be isolated outside the source checkout")
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha) or mode not in {
        "debug",
        "release",
    }:
        raise ValueError("Exact source SHA and debug/release mode are required")
    api_url = validate_api_url(api_url)
    mobile = source / "gilbic_mobile"
    lock = mobile / "pubspec.lock"
    if not lock.is_file():
        raise ValueError("Committed Flutter dependency lockfile is required")
    manifest_path = host / "android/app/src/main/AndroidManifest.xml"
    gradle_path = host / "android/app/build.gradle.kts"
    gradle = gradle_path.read_text(encoding="utf-8")
    if (
        f'applicationId = "{APPLICATION_ID}"' not in gradle
        or f'namespace = "{APPLICATION_ID}"' not in gradle
        or gradle.count('signingConfig = signingConfigs.getByName("debug")') != 1
        or gradle.count("buildTypes {") != 1
        or gradle.count("release {") != 1
    ):
        raise ValueError("Unexpected generated Android identity or Gradle template")
    expected_certificate = None
    if mode == "release":
        expected_certificate = signing_fingerprint(environment)
        key_path = Path(environment.get("SPINA_ANDROID_KEYSTORE_PATH", ""))
        if not key_path.is_file():
            raise ValueError("BLOCKED: owner-provided Android keystore file is missing")
        signing = """signingConfigs {
        create("spinaRelease") {
            storeFile = file(System.getenv("SPINA_ANDROID_KEYSTORE_PATH") ?: error("Missing keystore"))
            storePassword = System.getenv("SPINA_ANDROID_STORE_PASSWORD") ?: error("Missing store password")
            keyAlias = System.getenv("SPINA_ANDROID_KEY_ALIAS") ?: error("Missing alias")
            keyPassword = System.getenv("SPINA_ANDROID_KEY_PASSWORD") ?: error("Missing key password")
        }
    }

    buildTypes {"""
        gradle = gradle.replace("buildTypes {", signing).replace(
            'signingConfig = signingConfigs.getByName("debug")',
            'signingConfig = signingConfigs.getByName("spinaRelease")',
        )
    else:
        # An internal host cannot accidentally produce a debug-key release.
        gradle = gradle.replace(
            'signingConfig = signingConfigs.getByName("debug")', "signingConfig = null"
        )
    gradle = gradle.replace(
        "release {",
        'release {\n            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")',
    )
    ET.register_namespace("android", ANDROID[1:-1])
    manifest = ET.parse(manifest_path)
    application = manifest.getroot().find("application")
    if application is None:
        raise ValueError("Generated Android manifest is missing the application")
    application.set(f"{ANDROID}label", "Spina")
    if not any(
        permission.get(f"{ANDROID}name") == "android.permission.INTERNET"
        for permission in manifest.getroot().findall("uses-permission")
    ):
        ET.SubElement(
            manifest.getroot(),
            "uses-permission",
            {f"{ANDROID}name": "android.permission.INTERNET"},
        )
    pubspec = (mobile / "pubspec.yaml").read_text(encoding="utf-8")
    version = re.search(r"^version:\s*([0-9.]+)\+([0-9]+)\s*$", pubspec, re.MULTILINE)
    if not version:
        raise ValueError(
            "An explicit Android version name and build number are required"
        )
    metadata: dict[str, object] = {
        "source_sha": source_sha,
        "build_mode": mode,
        "application_id": APPLICATION_ID,
        "api_url": api_url,
        "version_name": version[1],
        "version_code": int(version[2]),
        "pubspec_lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest(),
        "expected_certificate_sha256": expected_certificate,
        "production_ready": False,
    }
    shutil.copytree(mobile / "lib", host / "lib", dirs_exist_ok=True)
    for name in ("pubspec.yaml", "pubspec.lock"):
        shutil.copyfile(mobile / name, host / name)
    gradle_path.write_text(gradle, encoding="utf-8")
    manifest.write(manifest_path, encoding="utf-8", xml_declaration=True)
    (host / "android/app/proguard-rules.pro").write_text(
        "-keep class net.sqlcipher.** { *; }\n", encoding="utf-8"
    )
    with (host / "android/gradle.properties").open("a", encoding="utf-8") as output:
        output.write(
            "\nkotlin.incremental=false\nkotlin.compiler.execution.strategy=in-process\norg.gradle.daemon=false\n"
        )
    assets = host / "android/app/src/main/assets"
    assets.mkdir(exist_ok=True)
    (assets / "spina-build.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    stage = commands.add_parser("stage-signing")
    stage.add_argument("--directory", type=Path, required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--source", type=Path, default=Path.cwd())
    prepare.add_argument("--host", type=Path, required=True)
    prepare.add_argument("--source-sha", required=True)
    prepare.add_argument("--mode", choices=("debug", "release"), required=True)
    prepare.add_argument("--api-url", required=True)
    args = parser.parse_args()
    try:
        if args.command == "stage-signing":
            runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve()
            if args.directory.resolve().parent != runner_temp:
                raise ValueError(
                    "Signing material must stay directly under RUNNER_TEMP"
                )
            path = stage_signing_material(args.directory, dict(os.environ))
            with Path(os.environ["GITHUB_ENV"]).open("a", encoding="utf-8") as output:
                output.write(f"SPINA_ANDROID_KEYSTORE_PATH={path}\n")
            print("Owner-provided signing material staged in a private temporary file")
            return
        actual_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=args.source, text=True
        ).strip()
        if actual_sha != args.source_sha:
            raise ValueError("Requested Android source SHA differs from the checkout")
        if subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=args.source,
            text=True,
        ).strip():
            raise ValueError(
                "Exact-commit Android packaging requires a clean source checkout"
            )
        result = prepare_host(
            args.source,
            args.host,
            source_sha=args.source_sha,
            mode=args.mode,
            api_url=args.api_url,
            environment=dict(os.environ),
        )
        print(json.dumps(result, indent=2))
    except (ValueError, OSError) as error:
        parser.exit(2, f"Android preparation failed: {error}\n")


if __name__ == "__main__":
    main()
