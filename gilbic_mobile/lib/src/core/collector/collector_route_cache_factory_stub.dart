import 'package:flutter/foundation.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache.dart';

CollectorRouteCache createPlatformCollectorRouteCache({
  required bool isWeb,
  required TargetPlatform platform,
}) => MemoryCollectorRouteCache();
