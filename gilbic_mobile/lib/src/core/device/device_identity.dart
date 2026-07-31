import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:package_info_plus/package_info_plus.dart';

class DeviceIdentity {
  const DeviceIdentity({
    required this.installationId,
    required this.platform,
    required this.appVersion,
  });

  final String installationId;
  final String platform;
  final String appVersion;
}

abstract interface class DeviceIdentityStore {
  Future<String?> readInstallationId();

  Future<void> writeInstallationId(String value);
}

class SecureDeviceIdentityStore implements DeviceIdentityStore {
  SecureDeviceIdentityStore({FlutterSecureStorage? storage})
      : _storage = storage ?? FlutterSecureStorage();

  static const String _installationKey = 'gilbic.installation_id.v1';
  final FlutterSecureStorage _storage;

  @override
  Future<String?> readInstallationId() => _storage.read(key: _installationKey);

  @override
  Future<void> writeInstallationId(String value) {
    return _storage.write(key: _installationKey, value: value);
  }
}

class MemoryDeviceIdentityStore implements DeviceIdentityStore {
  String? value;

  @override
  Future<String?> readInstallationId() async => value;

  @override
  Future<void> writeInstallationId(String value) async {
    this.value = value;
  }
}

typedef PlatformResolver = String Function();
typedef AppVersionResolver = Future<String> Function();
typedef RandomByteGenerator = List<int> Function(int length);

class DeviceIdentityProvider {
  DeviceIdentityProvider({
    DeviceIdentityStore? store,
    PlatformResolver? platformResolver,
    AppVersionResolver? appVersionResolver,
    RandomByteGenerator? randomByteGenerator,
  })  : _store = store ?? SecureDeviceIdentityStore(),
        _platformResolver = platformResolver ?? _defaultPlatform,
        _appVersionResolver = appVersionResolver ?? _defaultAppVersion,
        _randomByteGenerator = randomByteGenerator ?? _secureRandomBytes;

  final DeviceIdentityStore _store;
  final PlatformResolver _platformResolver;
  final AppVersionResolver _appVersionResolver;
  final RandomByteGenerator _randomByteGenerator;

  Future<DeviceIdentity> load() async {
    var installationId = (await _store.readInstallationId())?.trim();
    if (installationId == null || installationId.isEmpty) {
      installationId = _newInstallationId();
      await _store.writeInstallationId(installationId);
    }

    return DeviceIdentity(
      installationId: installationId,
      platform: _platformResolver(),
      appVersion: await _appVersionResolver(),
    );
  }

  String _newInstallationId() {
    final bytes = _randomByteGenerator(24);
    final encoded = bytes
        .map((value) => value.toRadixString(16).padLeft(2, '0'))
        .join();
    return 'gilbic-$encoded';
  }

  static List<int> _secureRandomBytes(int length) {
    final random = Random.secure();
    return List<int>.generate(length, (_) => random.nextInt(256));
  }

  static String _defaultPlatform() {
    if (kIsWeb) {
      return 'web';
    }
    return switch (defaultTargetPlatform) {
      TargetPlatform.android => 'android',
      TargetPlatform.iOS => 'ios',
      _ => 'desktop',
    };
  }

  static Future<String> _defaultAppVersion() async {
    final package = await PackageInfo.fromPlatform();
    final version = package.version.trim();
    final build = package.buildNumber.trim();
    if (build.isEmpty) {
      return version;
    }
    return '$version+$build';
  }
}
