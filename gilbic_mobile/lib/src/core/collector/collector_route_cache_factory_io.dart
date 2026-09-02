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
