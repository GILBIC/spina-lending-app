"""Build one isolated, synthetic acceptance APK. Dry plan unless --execute.

This is an artifact harness, not production preparation or release verification.
It never installs an APK, starts a backend/database, or edits the source checkout.
"""

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

sys.dont_write_bytecode = True
SOURCE_SHA = "83d66b31cfaff67783b03353fa16cf2dee509cd2"
CHECKPOINTS = Path(
    "C:/Users/pc/Documents/Codex/2026-09-19/continue-spina-if-you-have-some/checkpoints"
)
PRIVATE_ROOT = CHECKPOINTS / "s04-native-acceptance-20261013"
SOURCE = PRIVATE_ROOT / "source83"
HOST = PRIVATE_ROOT / "android-host"
ARTIFACT_ROOT = Path(__file__).resolve().parent
FLUTTER = Path("C:/src/flutter/bin/flutter.bat")
SDK = Path("C:/Users/pc/AppData/Local/Android/Sdk")
JAVA = Path("C:/Program Files/Android/Android Studio/jbr")
BASE_PACKAGE = "com.spinalending.gilbic_mobile"
PACKAGE = BASE_PACKAGE + ".nativeacceptance"
API_URL = "http://127.0.0.1:18080"
LABEL = "SPINA TEST ONLY"
GIB = 1024**3
METADATA_ASSET = "assets/native-acceptance-build.json"
KERNEL_ASSET = "assets/flutter_assets/kernel_blob.bin"
REQUIRED_APK_FILES = {
    "AndroidManifest.xml",
    "classes.dex",
    "lib/arm64-v8a/libflutter.so",
    "lib/arm64-v8a/libsqlcipher.so",
    "res/xml/native_acceptance_network_security.xml",
}
TOOL_ENV = {
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "WINDIR",
    "COMSPEC",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "PROGRAMDATA",
    "HOMEDRIVE",
    "HOMEPATH",
    "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE",
}
DEBUG_MANIFEST = """<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools">
    <uses-permission android:name="android.permission.INTERNET" />
    <application android:label="SPINA TEST ONLY"
        tools:replace="android:label"
        android:networkSecurityConfig="@xml/native_acceptance_network_security" />
</manifest>
"""
NETWORK_CONFIG = """<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config cleartextTrafficPermitted="false" />
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="false">127.0.0.1</domain>
    </domain-config>
</network-security-config>
"""


def child_environment(parent):
    # Allowlisting also strips lowercase secrets and Java/Gradle injection options.
    result = {
        key.upper(): value for key, value in parent.items() if key.upper() in TOOL_ENV
    }
    result.update(
        ANDROID_HOME=str(SDK),
        ANDROID_SDK_ROOT=str(SDK),
        JAVA_HOME=str(JAVA),
        CI="true",
        FLUTTER_SUPPRESS_ANALYTICS="true",
    )
    return result


def assert_plain(path):
    for entry in (path, *path.parents):
        if entry.exists() or entry.is_symlink():
            details = entry.lstat()
            if (
                entry.is_symlink()
                or getattr(details, "st_file_attributes", 0)
                & stat.FILE_ATTRIBUTE_REPARSE_POINT
            ):
                raise ValueError("Reparse points are forbidden in source/output paths")


def validate_host(host, owned_root):
    if host.absolute() != owned_root.absolute() / "android-host":
        raise ValueError("Host must be the exact owned android-host path")
    if not owned_root.is_dir():
        raise ValueError("Private root must be prepared with protect-private.ps1 first")
    assert_plain(host)
    if any(part.lower() == "onedrive" for part in host.parts):
        raise ValueError("Acceptance host must be outside OneDrive")
    if host.exists():
        raise FileExistsError("Host already exists; refusing to overwrite or clean it")


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_snapshot(mobile):
    assert_plain(mobile)
    if not (mobile / "lib").is_dir():
        raise ValueError("Missing Flutter lib source")
    paths = [mobile / "pubspec.yaml", mobile / "pubspec.lock"]
    for path in (mobile / "lib").rglob("*"):
        assert_plain(path)
        if path.is_file():
            paths.append(path)
    return {path.relative_to(mobile).as_posix(): sha256(path) for path in sorted(paths)}


