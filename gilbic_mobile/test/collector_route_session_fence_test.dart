import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache_sqlcipher.dart';
import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

const session = UserSession(
  userId: 'synthetic-collector',
  username: 'synthetic',
  displayName: 'Synthetic Collector',
  role: AppRole.collector,
  rawRole: 'collector',
  accessToken: 'synthetic-token',
  permissions: ['route.view', 'collection.post'],
  roles: ['collector', 'employee'],
);
CollectorRoute route() => CollectorRoute(
  routeDate: DateTime.utc(2026, 10, 6),
  collectorName: 'Synthetic Collector',
  areas: const ['Synthetic Area'],
  expectedTotal: 100,
  entries: const [
    CollectorRouteEntry(
      id: 'synthetic-entry',
      clientId: 'synthetic-client',
      loanId: 'synthetic-loan',
      clientName: 'Synthetic Borrower',
      area: 'Synthetic Area',
      loanType: 'Regular',
      dailyAmount: 100,
      balance: 900,
      status: 'Pending',
      passCount: 0,
    ),
  ],
);

class DelayedRemote implements CollectorRouteRepository {
  final calls = <Completer<CollectorRoute>>[];
  @override
  Future<CollectorRoute> fetchToday(UserSession session) {
    final result = Completer<CollectorRoute>();
    calls.add(result);
    return result.future;
  }
}

class OfflineRemote implements CollectorRouteRepository {
  @override
  Future<CollectorRoute> fetchToday(UserSession session) async =>
      throw const SpinaApiException(
        'Synthetic offline',
        code: 'network_unavailable',
      );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  for (final change in ['permission-loss', 'membership-loss']) {
    test(
      '$change continuation fences old fetch and same-user regrant',
      () async {
        final cache = MemoryCollectorRouteCache(), remote = DelayedRemote();
        final loader = CachedCollectorRouteLoader(remote: remote, cache: cache);
        final originalLease = cache.forSession(session);
        final alias = newSession();
        cache.continueSession(session, alias);
        final pending = loader.loadToday(alias);
        final revoked = change == 'permission-loss'
            ? newSession(permissions: const ['collection.post'])
            : newSession(roles: const ['collector']);
        cache.continueSession(alias, revoked);
        final rejected = expectLater(
          pending,
          throwsA(isA<SpinaApiException>()),
        );
        remote.calls.single.complete(route());
        await rejected;
        expect(originalLease.checkCurrent, throwsA(isA<SpinaApiException>()));
        final regranted = newSession();
        cache.continueSession(revoked, regranted);
        final offline = CachedCollectorRouteLoader(
          remote: OfflineRemote(),
          cache: cache,
        );
        await expectLater(
          offline.loadToday(regranted),
          throwsA(isA<SpinaApiException>()),
        );
        expect(await cache.readForUser(session.userId), isNull);
        final fresh = loader.loadToday(regranted);
        remote.calls.last.complete(route());
        await fresh;
        // A stale refresh or denial must not revoke the fresh authorization.
        cache.continueSession(alias, newSession());
        await cache.invalidateSession(alias);
        expect((await offline.loadToday(regranted)).isFromCache, isTrue);
      },
    );
  }

  test(
    'compatible verified continuation preserves authorized offline reads',
    () async {
      final cache = MemoryCollectorRouteCache(), remote = DelayedRemote();
      final pending = CachedCollectorRouteLoader(
        remote: remote,
        cache: cache,
      ).loadToday(session);
      remote.calls.single.complete(route());
      await pending;
      final refreshed = newSession(
        permissions: const ['collection.post', 'route.view'],
        roles: const ['employee', 'collector'],
        displayName: 'Updated cosmetic name',
      );
      cache.continueSession(session, refreshed);
      final offline = CachedCollectorRouteLoader(
        remote: OfflineRemote(),
        cache: cache,
      );
      expect((await offline.loadToday(refreshed)).isFromCache, isTrue);
      expect((await offline.loadToday(session)).isFromCache, isTrue);
      expect(await cache.readForUser(session.userId), isNotNull);
    },
  );

