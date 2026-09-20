"""Verify APK identity, native contents, provenance and real signing evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import zipfile
from pathlib import Path

APPLICATION_ID = "com.spinalending.gilbic_mobile"


def inspect_artifact(
    apk: Path,
    *,
    badging: str,
    certificates: str,
    expected_sha: str,
    expected_mode: str,
    expected_api_url: str,
    expected_certificate: str | None = None,
) -> dict[str, object]:
    if not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
        raise ValueError("Exact source SHA is required")
    if expected_mode not in {"debug", "release"}:
        raise ValueError("Explicit debug/release mode is required")
    with zipfile.ZipFile(apk) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("APK contains duplicate archive entries")
        required = {
            "AndroidManifest.xml",
            "classes.dex",
            "assets/spina-build.json",
            "lib/arm64-v8a/libflutter.so",
            "lib/x86_64/libflutter.so",
            "lib/arm64-v8a/libsqlcipher.so",
            "lib/x86_64/libsqlcipher.so",
        }
        if not required.issubset(names):
            raise ValueError(
                "APK is missing its manifest, provenance or required native libraries"
            )
        metadata = json.loads(archive.read("assets/spina-build.json"))
    if not isinstance(metadata, dict) or any(
        metadata.get(key) != value
        for key, value in {
            "source_sha": expected_sha,
            "build_mode": expected_mode,
            "application_id": APPLICATION_ID,
            "api_url": expected_api_url.rstrip("/"),
            "production_ready": False,
        }.items()
    ):
        raise ValueError("APK provenance does not match this candidate")
    if not re.fullmatch(r"[0-9a-f]{64}", str(metadata.get("pubspec_lock_sha256", ""))):
        raise ValueError("APK dependency lock provenance is missing")
    package = re.search(
        r"^package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'",
        badging,
        re.MULTILINE,
    )
    if not package or (
        package[1] != APPLICATION_ID
        or package[2] != str(metadata.get("version_code"))
        or package[3] != metadata.get("version_name")
    ):
        raise ValueError(
            "APK manifest package/version does not match candidate provenance"
        )
    if "uses-permission: name='android.permission.INTERNET'" not in badging:
        raise ValueError("APK lacks INTERNET permission")
    debuggable = bool(re.search(r"^application-debuggable\s*$", badging, re.MULTILINE))
    if debuggable != (expected_mode == "debug"):
        raise ValueError("APK debuggable flag does not match its claimed build mode")
    signer_label = r"(?:Signer #\d+|V\d+(?:\.\d+)? Signer(?: #\d+)?:)"
    digests = re.findall(
        rf"^{signer_label} certificate SHA-256 digest: ([0-9a-fA-F:]+)\s*$",
        certificates,
        re.MULTILINE,
    )
    identities = re.findall(
        rf"^{signer_label} certificate DN: (.+)$", certificates, re.MULTILINE
    )
    fingerprints = {digest.replace(":", "").lower() for digest in digests}
    identities = sorted({identity.strip() for identity in identities})
    if (
        re.findall(r"^Number of signers: (\d+)\s*$", certificates, re.MULTILINE)
        != ["1"]
        or len(fingerprints) != 1
        or len(identities) != 1
    ):
        raise ValueError("Exactly one verified APK signer is required")
    fingerprint = next(iter(fingerprints))
    if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise ValueError("APK signer fingerprint is invalid")
    if expected_mode == "release":
        expected = (expected_certificate or "").replace(":", "").lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError(
                "BLOCKED: expected production signing certificate is required"
            )
        if "android debug" in identities[0].lower():
            raise ValueError("A debug certificate cannot sign a production release")
        if (
            fingerprint != expected
            or metadata.get("expected_certificate_sha256") != expected
        ):
            raise ValueError("APK signer is not the expected owner release identity")
    return {
        **metadata,
        "apk_sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
        "apk_bytes": apk.stat().st_size,
        "certificate_sha256": fingerprint,
        "debuggable": debuggable,
        "status": "signed_candidate"
        if expected_mode == "release"
        else "internal_test_only",
        "production_ready": False,
        "remaining": [
            "Exact-candidate device acceptance",
            "Production activation approval",
        ],
    }


def android_tool(name: str) -> Path:
    root = Path(
        os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME") or ""
    )
    suffix = (
        ".bat"
        if os.name == "nt" and name == "apksigner"
        else ".exe"
        if os.name == "nt"
        else ""
    )
    paths = list((root / "build-tools").glob(f"*/{name}{suffix}"))
    if not paths:
        raise ValueError(f"Android SDK {name} is required for artifact verification")
    return max(
        paths,
        key=lambda path: tuple(
            int(part) for part in re.findall(r"\d+", path.parent.name)
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--mode", choices=("debug", "release"), required=True)
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        badging = subprocess.check_output(
            [str(android_tool("aapt")), "dump", "badging", str(args.apk)], text=True
        )
        certificates = subprocess.check_output(
            [
                str(android_tool("apksigner")),
                "verify",
                "--verbose",
                "--print-certs",
                str(args.apk),
            ],
            text=True,
        )
        result = inspect_artifact(
            args.apk,
            badging=badging,
            certificates=certificates,
            expected_sha=args.source_sha,
            expected_mode=args.mode,
            expected_api_url=args.api_url,
            expected_certificate=os.environ.get("SPINA_ANDROID_CERT_SHA256"),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
    except (
        ValueError,
        OSError,
        subprocess.CalledProcessError,
        zipfile.BadZipFile,
    ) as error:
        parser.exit(2, f"Android verification failed: {error}\n")


if __name__ == "__main__":
    main()
