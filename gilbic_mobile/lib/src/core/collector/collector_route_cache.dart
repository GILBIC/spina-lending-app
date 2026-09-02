import 'dart:convert';
import 'dart:math';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';

class CollectorRouteCacheSnapshot {
  const CollectorRouteCacheSnapshot({
    required this.route,
    required this.syncedAt,
  });

  final CollectorRoute route;
  final DateTime syncedAt;
}

abstract interface class CollectorRouteCache {
  Future<CollectorRouteCacheSnapshot?> readForUser(String userId);

  Future<void> writeForUser(
    String userId,
    CollectorRoute route,
    DateTime syncedAt,
  );

  Future<void> clearForUser(String userId);
}

class MemoryCollectorRouteCache implements CollectorRouteCache {
  final Map<String, CollectorRouteCacheSnapshot> _snapshots =
      <String, CollectorRouteCacheSnapshot>{};

  @override
  Future<void> clearForUser(String userId) async {
    _snapshots.remove(userId);
  }

  @override
  Future<CollectorRouteCacheSnapshot?> readForUser(String userId) async {
    return _snapshots[userId];
  }

  @override
  Future<void> writeForUser(
    String userId,
    CollectorRoute route,
    DateTime syncedAt,
  ) async {
    _snapshots[userId] = CollectorRouteCacheSnapshot(
      route: route,
      syncedAt: syncedAt,
    );
  }
}

abstract interface class RouteCacheKeyStore {
  Future<String> readOrCreateKey();
}

class SecureRouteCacheKeyStore implements RouteCacheKeyStore {
  SecureRouteCacheKeyStore({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  static const String _keyName = 'gilbic.route-cache.sqlcipher-key.v1';
  final FlutterSecureStorage _storage;

  @override
  Future<String> readOrCreateKey() async {
    final existing = await _storage.read(key: _keyName);
    if (existing != null && existing.isNotEmpty) {
      return existing;
    }

    final random = Random.secure();
    final bytes = List<int>.generate(32, (_) => random.nextInt(256));
    final created = base64UrlEncode(bytes);
    await _storage.write(key: _keyName, value: created);
    return created;
  }
}