def debug_gradle(original):
    expected = {
        f'namespace = "{BASE_PACKAGE}"': 1,
        f'applicationId = "{BASE_PACKAGE}"': 1,
        'signingConfig = signingConfigs.getByName("debug")': 1,
        "    buildTypes {": 1,
        "    defaultConfig {": 1,
        "        release {": 1,
    }
    if any(original.count(text) != count for text, count in expected.items()):
        raise ValueError("Unexpected Android template; refusing to guess a patch")
    if "applicationIdSuffix" in original or "signingConfigs {" in original:
        raise ValueError(
            "Expected a fresh Android template without signing configuration"
        )
    output = (
        original.replace(
            'signingConfig = signingConfigs.getByName("debug")', "signingConfig = null"
        )
        .replace(
            "    defaultConfig {",
            """    defaultConfig {
        ndk {
            abiFilters.clear()
            abiFilters.add("arm64-v8a")
        }""",
        )
        .replace(
            "    buildTypes {",
            """    buildTypes {
        debug {
            applicationIdSuffix = ".nativeacceptance"
        }""",
        )
        .replace(
            "        release {",
            """        release {
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")""",
        )
    )
    return (
        output
        + """
// Disposable acceptance host: no release/profile task may execute.
gradle.taskGraph.whenReady {
    val rejected = allTasks.filter {
        val debugProfileSupport = listOf("DebugArtProfile", "DebugStartupProfile", "DebugArtProfileWildcards")
            .any { suffix -> it.name.endsWith(suffix, ignoreCase = true) }
        it.name.contains("release", ignoreCase = true) ||
            (it.name.contains("profile", ignoreCase = true) && !debugProfileSupport)
    }
    if (rejected.isNotEmpty()) {
        throw GradleException("Debug acceptance host rejects release/profile tasks: " + rejected.joinToString { it.path })
    }
}
"""
    )


def write_new(path, contents):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(contents)


def write_json_new(path, data):
    write_new(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def resource_snapshot(directory):
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong)
            for name in (
                "total_phys",
                "avail_phys",
                "total_page",
                "avail_page",
                "total_virtual",
                "avail_virtual",
                "avail_extended",
            )
        ]

    memory = MemoryStatus()
    memory.length = ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise OSError("Unable to read Windows available memory")
    return {
        "free_ram_bytes": memory.avail_phys,
        "free_disk_bytes": shutil.disk_usage(directory).free,
    }


def check_resource_floor(sample, *, starting):
    ram = 2 * GIB if starting else GIB // 2
    disk = 8 * GIB if starting else 2 * GIB
    if sample["free_ram_bytes"] < ram or sample["free_disk_bytes"] < disk:
        raise RuntimeError(
            "Build resource floor reached; no success artifact may be recorded"
        )