  test(
    'old cleanup finishes before a new same-actor write and cannot run again',
    () async {
      final cache = DelayedCleanupCache(), remote = DelayedRemote();
      final loader = CachedCollectorRouteLoader(remote: remote, cache: cache);
      final first = loader.loadToday(session);
      remote.calls.single.complete(route());
      await first;
      final cleanup = cache.invalidateSession(session);
      await cache.clearStarted.future;
      final next = newSession();
      final fresh = loader.loadToday(next);
      remote.calls.last.complete(route());
      await Future<void>.delayed(Duration.zero);
      cache.releaseClear.complete();
      await cleanup;
      await fresh;
      await cache.invalidateSession(session);
      expect(await cache.readForUser(session.userId), isNotNull);
      expect(
        (await CachedCollectorRouteLoader(
          remote: OfflineRemote(),
          cache: cache,
        ).loadToday(next)).isFromCache,
        isTrue,
      );
      await expectLater(
        loader.loadToday(session),
        throwsA(isA<SpinaApiException>()),
      );
    },
  );
  test('older denial cannot erase a new authorized same-actor route', () async {
    final cache = MemoryCollectorRouteCache(), remote = DelayedRemote();
    final loader = CachedCollectorRouteLoader(remote: remote, cache: cache);
    final old = loader.loadToday(session);
    final denied = expectLater(old, throwsA(isA<SpinaApiException>()));
    final fresh = loader.loadToday(newSession());
    remote.calls.last.complete(route());
    await fresh;
    remote.calls.first.completeError(
      const SpinaApiException('Denied', statusCode: 403),
    );
    await denied;
    expect(await cache.readForUser(session.userId), isNotNull);
  });

  for (final boundary in ['logout', 'replacement', 'permission-loss']) {
    test(
      'SQLCipher $boundary blocks offline fallback from delayed old insert',
      () async {
        FlutterSecureStorage.setMockInitialValues({});
        const channel = MethodChannel('com.davidmartos96.sqflite_sqlcipher');
        final rows = <String, Map<String, Object?>>{};
        final inserting = Completer<void>(), finishInsert = Completer<void>();
        var writes = 0, deletions = 0;
        var encrypted = false;
        TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
            .setMockMethodCallHandler(channel, (call) async {
              final args = call.arguments as Map? ?? {};
              switch (call.method) {
                case 'getDatabasesPath':
                  return 'C:/synthetic-route-cache';
                case 'openDatabase':
                  encrypted =
                      args['password'] is String &&
                      base64Url.decode(args['password'] as String).length == 32;
                  return 303;
                case 'query':
                  if (args['sql'] == 'PRAGMA user_version') {
                    return [
                      {'user_version': 1},
                    ];
                  }
                  final user = (args['arguments'] as List).first as String;
                  return rows.containsKey(user) ? [rows[user]] : [];
                case 'insert':
                  final values = args['arguments'] as List;
                  if (++writes == 1) {
                    inserting.complete();
                    await finishInsert.future;
                  }
                  rows[values[0] as String] = {
                    'synced_at': values[2],
                    'payload_json': values[3],
                  };
                  return 1;
                case 'update':
                  deletions++;
                  rows.remove((args['arguments'] as List).first);
                  return 1;
                default:
                  return null;
              }
            });
        addTearDown(
          () => TestDefaultBinaryMessengerBinding
              .instance
              .defaultBinaryMessenger
              .setMockMethodCallHandler(channel, null),
        );
        final cache = SqlCipherCollectorRouteCache(
              databaseName: 'session-fence-$boundary-test.db',
            ),
            remote = DelayedRemote();
        final loader = CachedCollectorRouteLoader(remote: remote, cache: cache);
        final old = loader.loadToday(session);
        remote.calls[0].complete(route());
        await inserting.future;
        final rejected = expectLater(old, throwsA(isA<SpinaApiException>()));
        final next = newSession();
        if (boundary == 'logout') {
          final cleanup = cache.invalidateSession(session);
          finishInsert.complete();
          await cleanup;
          await rejected;
        } else {
          if (boundary == 'permission-loss') {
            final revoked = newSession(permissions: const ['collection.post']);
            cache.continueSession(session, revoked);
            cache.continueSession(revoked, next);
          }
          // No explicit logout: replacement itself must revoke the old stored row
          // before the immediately offline replacement can fall back to it.
          final offline = CachedCollectorRouteLoader(
            remote: OfflineRemote(),
            cache: cache,
          ).loadToday(next);
          final blocked = expectLater(
            offline,
            throwsA(isA<SpinaApiException>()),
          );
          finishInsert.complete();
          await rejected;
          await blocked;
        }
        expect(await cache.readForUser(session.userId), isNull);
        expect(encrypted, isTrue);
        // Permission loss and regrant are two distinct authority boundaries.
        final expectedDeletions = boundary == 'permission-loss' ? 2 : 1;
        expect(deletions, expectedDeletions);
        final newer = loader.loadToday(next);
        remote.calls.last.complete(route());
        await newer;
        await cache.invalidateSession(session);
        expect(deletions, expectedDeletions);
        expect(await cache.readForUser(session.userId), isNotNull);
        expect(
          (await CachedCollectorRouteLoader(
            remote: OfflineRemote(),
            cache: cache,
          ).loadToday(next)).isFromCache,
          isTrue,
        );
      },
    );
  }

