"""Artifact-only Linux port of the reviewed isolated debug host builder."""

import argparse
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
SOURCE_SHA = "83d66b31cfaff67783b03353fa16cf2dee509cd2"
REPOSITORY = "GILBIC/spina-lending-app"
REF = "refs/heads/acceptance/s04-native-83-20261013"
FLUTTER_VERSION = "3.44.7"
BUILDER_HASH = "a731a8d36476584d970f342e8ccedbe14a787e77bcf251d2bdf850c94c3febdc"
BRANCH_FILES = {
    ".github/workflows/spina-ci.yml",
    ".native-acceptance/build_linux.py",
    ".native-acceptance/reviewed_builder.py",
}
SOURCE_OBJECTS = {
    "gilbic_mobile/lib": "c0889952fa45169d9941aa21f2e686e85a986258",
    "gilbic_mobile/pubspec.yaml": "7e9f3da20de954568589af40a5e126f573fe9b77",
    "gilbic_mobile/pubspec.lock": "e07990fb328db2ec33c516fdd1689c19d76750de",
}
GIB = 1024**3


def validate_delta(changed):
    if set(changed) != BRANCH_FILES:
        raise ValueError(
            "Acceptance branch must differ only in the exact three build files"
        )


def validate_context(environment):
    expected = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": REF,
        "GITHUB_REPOSITORY": REPOSITORY,
    }
    if any(environment.get(key) != value for key, value in expected.items()):
        raise ValueError(
            "Only the explicit isolated manual workflow context is allowed"
        )
    if not re.fullmatch(r"[0-9a-f]{40}", environment.get("GITHUB_SHA", "")):
        raise ValueError("Exact workflow commit is required")
    if not all(
        environment.get(key, "").isdigit()
        for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")
    ):
        raise ValueError("Exact workflow run identity is required")


def child_environment(parent, root):
    result = {
        key: value
        for key, value in parent.items()
        if key
        in {"PATH", "JAVA_HOME", "ANDROID_HOME", "ANDROID_SDK_ROOT", "LANG", "LC_ALL"}
    }
    result.update(
        HOME=str(root / "home"),
        TMPDIR=str(root / "tmp"),
        PUB_CACHE=str(root / "pub-cache"),
        GRADLE_USER_HOME=str(root / "gradle"),
        ANDROID_USER_HOME=str(root / "home/.android"),
        CI="true",
        FLUTTER_SUPPRESS_ANALYTICS="true",
        PYTHONDONTWRITEBYTECODE="1",
    )
    return result


def validate_output(output, runner_temp):
    if output != runner_temp / "s04-native-debug-output" or not runner_temp.is_dir():
        raise ValueError("Output must be the exact runner-owned temporary directory")
    if output.exists():
        raise FileExistsError("Output already exists; refusing overwrite or cleanup")
    for path in (output, *output.parents):
        if path.is_symlink():
            raise ValueError("Symbolic output paths are forbidden")


def build_command(flutter):
    return [
        str(flutter),
        "build",
        "apk",
        "--debug",
        "--no-pub",
        "--target-platform=android-arm64",
        "--dart-define=GILBIC_API_URL=http://127.0.0.1:18080",
    ]


def verify_debug_signer(certificates):
    # Called only after apksigner verify exits zero. Recognize the observed SDK
    # 37 prefix and the legacy format, without ignoring extra certificate rows.
    lines = certificates.splitlines()
    counts = [line for line in lines if "Number of signers:" in line]
    subjects = [line for line in lines if "certificate DN:" in line]
    digests = [line for line in lines if "certificate SHA-256 digest:" in line]
    if counts != ["Number of signers: 1"] or len(digests) != 1 or len(subjects) != 1:
        raise ValueError("Exactly one fresh Android debug signer required")
    subject = re.fullmatch(r"(Signer #1|V2 Signer:) certificate DN: (.+)", subjects[0])
    digest = re.fullmatch(
        r"(Signer #1|V2 Signer:) certificate SHA-256 digest: ([0-9a-fA-F]{64})",
        digests[0],
    )
    if (
        not subject
        or not digest
        or subject[1] != digest[1]
        or [
            part.strip()
            for part in subject[2].split(",")
            if part.strip().startswith("CN=")
        ]
        != ["CN=Android Debug"]
    ):
        raise ValueError("Exactly one fresh Android debug signer required")
    return digest[2].lower()


