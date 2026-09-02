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
