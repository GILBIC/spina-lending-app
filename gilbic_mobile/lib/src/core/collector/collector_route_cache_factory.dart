import 'package:flutter/foundation.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache_factory_stub.dart'
    if (dart.library.io) 'collector_route_cache_factory_io.dart' as implementation;

CollectorRouteCache createDefaultCollectorRouteCache({
  bool? isWeb,
  TargetPlatform? platform,
}) {
  return implementation.createPlatformCollectorRouteCache(
    isWeb: isWeb ?? kIsWeb,
    platform: platform ?? defaultTargetPlatform,
  );
}