def resource_snapshot(directory):
    match = re.search(
        r"^MemAvailable:\s+(\d+)\s+kB$", Path("/proc/meminfo").read_text(), re.MULTILINE
    )
    if not match:
        raise ValueError("Linux available memory cannot be read")
    return {
        "free_ram_bytes": int(match[1]) * 1024,
        "free_disk_bytes": shutil.disk_usage(directory).free,
    }


class Runner:
    def __init__(self, directory, environment, builder):
        self.directory, self.environment, self.builder = directory, environment, builder
        self.index = 0
        self.events = (directory / "events.jsonl").open("x", encoding="utf-8")

    def emit(self, event, **fields):
        self.events.write(
            json.dumps(
                {
                    "utc": datetime.now(timezone.utc).isoformat(),
                    "event": event,
                    **fields,
                }
            )
            + "\n"
        )
        self.events.flush()

    def run(self, name, argv, *, cwd, timeout):
        sample = resource_snapshot(self.directory)
        self.emit("preflight", phase=name, **sample)
        self.builder.check_resource_floor(sample, starting=True)
        self.index += 1
        path = self.directory / f"{self.index:02d}-{name}.log"
        started = time.monotonic()
        with path.open("xb") as stream:
            self.emit(
                "command_start",
                phase=name,
                argv=[str(item) for item in argv],
                timeout_seconds=timeout,
            )
            process = subprocess.Popen(
                [str(item) for item in argv],
                cwd=cwd,
                env=self.environment,
                stdin=subprocess.DEVNULL,
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                while True:
                    try:
                        result = process.wait(timeout=5)
                        break
                    except subprocess.TimeoutExpired:
                        sample = resource_snapshot(self.directory)
                        self.emit("resources", phase=name, **sample)
                        self.builder.check_resource_floor(sample, starting=False)
                        if time.monotonic() - started > timeout:
                            raise TimeoutError(
                                "Finite build phase deadline exceeded"
                            ) from None
            except BaseException:
                if process.poll() is None:
                    # Only this freshly created process group in the disposable runner.
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=10)
                self.emit("command_aborted", phase=name)
                raise
        self.emit(
            "command_complete",
            phase=name,
            exit_code=result,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )
        if result:
            raise RuntimeError(
                f"Build phase {name} failed; inspect retained bounded log"
            )
        return path.read_text(encoding="utf-8", errors="replace")


def verify_checkout(runner, source, expected_head, phase):
    head = runner.run(
        phase + "-head", ["git", "rev-parse", "HEAD"], cwd=source, timeout=30
    ).strip()
    dirty = runner.run(
        phase + "-status",
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=source,
        timeout=30,
    )
    if head != expected_head or dirty.strip():
        raise ValueError("Workflow checkout must be exact and clean")
    runner.run(
        phase + "-ancestry",
        ["git", "merge-base", "--is-ancestor", SOURCE_SHA, "HEAD"],
        cwd=source,
        timeout=30,
    )
    changed = runner.run(
        phase + "-delta",
        ["git", "diff", "--name-only", "--no-renames", SOURCE_SHA, "HEAD"],
        cwd=source,
        timeout=30,
    )
    validate_delta(changed.splitlines())
    objects = runner.run(
        phase + "-objects",
        ["git", "rev-parse", *(f"HEAD:{path}" for path in SOURCE_OBJECTS)],
        cwd=source,
        timeout=30,
    ).splitlines()
    if objects != list(SOURCE_OBJECTS.values()):
        raise ValueError(
            "Flutter lib/pubspec/lock Git object pins differ from source83"
        )
    snapshot = runner.builder.source_snapshot(source / "gilbic_mobile")
    tracked = runner.run(
        phase + "-tracked",
        ["git", "ls-files", "--", *SOURCE_OBJECTS],
        cwd=source,
        timeout=30,
    ).splitlines()
    if set(tracked) != {"gilbic_mobile/" + name for name in snapshot}:
        raise ValueError("Flutter input inventory differs from tracked source")
    return snapshot


