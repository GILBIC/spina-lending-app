# SPINA Cross-Platform Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing Flutter client compile and launch safely on Web and Windows while preserving Android/iOS encrypted-route behavior and add one exact-head cross-platform build lane.

**Architecture:** Keep the platform-neutral route-cache contract in `collector_route_cache.dart`, move SQLCipher implementation behind a conditional platform factory, and use an online-only memory cache on Web/Windows. Extend the existing platform bootstrap and CI without changing server-authoritative collection behavior.

**Tech Stack:** Flutter 3.44+, Dart 3.10+, `flutter_secure_storage`, `sqflite_sqlcipher`, GitHub Actions, self-hosted Windows runner.

**Spec:** `docs/superpowers/specs/2026-09-03-cross-platform-mvp-design.md`

## Global Constraints

- One Flutter codebase must target Web, Windows, Android, and iOS.
- Android/iOS retain encrypted SQLCipher route caching.
- Web/Windows use an online-only in-memory route cache for the MVP.
- Collector financial writes remain online-only on every platform.
- No Supabase secret, PostgreSQL URL, webhook secret, or provider secret enters Flutter.
- The branch remains Draft and must not be merged or used for real financial activity from MVP evidence alone.

---

### Task 1: Define and prove the route-cache platform policy

**Files:**
- Create: `gilbic_mobile/lib/src/core/collector/collector_route_cache_policy.dart`
- Test: `gilbic_mobile/test/collector_route_cache_policy_test.dart`

**Interfaces:**
- Consumes: Flutter `TargetPlatform` and an explicit `isWeb` value.
- Produces: `enum CollectorRouteCacheMode { encryptedSqlCipher, onlineMemory }` and `CollectorRouteCacheMode collectorRouteCacheMode({required bool isWeb, required TargetPlatform platform})`.

- [ ] **Step 1: Write the failing policy test**

```dart
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache_policy.dart';

void main() {
  test('Android and iOS require encrypted route cache', () {
    for (final platform in <TargetPlatform>[
      TargetPlatform.android,
      TargetPlatform.iOS,
    ]) {
      expect(
        collectorRouteCacheMode(isWeb: false, platform: platform),
        CollectorRouteCacheMode.encryptedSqlCipher,
      );
    }
  });

  test('Web and desktop use online-only memory route cache', () {
    expect(
      collectorRouteCacheMode(
        isWeb: true,
        platform: TargetPlatform.android,
      ),
      CollectorRouteCacheMode.onlineMemory,
    );
    for (final platform in <TargetPlatform>[
      TargetPlatform.windows,
      TargetPlatform.macOS,
      TargetPlatform.linux,
      TargetPlatform.fuchsia,
    ]) {
      expect(
        collectorRouteCacheMode(isWeb: false, platform: platform),
        CollectorRouteCacheMode.onlineMemory,
      );
    }
  });
}
```

- [ ] **Step 2: Run the test and confirm RED**

Run:

```powershell
Set-Location gilbic_mobile
flutter test test/collector_route_cache_policy_test.dart
```

Expected: compilation failure because `collector_route_cache_policy.dart` and its API do not exist.

- [ ] **Step 3: Implement the minimal policy**

```dart
import 'package:flutter/foundation.dart';

enum CollectorRouteCacheMode { encryptedSqlCipher, onlineMemory }

CollectorRouteCacheMode collectorRouteCacheMode({
  required bool isWeb,
  required TargetPlatform platform,
}) {
  if (!isWeb &&
      (platform == TargetPlatform.android ||
          platform == TargetPlatform.iOS)) {
    return CollectorRouteCacheMode.encryptedSqlCipher;
  }
  return CollectorRouteCacheMode.onlineMemory;
}
```

- [ ] **Step 4: Run the focused test and confirm GREEN**

Run:

```powershell
Set-Location gilbic_mobile
flutter test test/collector_route_cache_policy_test.dart
```

Expected: 2 tests pass, 0 fail.

- [ ] **Step 5: Commit**