  test('logout during storage write cannot restore a snapshot', () async {
    final cache = DelayedCache(), remote = DelayedRemote();
    final loader = CachedCollectorRouteLoader(remote: remote, cache: cache);
    final pending = loader.loadToday(session);
    remote.calls.single.complete(route());
    await cache.writeStarted.future;
    final rejected = expectLater(pending, throwsA(isA<SpinaApiException>()));
    final cleanup = cache.invalidateSession(session);
    cache.releaseWrite.complete();
    await cleanup;
    await rejected;
    expect(await cache.readForUser(session.userId), isNull);
  });
  test('logout during fallback read cannot display captured data', () async {
    final cache = DelayedReadCache();
    await cache.writeForUser(session.userId, route(), DateTime.utc(2026));
    final pending = CachedCollectorRouteLoader(
      remote: OfflineRemote(),
      cache: cache,
    ).loadToday(session);
    await cache.readStarted.future;
    final rejected = expectLater(pending, throwsA(isA<SpinaApiException>()));
    final cleanup = cache.invalidateSession(session);
    cache.releaseRead.complete();
    await cleanup;
    await rejected;
  });

  test('logout fences a late remote route', () async {
    final cache = MemoryCollectorRouteCache(), remote = DelayedRemote();
    final loader = CachedCollectorRouteLoader(remote: remote, cache: cache);
    final pending = loader.loadToday(session);
    await cache.invalidateSession(session); // app.dart logout cleanup
    expect(await cache.readForUser(session.userId), isNull);
    final rejected = expectLater(pending, throwsA(isA<SpinaApiException>()));
    remote.calls.single.complete(route());
    await rejected;
    final restored = await cache.readForUser(session.userId);
    expect(restored, isNull);
  });
  test('denial fences older success and later offline fallback', () async {
    final cache = MemoryCollectorRouteCache(), remote = DelayedRemote();
    final loader = CachedCollectorRouteLoader(remote: remote, cache: cache);
    final old = loader.loadToday(session);
    final denied = loader.loadToday(session);
    final asserted = expectLater(denied, throwsA(isA<SpinaApiException>()));
    remote.calls[1].completeError(
      const SpinaApiException('Synthetic revoked', statusCode: 403),
    );
    await asserted;
    expect(await cache.readForUser(session.userId), isNull);
    final rejected = expectLater(old, throwsA(isA<SpinaApiException>()));
    remote.calls[0].complete(route());
    await rejected;
    await expectLater(
      CachedCollectorRouteLoader(
        remote: OfflineRemote(),
        cache: cache,
      ).loadToday(session),
      throwsA(isA<SpinaApiException>()),
    );
    expect(await cache.readForUser(session.userId), isNull);
  });
}

class DelayedCache extends MemoryCollectorRouteCache {
  final writeStarted = Completer<void>(), releaseWrite = Completer<void>();
  @override
  Future<void> writeForUser(
    String userId,
    CollectorRoute route,
    DateTime syncedAt,
  ) async {
    writeStarted.complete();
    await releaseWrite.future;
    await super.writeForUser(userId, route, syncedAt);
  }
}

class DelayedReadCache extends MemoryCollectorRouteCache {
  final readStarted = Completer<void>(), releaseRead = Completer<void>();
  @override
  Future<CollectorRouteCacheSnapshot?> readForUser(String userId) async {
    final result = await super.readForUser(userId);
    readStarted.complete();
    await releaseRead.future;
    return result;
  }
}

UserSession newSession({
  List<String> permissions = const ['route.view', 'collection.post'],
  List<String> roles = const ['collector', 'employee'],
  String? displayName,
}) => UserSession(
  userId: session.userId,
  username: session.username,
  displayName: displayName ?? session.displayName,
  role: session.role,
  rawRole: session.rawRole,
  accessToken: 'new-authorized-token',
  permissions: permissions,
  roles: roles,
);

class DelayedCleanupCache extends MemoryCollectorRouteCache {
  final clearStarted = Completer<void>(), releaseClear = Completer<void>();
  @override
  Future<void> clearForUser(String userId) async {
    clearStarted.complete();
    await releaseClear.future;
    await super.clearForUser(userId);
  }
}