def load_builder():
    path = Path(__file__).with_name("reviewed_builder.py")
    import hashlib

    if hashlib.sha256(path.read_bytes()).hexdigest() != BUILDER_HASH:
        raise ValueError("Reviewed builder bytes changed")
    spec = importlib.util.spec_from_file_location("reviewed_acceptance_builder", path)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder


def execute():
    if not sys.platform.startswith("linux"):
        raise ValueError("Only the isolated Linux runner is allowed")
    validate_context(os.environ)
    source = Path(os.environ["GITHUB_WORKSPACE"]).resolve()
    if Path(__file__).resolve() != source / ".native-acceptance/build_linux.py":
        raise ValueError("Wrapper must be the checked-out acceptance branch file")
    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve()
    output = runner_temp / "s04-native-debug-output"
    validate_output(output, runner_temp)
    builder = load_builder()
    builder.assert_plain(source)
    output.mkdir()
    work = runner_temp / (
        "s04-native-debug-work-"
        + os.environ["GITHUB_RUN_ID"]
        + "-"
        + os.environ["GITHUB_RUN_ATTEMPT"]
    )
    if work.exists() or work.is_symlink():
        raise FileExistsError("Owned build work directory already exists")
    work.mkdir()
    environment = child_environment(os.environ, work)
    for key in ("HOME", "TMPDIR", "PUB_CACHE", "GRADLE_USER_HOME", "ANDROID_USER_HOME"):
        Path(environment[key]).mkdir(parents=True, exist_ok=True)
    runner = Runner(output, environment, builder)
    try:
        snapshot = verify_checkout(runner, source, os.environ["GITHUB_SHA"], "before")
        flutter = shutil.which("flutter", path=environment.get("PATH"))
        if not flutter:
            raise ValueError("Pinned Flutter executable absent")
        runner.run("bootstrap-flutter", [flutter, "--version"], cwd=work, timeout=360)
        version_text = runner.run(
            "flutter-version",
            [flutter, "--version", "--machine"],
            cwd=work,
            timeout=180,
        )
        version = json.loads(version_text)
        if version.get("frameworkVersion") != FLUTTER_VERSION:
            raise ValueError(
                "Flutter version differs from existing reviewed CI toolchain"
            )
        java = runner.run(
            "java-version",
            [Path(environment["JAVA_HOME"]) / "bin/java", "-version"],
            cwd=work,
            timeout=30,
        )
        if not re.search(r'version "17(?:\.|")', java):
            raise ValueError("Temurin Java17 toolchain required")
        sdk = Path(
            environment.get("ANDROID_SDK_ROOT") or environment["ANDROID_HOME"]
        ).resolve()
        builder.SDK = sdk
        aapt, apksigner = builder.sdk_tool("aapt"), builder.sdk_tool("apksigner")
        host = work / "android-host"
        host.mkdir()
        # Explicit portability adapter only: reviewed preparation/validation functions unchanged.
        builder.SOURCE, builder.HOST = source, host
        runner.run(
            "create-host",
            [
                flutter,
                "create",
                "--no-pub",
                "--platforms=android",
                "--android-language=kotlin",
                "--org",
                "com.spinalending",
                "--project-name",
                "gilbic_mobile",
                ".",
            ],
            cwd=host,
            timeout=180,
        )
        metadata = builder.prepare_generated_host(snapshot)
        metadata.update(
            build_host_platform="linux-disposable-github-runner",
            workflow_repository=REPOSITORY,
            workflow_ref=REF,
            workflow_commit=os.environ["GITHUB_SHA"],
            workflow_run_id=os.environ["GITHUB_RUN_ID"],
            workflow_run_attempt=os.environ["GITHUB_RUN_ATTEMPT"],
            port_adapter_sha256=builder.sha256(Path(__file__)),
            source_git_objects=SOURCE_OBJECTS,
            flutter_version=version,
            java_version=java.strip(),
        )
        asset = host / "android/app/src/main/assets/native-acceptance-build.json"
        asset.write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        builder.write_json_new(output / "build-provenance.json", metadata)
        runner.run(
            "precache-android",
            [flutter, "precache", "--android"],
            cwd=host,
            timeout=600,
        )
        runner.run(
            "locked-pub-get",
            [flutter, "pub", "get", "--enforce-lockfile"],
            cwd=host,
            timeout=600,
        )
        if builder.source_snapshot(host) != snapshot:
            raise ValueError("Locked dependency resolution changed source inputs")
        runner.run(
            "debug-arm64-build", build_command(Path(flutter)), cwd=host, timeout=2400
        )
        if (
            builder.source_snapshot(host) != snapshot
            or verify_checkout(runner, source, os.environ["GITHUB_SHA"], "after")
            != snapshot
        ):
            raise ValueError("Build changed source inputs")
        if any(
            builder.sha256(host / name) != digest
            for name, digest in metadata["host_configuration_sha256"].items()
        ):
            raise ValueError("Generated host configuration changed during build")
        apk = host / "build/app/outputs/flutter-apk/app-debug.apk"
        builder.verify_zip(apk, metadata)
        badging = runner.run(
            "apk-badging", [aapt, "dump", "badging", apk], cwd=host, timeout=60
        )
        builder.verify_badging(
            badging, metadata["version_name"], metadata["version_code"]
        )
        runner.run(
            "apk-manifest",
            [aapt, "dump", "xmltree", apk, "AndroidManifest.xml"],
            cwd=host,
            timeout=60,
        )
        runner.run(
            "apk-network-policy",
            [
                aapt,
                "dump",
                "xmltree",
                apk,
                "res/xml/native_acceptance_network_security.xml",
            ],
            cwd=host,
            timeout=60,
        )
        certificates = runner.run(
            "apk-signature",
            [apksigner, "verify", "--verbose", "--print-certs", apk],
            cwd=host,
            timeout=60,
        )
        certificate_sha256 = verify_debug_signer(certificates)
        destination = output / "Spina-Native-Acceptance-arm64-debug.apk"
        with apk.open("rb") as reader, destination.open("xb") as writer:
            shutil.copyfileobj(reader, writer)
        result = {
            "status": "DEBUG_ARTIFACT_CHECKS_PASSED",
            "production_ready": False,
            "production_verifier_used": False,
            "native_acceptance_executed": False,
            "source_sha": SOURCE_SHA,
            "workflow_commit": os.environ["GITHUB_SHA"],
            "application_id": builder.PACKAGE,
            "label": builder.LABEL,
            "debuggable": True,
            "target_platform": "android-arm64",
            "api_url": builder.API_URL,
            "apk_name": destination.name,
            "apk_sha256": builder.sha256(destination),
            "certificate_sha256": certificate_sha256,
            "endpoint_evidence": "Exact build define, copied source/lock hashes, APK metadata and endpoint string in debug kernel; phone connectivity untested",
        }
        builder.write_json_new(output / "debug-artifact-result.json", result)
        runner.emit("debug_artifact_verified", **result)
        print(json.dumps(result, indent=2))
    except BaseException as error:
        runner.emit("failed", error_type=type(error).__name__)
        raise
    finally:
        runner.events.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        print(
            json.dumps(
                {
                    "mode": "PLAN_ONLY",
                    "source_sha": SOURCE_SHA,
                    "workflow_ref": REF,
                    "debug_only": True,
                    "no_build_or_network_started": True,
                },
                indent=2,
            )
        )
        return 0
    try:
        execute()
        return 0
    except Exception as error:  # noqa: BLE001 - fixed summary; no environment/error payload
        print("Isolated debug build stopped: " + type(error).__name__, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