```bash
git add gilbic_mobile/lib/src/core/collector/collector_route_cache_policy.dart gilbic_mobile/test/collector_route_cache_policy_test.dart
git commit -m "test: define cross-platform route cache policy"
```

### Task 2: Isolate SQLCipher and build the default cache factory

**Files:**
- Modify: `gilbic_mobile/lib/src/core/collector/collector_route_cache.dart`
- Create: `gilbic_mobile/lib/src/core/collector/collector_route_cache_sqlcipher.dart`
- Create: `gilbic_mobile/lib/src/core/collector/collector_route_cache_factory.dart`
- Create: `gilbic_mobile/lib/src/core/collector/collector_route_cache_factory_stub.dart`
- Create: `gilbic_mobile/lib/src/core/collector/collector_route_cache_factory_io.dart`
- Test: `gilbic_mobile/test/collector_route_cache_factory_test.dart`

**Interfaces:**
- Consumes: `CollectorRouteCache`, `MemoryCollectorRouteCache`, `CollectorRouteCacheMode`, Flutter runtime platform.
- Produces: `CollectorRouteCache createDefaultCollectorRouteCache({bool? isWeb, TargetPlatform? platform})`.

- [ ] **Step 1: Write the failing factory test**

```dart
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache_factory.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache_sqlcipher.dart';

void main() {
  test('factory uses memory cache for Web and Windows', () {
    expect(
      createDefaultCollectorRouteCache(
        isWeb: true,
        platform: TargetPlatform.android,
      ),
      isA<MemoryCollectorRouteCache>(),
    );
    expect(
      createDefaultCollectorRouteCache(
        isWeb: false,
        platform: TargetPlatform.windows,
      ),
      isA<MemoryCollectorRouteCache>(),
    );
  });

  test('factory uses SQLCipher for Android and iOS on IO runtimes', () {
    for (final platform in <TargetPlatform>[
      TargetPlatform.android,
      TargetPlatform.iOS,
    ]) {
      expect(
        createDefaultCollectorRouteCache(
          isWeb: false,
          platform: platform,
        ),
        isA<SqlCipherCollectorRouteCache>(),
      );
    }
  });
}
```

- [ ] **Step 2: Run the test and confirm RED**

Run:

```powershell
Set-Location gilbic_mobile
flutter test test/collector_route_cache_factory_test.dart
```

Expected: compilation failure because the factory and isolated SQLCipher module do not exist.

- [ ] **Step 3: Move the SQLCipher implementation without changing behavior**

Keep these types in `collector_route_cache.dart`:

```dart
class CollectorRouteCacheSnapshot { /* existing fields and constructor */ }
abstract interface class CollectorRouteCache { /* existing methods */ }
class MemoryCollectorRouteCache implements CollectorRouteCache { /* existing behavior */ }
abstract interface class RouteCacheKeyStore { /* existing method */ }
class SecureRouteCacheKeyStore implements RouteCacheKeyStore { /* existing behavior */ }
```

Move `SqlCipherCollectorRouteCache` and the `path`/`sqflite_sqlcipher` imports unchanged into `collector_route_cache_sqlcipher.dart`. Import `collector_route_cache.dart` and `collector_route.dart` there.

- [ ] **Step 4: Add the conditional factory**

`collector_route_cache_factory.dart`:

```dart
import 'package:flutter/foundation.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache_factory_stub.dart'
    if (dart.library.io) 'collector_route_cache_factory_io.dart' as platform;

CollectorRouteCache createDefaultCollectorRouteCache({
  bool? isWeb,
  TargetPlatform? platform,
}) {
  return platform.createPlatformCollectorRouteCache(
    isWeb: isWeb ?? kIsWeb,
    platform: platform ?? defaultTargetPlatform,
  );
}
```

`collector_route_cache_factory_stub.dart`:

```dart
import 'package:flutter/foundation.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache.dart';

CollectorRouteCache createPlatformCollectorRouteCache({
  required bool isWeb,
  required TargetPlatform platform,
}) => MemoryCollectorRouteCache();
```

