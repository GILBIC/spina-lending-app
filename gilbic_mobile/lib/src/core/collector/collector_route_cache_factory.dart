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
