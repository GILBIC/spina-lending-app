import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_repository.dart';

class CollectorRouteLoadResult {
  const CollectorRouteLoadResult({
    required this.route,
    required this.syncedAt,
    required this.isFromCache,
    this.warning,
  });

  final CollectorRoute route;
  final DateTime syncedAt;
  final bool isFromCache;
  final String? warning;
}

abstract interface class CollectorRouteLoader {
  Future<CollectorRouteLoadResult> loadToday(UserSession session);
}

class CachedCollectorRouteLoader implements CollectorRouteLoader {
  CachedCollectorRouteLoader({
    required CollectorRouteRepository remote,
    required CollectorRouteCache cache,
    DateTime Function()? now,
  })  : _remote = remote,
        _cache = cache,
        _now = now ?? DateTime.now;

  final CollectorRouteRepository _remote;
  final CollectorRouteCache _cache;
  final DateTime Function() _now;

  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async {
    try {
      final route = await _remote.fetchToday(session);
      final syncedAt = _now().toUtc();
      String? warning;
      try {
        await _cache.writeForUser(session.userId, route, syncedAt);
      } on Object {
        warning = 'The route is online, but its offline copy could not be updated.';
      }
      return CollectorRouteLoadResult(
        route: route,
        syncedAt: syncedAt,
        isFromCache: false,
        warning: warning,
      );
    } on Object catch (remoteError, remoteStackTrace) {
      CollectorRouteCacheSnapshot? cached;
      try {
        cached = await _cache.readForUser(session.userId);
      } on Object {
        cached = null;
      }
      if (cached != null) {
        return CollectorRouteLoadResult(
          route: cached.route,
          syncedAt: cached.syncedAt,
          isFromCache: true,
          warning: 'Offline copy shown because the SPINA server could not be reached.',
        );
      }
      Error.throwWithStackTrace(remoteError, remoteStackTrace);
    }
  }
}