`collector_route_cache_factory_io.dart`:

```dart
import 'package:flutter/foundation.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache_policy.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache_sqlcipher.dart';

CollectorRouteCache createPlatformCollectorRouteCache({
  required bool isWeb,
  required TargetPlatform platform,
}) {
  return switch (collectorRouteCacheMode(isWeb: isWeb, platform: platform)) {
    CollectorRouteCacheMode.encryptedSqlCipher =>
      SqlCipherCollectorRouteCache(),
    CollectorRouteCacheMode.onlineMemory => MemoryCollectorRouteCache(),
  };
}
```

- [ ] **Step 5: Run focused and neighboring tests**

Run:

```powershell
Set-Location gilbic_mobile
flutter test test/collector_route_cache_policy_test.dart test/collector_route_cache_factory_test.dart test/collector_route_cache_test.dart test/collector_route_loader_test.dart
```

Expected: all tests pass with no exception or warning.

- [ ] **Step 6: Run a Web compile smoke**

Run:

```powershell
Set-Location gilbic_mobile
flutter create --platforms=web --project-name gilbic_mobile .
flutter build web --debug --dart-define=GILBIC_API_URL=http://127.0.0.1:8000
```

Expected: build exits 0 and `build/web/index.html` exists. The Web compilation must not import `sqflite_sqlcipher`.

- [ ] **Step 7: Commit**

```bash
git add gilbic_mobile/lib/src/core/collector/collector_route_cache.dart gilbic_mobile/lib/src/core/collector/collector_route_cache_sqlcipher.dart gilbic_mobile/lib/src/core/collector/collector_route_cache_factory.dart gilbic_mobile/lib/src/core/collector/collector_route_cache_factory_stub.dart gilbic_mobile/lib/src/core/collector/collector_route_cache_factory_io.dart gilbic_mobile/test/collector_route_cache_factory_test.dart
git commit -m "feat: select safe route cache per platform"
```

### Task 3: Wire application composition to the platform factory

**Files:**
- Modify: `gilbic_mobile/lib/src/app.dart`
- Test: `gilbic_mobile/test/app_default_route_cache_test.dart`

**Interfaces:**
- Consumes: `createDefaultCollectorRouteCache()` from Task 2.
- Produces: `GilbicApp` default composition that starts on Web/Windows without opening SQLCipher.

- [ ] **Step 1: Write the failing widget test**

```dart
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/app.dart';
import 'package:gilbic_mobile/src/core/auth/auth_repository.dart';
import 'package:gilbic_mobile/src/core/auth/session_store.dart';

void main() {
  testWidgets('default Windows composition reaches login without SQLCipher', (
    tester,
  ) async {
    final previous = debugDefaultTargetPlatformOverride;
    debugDefaultTargetPlatformOverride = TargetPlatform.windows;
    addTearDown(() => debugDefaultTargetPlatformOverride = previous);

    await tester.pumpWidget(
      GilbicApp(
        sessionStore: MemorySessionStore(),
        authRepository: _OfflineAuthRepository(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byType(TextField), findsWidgets);
    expect(find.text('Sign in'), findsWidgets);
  });
}

class _OfflineAuthRepository implements AuthRepository {
  @override
  Future<void> signOut(session) async {}

  @override
  Future signIn({required String username, required String password}) {
    throw UnimplementedError();
  }
}
```

Adapt the fake method signatures exactly to the current `AuthRepository` interface while preserving the assertion: default Windows composition must reach the login UI without a missing SQLCipher plugin failure.

- [ ] **Step 2: Run the test and confirm RED**

Run:

```powershell
Set-Location gilbic_mobile
flutter test test/app_default_route_cache_test.dart
```

Expected: the current app constructs `SqlCipherCollectorRouteCache` unconditionally, so the test fails during default composition or compilation after the SQLCipher split.

- [ ] **Step 3: Replace the default constructor call**

In `app.dart`, import the factory and replace:

```dart
final cache = widget.collectorRouteCache ?? SqlCipherCollectorRouteCache();
```

