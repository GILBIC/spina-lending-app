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
