import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

void main() {
  const session = UserSession(
    userId: 'collector-1',
    username: 'collector.one',
    displayName: 'Collector One',
    role: AppRole.collector,
    rawRole: 'Collector',
    accessToken: 'token',
  );

  test('downloads and caches a fresh route', () async {
    final cache = MemoryCollectorRouteCache();
    final now = DateTime.utc(2026, 7, 31, 5, 15);
    final loader = CachedCollectorRouteLoader(
      remote: _RouteRepository(_route('Fresh Client')),
      cache: cache,
      now: () => now,
    );

    final result = await loader.loadToday(session);

    expect(result.isFromCache, isFalse);
    expect(result.syncedAt, now);
    expect(result.route.entries.single.clientName, 'Fresh Client');
    expect(result.warning, isNull);
    expect(
      (await cache.readForUser(session.userId))?.route.entries.single.clientName,
      'Fresh Client',
    );
  });

  test('uses the encrypted-cache boundary when the server is offline', () async {
    final cache = MemoryCollectorRouteCache();
    final savedAt = DateTime.utc(2026, 7, 31, 4, 45);
    await cache.writeForUser(session.userId, _route('Cached Client'), savedAt);
    final loader = CachedCollectorRouteLoader(
      remote: _FailingRouteRepository(),
      cache: cache,
    );

    final result = await loader.loadToday(session);

    expect(result.isFromCache, isTrue);
    expect(result.syncedAt, savedAt);
    expect(result.route.entries.single.clientName, 'Cached Client');
    expect(result.warning, contains('Offline copy'));
  });

  test('rethrows the server failure when no cache exists', () async {
    final loader = CachedCollectorRouteLoader(
      remote: _FailingRouteRepository(),
      cache: MemoryCollectorRouteCache(),
    );

    expect(
      () => loader.loadToday(session),
      throwsA(isA<SpinaApiException>()),
    );
  });

  test('still shows a live route when cache storage fails', () async {
    final loader = CachedCollectorRouteLoader(
      remote: _RouteRepository(_route('Online Client')),
      cache: _WriteFailingCache(),
    );

    final result = await loader.loadToday(session);

    expect(result.isFromCache, isFalse);
    expect(result.route.entries.single.clientName, 'Online Client');
    expect(result.warning, contains('offline copy could not be updated'));
  });
}

class _RouteRepository implements CollectorRouteRepository {
  _RouteRepository(this.route);

  final CollectorRoute route;

  @override
  Future<CollectorRoute> fetchToday(UserSession session) async => route;
}

class _FailingRouteRepository implements CollectorRouteRepository {
  @override
  Future<CollectorRoute> fetchToday(UserSession session) async {
    throw const SpinaApiException('Server unavailable');
  }
}

class _WriteFailingCache implements CollectorRouteCache {
  @override
  Future<void> clearForUser(String userId) async {}

  @override
  Future<CollectorRouteCacheSnapshot?> readForUser(String userId) async => null;

  @override
  Future<void> writeForUser(
    String userId,
    CollectorRoute route,
    DateTime syncedAt,
  ) async {
    throw StateError('disk unavailable');
  }
}

CollectorRoute _route(String clientName) {
  return CollectorRoute(
    routeDate: DateTime.utc(2026, 7, 31),
    collectorName: 'Collector One',
    areas: const <String>['Cardona'],
    expectedTotal: 200,
    entries: <CollectorRouteEntry>[
      CollectorRouteEntry(
        id: 'entry-1',
        clientId: 'client-1',
        loanId: 'loan-1',
        clientName: clientName,
        area: 'Cardona',
        loanType: 'Regular',
        dailyAmount: 200,
        balance: 4800,
        status: 'Pending',
        passCount: 0,
      ),
    ],
  );
}