with:

```dart
final cache =
    widget.collectorRouteCache ?? createDefaultCollectorRouteCache();
```

- [ ] **Step 4: Run focused tests and complete Flutter suite**

Run:

```powershell
Set-Location gilbic_mobile
flutter test test/app_default_route_cache_test.dart test/app_widget_test.dart test/mobile_auth_error_parity_test.dart
flutter test
flutter analyze --fatal-infos
```

Expected: all tests pass and analyzer reports no issues.

- [ ] **Step 5: Commit**

```bash
git add gilbic_mobile/lib/src/app.dart gilbic_mobile/test/app_default_route_cache_test.dart
git commit -m "feat: compose route cache safely across platforms"
```

### Task 4: Extend reproducible platform generation to Web and Windows

**Files:**
- Modify: `gilbic_mobile/tool/bootstrap_platforms.ps1`
- Modify: `gilbic_mobile/README.md`
- Test: `gilbic_backend/tests/test_cross_platform_bootstrap_contract.py`

**Interfaces:**
- Consumes: Flutter CLI and the repository's current package manifest.
- Produces: one repeatable command that generates `android`, `ios`, `web`, and `windows`, removes only Flutter's generated sample test, applies Android SQLCipher keep rules, restores packages, analyzes, and tests.

- [ ] **Step 1: Write the failing static contract test**

```python
from pathlib import Path


def test_flutter_bootstrap_generates_all_mvp_platforms() -> None:
    root = Path(__file__).resolve().parents[2]
    script = (root / "gilbic_mobile/tool/bootstrap_platforms.ps1").read_text(
        encoding="utf-8"
    )
    assert "--platforms=android,ios,web,windows" in script
    assert 'Join-Path $ProjectRoot "test/widget_test.dart"' in script
    assert "Remove-Item -LiteralPath $GeneratedSampleTest -Force" in script
```

- [ ] **Step 2: Run the test and confirm RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q gilbic_backend\tests\test_cross_platform_bootstrap_contract.py
```

Expected: failure because the script currently generates only Android/iOS and does not remove Flutter's generated sample test.

- [ ] **Step 3: Update the PowerShell bootstrap**

Change the generation call to:

```powershell
flutter create `
    --platforms=android,ios,web,windows `
    --org $Organization `
    --project-name gilbic_mobile `
    .

$GeneratedSampleTest = Join-Path $ProjectRoot "test/widget_test.dart"
if (Test-Path -LiteralPath $GeneratedSampleTest) {
    Remove-Item -LiteralPath $GeneratedSampleTest -Force
}
```

Keep `Add-SqlCipherAndroidRules`, `flutter pub get`, `flutter analyze`, and `flutter test` unchanged after this block.

- [ ] **Step 4: Update README commands**

Document:

```powershell
cd gilbic_mobile
.\tool\bootstrap_platforms.ps1
flutter run -d chrome --dart-define=GILBIC_API_URL=http://127.0.0.1:8000
flutter run -d windows --dart-define=GILBIC_API_URL=http://127.0.0.1:8000
```

State that Web/Windows route snapshots are online-only memory state in the MVP and that financial writes require the API.

- [ ] **Step 5: Run the contract test and bootstrap**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q gilbic_backend\tests\test_cross_platform_bootstrap_contract.py
Set-Location gilbic_mobile
.\tool\bootstrap_platforms.ps1
```

Expected: contract test passes; bootstrap exits 0; analyzer and Flutter suite pass.

- [ ] **Step 6: Commit**

```bash
git add gilbic_mobile/tool/bootstrap_platforms.ps1 gilbic_mobile/README.md gilbic_backend/tests/test_cross_platform_bootstrap_contract.py
git commit -m "build: bootstrap Web and Windows Flutter targets"
```

### Task 5: Add exact-head cross-platform build evidence

**Files:**
- Create: `.github/workflows/spina-cross-platform-mvp.yml`
- Modify: `gilbic_backend/tests/test_cross_platform_bootstrap_contract.py`