class Runner:
    def __init__(self, directory, environment):
        directory.mkdir(exist_ok=False)
        self.directory, self.environment = directory, environment
        self.events = (directory / "events.jsonl").open("x", encoding="utf-8")
        self.index = 0

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
        sample = resource_snapshot(PRIVATE_ROOT)
        self.emit("preflight", phase=name, **sample)
        check_resource_floor(sample, starting=True)
        self.index += 1
        output = self.directory / f"{self.index:02d}-{name}.log"
        start = time.monotonic()
        with output.open("xb") as stream:
            self.emit(
                "command_start",
                phase=name,
                argv=[str(item) for item in argv],
                cwd=str(cwd),
                deadline_seconds=timeout,
            )
            process = subprocess.Popen(
                [str(item) for item in argv],
                cwd=cwd,
                env=self.environment,
                stdout=stream,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            try:
                while True:
                    try:
                        result = process.wait(timeout=5)
                        break
                    except subprocess.TimeoutExpired:
                        sample = resource_snapshot(PRIVATE_ROOT)
                        self.emit("resources", phase=name, **sample)
                        check_resource_floor(sample, starting=False)
                        if time.monotonic() - start > timeout:
                            raise TimeoutError(
                                f"Finite phase deadline exceeded: {name}"
                            ) from None
            except BaseException:
                if process.poll() is None:
                    # Terminate only this freshly launched process tree, never unrelated tools.
                    subprocess.run(
                        [
                            str(
                                Path(self.environment["SYSTEMROOT"])
                                / "System32/taskkill.exe"
                            ),
                            "/PID",
                            str(process.pid),
                            "/T",
                            "/F",
                        ],
                        env=self.environment,
                        stdout=stream,
                        stderr=subprocess.STDOUT,
                        timeout=15,
                        check=False,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    process.wait(timeout=15)
                self.emit(
                    "command_aborted",
                    phase=name,
                    elapsed_seconds=time.monotonic() - start,
                )
                raise
        self.emit(
            "command_complete",
            phase=name,
            exit_code=result,
            elapsed_seconds=time.monotonic() - start,
        )
        if result:
            raise RuntimeError(f"{name} failed with exit {result}; see {output}")
        return output.read_text(encoding="utf-8", errors="replace")


def verify_badging(text, version_name, version_code):
    package = re.search(
        r"^package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'",
        text,
        re.MULTILINE,
    )
    if not package or package.groups() != (PACKAGE, version_code, version_name):
        raise ValueError("APK package/version mismatch")
    if not re.search(r"^application-debuggable\s*$", text, re.MULTILINE):
        raise ValueError("APK is not debuggable")
    if f"application-label:'{LABEL}'" not in text.splitlines():
        raise ValueError("APK acceptance label mismatch")
    if "uses-permission: name='android.permission.INTERNET'" not in text:
        raise ValueError("APK INTERNET permission missing")
    native = re.search(r"^native-code:(.*)$", text, re.MULTILINE)
    if not native or re.findall(r"'([^']+)'", native[1]) != ["arm64-v8a"]:
        raise ValueError("APK must contain only arm64 native code")


def verify_zip(apk, metadata):
    with ZipFile(apk) as zipped:
        names = zipped.namelist()
        if len(set(names)) != len(names):
            raise ValueError("Duplicate APK archive entries")
        if not REQUIRED_APK_FILES.issubset(names):
            raise ValueError("APK missing required native or manifest entries")
        if "assets/spina-build.json" in names:
            raise ValueError(
                "Acceptance host must not masquerade as production build metadata"
            )
        if json.loads(zipped.read(METADATA_ASSET)) != metadata:
            raise ValueError("APK provenance metadata mismatch")
        if API_URL.encode() not in zipped.read(KERNEL_ASSET):
            raise ValueError("Compiled debug kernel lacks acceptance endpoint string")


def sdk_tool(name):
    versions = [
        path
        for path in (SDK / "build-tools").iterdir()
        if re.fullmatch(r"\d+\.\d+\.\d+", path.name) and (path / name).is_file()
    ]
    if not versions:
        raise ValueError(f"Required SDK tool absent: {name}")
    return max(versions, key=lambda path: tuple(map(int, path.name.split(".")))) / name


def check_source(runner, label):
    head = runner.run(
        label + "-head", ["git", "rev-parse", "HEAD"], cwd=SOURCE, timeout=30
    ).strip()
    status = runner.run(
        label + "-status",
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=SOURCE,
        timeout=30,
    )
    if head != SOURCE_SHA or status.strip():
        raise ValueError("Source must be the exact clean reviewed commit")
    snapshot = source_snapshot(SOURCE / "gilbic_mobile")
    tracked = runner.run(
        label + "-tracked",
        [
            "git",
            "ls-files",
            "--",
            "gilbic_mobile/lib",
            "gilbic_mobile/pubspec.yaml",
            "gilbic_mobile/pubspec.lock",
        ],
        cwd=SOURCE,
        timeout=30,
    )
    if set(tracked.splitlines()) != {"gilbic_mobile/" + name for name in snapshot}:
        raise ValueError("Copied Flutter files must match tracked source exactly")
    return snapshot


def prepare_generated_host(snapshot):
    mobile = SOURCE / "gilbic_mobile"
    if {
        path.relative_to(HOST / "lib").as_posix()
        for path in (HOST / "lib").rglob("*")
        if path.is_file()
    } != {"main.dart"}:
        raise ValueError("Unexpected generated lib template")
    shutil.copytree(mobile / "lib", HOST / "lib", dirs_exist_ok=True)
    for name in ("pubspec.yaml", "pubspec.lock"):
        shutil.copyfile(mobile / name, HOST / name)
    if source_snapshot(HOST) != snapshot:
        raise ValueError("Copied source does not match candidate")
    gradle = HOST / "android/app/build.gradle.kts"
    gradle.write_text(debug_gradle(gradle.read_text()), encoding="utf-8")
    # Only freshly generated files are replaced. No production host is read/copied.
    (HOST / "android/app/src/debug/AndroidManifest.xml").write_text(
        DEBUG_MANIFEST, encoding="utf-8"
    )
    write_new(
        HOST / "android/app/src/debug/res/xml/native_acceptance_network_security.xml",
        NETWORK_CONFIG,
    )
    write_new(
        HOST / "android/app/proguard-rules.pro", "-keep class net.sqlcipher.** { *; }\n"
    )
    properties = HOST / "android/gradle.properties"
    existing = properties.read_text()
    values = {
        "org.gradle.jvmargs": "-Xmx1024m -XX:MaxMetaspaceSize=512m -XX:+HeapDumpOnOutOfMemoryError",
        "org.gradle.workers.max": "1",
        "org.gradle.daemon": "false",
        "kotlin.incremental": "false",
        "kotlin.compiler.execution.strategy": "in-process",
    }
    lines = [
        line
        for line in existing.splitlines()
        if line.partition("=")[0].strip() not in values
    ]
    properties.write_text(
        "\n".join(lines + [f"{key}={value}" for key, value in values.items()]) + "\n",
        encoding="utf-8",
    )
    version = re.search(
        r"^version:\s*(\d+\.\d+\.\d+)\+(\d+)\s*$",
        (HOST / "pubspec.yaml").read_text(),
        re.MULTILINE,
    )
    if not version:
        raise ValueError("Expected explicit Flutter version name and number")
    altered = [
        "android/app/build.gradle.kts",
        "android/gradle.properties",
        "android/app/src/debug/AndroidManifest.xml",
        "android/app/proguard-rules.pro",
        "android/app/src/debug/res/xml/native_acceptance_network_security.xml",
    ]
    metadata = {
        "kind": "synthetic_native_acceptance",
        "production_ready": False,
        "production_verifier_used": False,
        "source_sha": SOURCE_SHA,
        "application_id": PACKAGE,
        "label": LABEL,
        "build_mode": "debug",
        "target_platform": "android-arm64",
        "api_url": API_URL,
        "dart_defines": ["GILBIC_API_URL=" + API_URL],
        "version_name": version[1],
        "version_code": version[2],
        "source_files_sha256": snapshot,
        "pubspec_lock_sha256": snapshot["pubspec.lock"],
        "host_configuration_sha256": {name: sha256(HOST / name) for name in altered},
        "builder_sha256": sha256(Path(__file__)),
    }
    write_json_new(
        HOST / "android/app/src/main/assets/native-acceptance-build.json", metadata
    )
    return metadata


def execute():
    if os.name != "nt":
        raise ValueError(
            "This artifact builder is pinned to the reviewed Windows toolchain"
        )
    validate_host(HOST, PRIVATE_ROOT)
    for required in (
        FLUTTER,
        JAVA / "bin/java.exe",
        SOURCE / ".git",
        ARTIFACT_ROOT / "protect-private.ps1",
    ):
        if not required.exists():
            raise ValueError(f"Required local input missing: {required}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    runner = Runner(
        ARTIFACT_ROOT / ("android-build-" + stamp), child_environment(os.environ)
    )
    try:
        powershell = shutil.which("pwsh", path=runner.environment.get("PATH")) or str(
            Path(runner.environment["SYSTEMROOT"])
            / "System32/WindowsPowerShell/v1.0/powershell.exe"
        )
        runner.run(
            "acl-check",
            [
                powershell,
                "-NoProfile",
                "-File",
                ARTIFACT_ROOT / "protect-private.ps1",
                "-CheckOnly",
            ],
            cwd=ARTIFACT_ROOT,
            timeout=60,
        )
        snapshot = check_source(runner, "before")
        aapt, apksigner = sdk_tool("aapt.exe"), sdk_tool("apksigner.bat")
        validate_host(HOST, PRIVATE_ROOT)
        HOST.mkdir(exist_ok=False)
        write_json_new(
            HOST / ".native-acceptance-owner.json",
            {
                "source_sha": SOURCE_SHA,
                "kind": "synthetic_native_acceptance",
                "created_utc": stamp,
            },
        )
        runner.run(
            "flutter-version", [FLUTTER, "--version", "--machine"], cwd=HOST, timeout=90
        )
        runner.run(
            "create-host",
            [
                FLUTTER,
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
            cwd=HOST,
            timeout=180,
        )
        metadata = prepare_generated_host(snapshot)
        write_json_new(runner.directory / "build-provenance.json", metadata)
        runner.run(
            "locked-pub-get",
            [FLUTTER, "pub", "get", "--enforce-lockfile"],
            cwd=HOST,
            timeout=600,
        )
        if source_snapshot(HOST) != snapshot:
            raise ValueError("Dependency resolution changed locked candidate files")
        runner.run(
            "debug-arm64-build",
            [
                FLUTTER,
                "build",
                "apk",
                "--debug",
                "--no-pub",
                "--target-platform=android-arm64",
                "--dart-define=GILBIC_API_URL=" + API_URL,
            ],
            cwd=HOST,
            timeout=2400,
        )
        if (
            source_snapshot(HOST) != snapshot
            or check_source(runner, "after") != snapshot
        ):
            raise ValueError("Source changed during build")
        for name, expected in metadata["host_configuration_sha256"].items():
            if sha256(HOST / name) != expected:
                raise ValueError("Generated host configuration changed during build")
        apk = HOST / "build/app/outputs/flutter-apk/app-debug.apk"
        verify_zip(apk, metadata)
        badging = runner.run(
            "apk-badging", [aapt, "dump", "badging", apk], cwd=HOST, timeout=60
        )
        verify_badging(badging, metadata["version_name"], metadata["version_code"])
        runner.run(
            "apk-manifest",
            [aapt, "dump", "xmltree", apk, "AndroidManifest.xml"],
            cwd=HOST,
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
            cwd=HOST,
            timeout=60,
        )
        certificates = runner.run(
            "apk-signature",
            [apksigner, "verify", "--verbose", "--print-certs", apk],
            cwd=HOST,
            timeout=60,
        )
        digests = re.findall(
            r"^Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F]{64})$",
            certificates,
            re.MULTILINE,
        )
        subjects = re.findall(
            r"^Signer #\d+ certificate DN: (.+)$", certificates, re.MULTILINE
        )
        if (
            "Number of signers: 1" not in certificates
            or len(digests) != 1
            or len(subjects) != 1
            or "CN=Android Debug" not in subjects[0]
        ):
            raise ValueError("Expected one standard Android debug signer")
        result = {
            "status": "DEBUG_ARTIFACT_CHECKS_PASSED",
            "production_ready": False,
            "native_acceptance_executed": False,
            "production_verifier_used": False,
            "apk": str(apk),
            "apk_sha256": sha256(apk),
            "source_sha": SOURCE_SHA,
            "application_id": PACKAGE,
            "label": LABEL,
            "debuggable": True,
            "api_url": API_URL,
            "certificate_sha256": digests[0].lower(),
            "endpoint_evidence": "Exact build define, source/lock hashes, APK metadata, and endpoint string in compiled debug kernel; device connectivity not yet tested",
            "logs": str(runner.directory),
        }
        write_json_new(runner.directory / "debug-artifact-result.json", result)
        runner.emit("debug_artifact_verified", **result)
        print(json.dumps(result, indent=2))
    except BaseException as error:
        # Do not expose environment values or arbitrary subprocess exception output.
        runner.emit("failed", error_type=type(error).__name__)
        print(
            f"Builder failed ({type(error).__name__}); retained logs: {runner.directory}",
            file=sys.stderr,
        )
        raise
    finally:
        runner.events.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Create the fresh owned host and run the bounded debug build",
    )
    args = parser.parse_args(argv)
    if not args.execute:
        print(
            json.dumps(
                {
                    "mode": "PLAN_ONLY",
                    "source": str(SOURCE),
                    "source_sha": SOURCE_SHA,
                    "host": str(HOST),
                    "package": PACKAGE,
                    "label": LABEL,
                    "debug_only": True,
                    "api_url": API_URL,
                    "target_platform": "android-arm64",
                    "requires": "Prepared private ACL root; host absent; clean source; free RAM >=2GiB and disk >=8GiB",
                    "creates_host": False,
                    "launches_tools": False,
                },
                indent=2,
            )
        )
        return 0
    execute()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