**Interfaces:**
- Consumes: the bootstrap script, existing Python/backend packages, self-hosted Windows Flutter/Android toolchain.
- Produces: one pull-request workflow proving backend tests, Flutter analysis/tests, Web build, Windows build, Android debug build, and clean tree on the exact head.

- [ ] **Step 1: Extend the failing contract test**

Add:

```python
def test_mvp_workflow_builds_web_windows_and_android() -> None:
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github/workflows/spina-cross-platform-mvp.yml").read_text(
        encoding="utf-8"
    )
    assert "flutter build web" in workflow
    assert "flutter build windows" in workflow
    assert "flutter build apk --debug" in workflow
    assert "git diff --exit-code" in workflow
```

- [ ] **Step 2: Run the test and confirm RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q gilbic_backend\tests\test_cross_platform_bootstrap_contract.py
```

Expected: failure because the workflow file does not exist.

- [ ] **Step 3: Create the workflow**

The workflow must:

```yaml
name: SPINA Cross-Platform MVP

on:
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: spina-cross-platform-mvp-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true

jobs:
  cross-platform-mvp:
    runs-on: [self-hosted, Windows, X64]
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha || github.sha }}
          persist-credentials: false
      - name: Install backend
        shell: cmd
        run: |
          python -m venv "%RUNNER_TEMP%\spina-mvp-venv" || exit /b 1
          "%RUNNER_TEMP%\spina-mvp-venv\Scripts\python.exe" -m pip install -e ".\spina_backend_mobile" -e ".\gilbic_backend[test]" || exit /b 1
      - name: Test backend contracts
        shell: cmd
        run: "%RUNNER_TEMP%\spina-mvp-venv\Scripts\python.exe" -m pytest -q gilbic_backend\tests\test_cross_platform_bootstrap_contract.py
      - name: Bootstrap Flutter platforms
        shell: powershell
        run: .\gilbic_mobile\tool\bootstrap_platforms.ps1
      - name: Build Web
        working-directory: gilbic_mobile
        shell: cmd
        run: flutter build web --release --dart-define=GILBIC_API_URL=https://mvp-api.invalid || exit /b 1
      - name: Build Windows
        working-directory: gilbic_mobile
        shell: cmd
        run: flutter build windows --release --dart-define=GILBIC_API_URL=https://mvp-api.invalid || exit /b 1
      - name: Build Android debug APK
        working-directory: gilbic_mobile
        shell: cmd
        run: flutter build apk --debug --target-platform android-arm64,android-x64 --dart-define=GILBIC_API_URL=https://mvp-api.invalid || exit /b 1
      - name: Verify clean tree
        shell: cmd
        run: git diff --exit-code && git status --short
```

Persist build outputs under `C:\Users\Public\Documents\SPINA_MVP_BUILDS\${{ github.event.pull_request.head.sha || github.sha }}` before cleanup. Artifact upload may be `continue-on-error: true` because the repository currently has an artifact-storage quota issue; the build itself remains blocking.

- [ ] **Step 4: Run static test and open Draft PR**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q gilbic_backend\tests\test_cross_platform_bootstrap_contract.py
```

Expected: test passes. Push the exact commit and let the hosted workflow execute.

- [ ] **Step 5: Verify hosted evidence**

Expected exact-head results:

- backend layout contract passes;
- Flutter analyze reports no issues;
- complete Flutter suite passes;
- Web release build exits 0;
- Windows release build exits 0;
- Android debug APK exits 0 and contains arm64/x64;
- repository remains clean after generated-platform build.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/spina-cross-platform-mvp.yml gilbic_backend/tests/test_cross_platform_bootstrap_contract.py
git commit -m "ci: prove cross-platform MVP builds"
```

## Completion checkpoint

This plan is complete only when the exact branch head passes the focused policy/factory tests, complete Flutter suite, analyzer, Web build, Windows build, Android build, and static workflow contract. Native iOS compilation remains a separately recorded macOS/Xcode gate; shared Dart iOS behavior must still pass here.