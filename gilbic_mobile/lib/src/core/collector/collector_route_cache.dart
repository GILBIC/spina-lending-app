import 'dart:convert';
import 'dart:math';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:path/path.dart' as path_helper;
import 'package:sqflite_sqlcipher/sqflite.dart';

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

class SqlCipherCollectorRouteCache implements CollectorRouteCache {
  SqlCipherCollectorRouteCache({
    RouteCacheKeyStore? keyStore,
    this.databaseName = 'gilbic_collector_routes.db',
  }) : _keyStore = keyStore ?? SecureRouteCacheKeyStore();

  static const String _table = 'collector_route_snapshots';

  final RouteCacheKeyStore _keyStore;
  final String databaseName;
  Database? _database;

  Future<Database> _open() async {
    final existing = _database;
    if (existing != null) {
      return existing;
    }

    final directory = await getDatabasesPath();
    final database = await openDatabase(
      path_helper.join(directory, databaseName),
      password: await _keyStore.readOrCreateKey(),
      version: 1,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE $_table (
            user_id TEXT PRIMARY KEY,
            route_date TEXT,
            synced_at TEXT NOT NULL,
            payload_json TEXT NOT NULL
          )
        ''');
      },
    );
    _database = database;
    return database;
  }

  @override
  Future<void> clearForUser(String userId) async {
    final database = await _open();
    await database.delete(
      _table,
      where: 'user_id = ?',
      whereArgs: <Object?>[userId],
    );
  }

  @override
  Future<CollectorRouteCacheSnapshot?> readForUser(String userId) async {
    final database = await _open();
    final rows = await database.query(
      _table,
      columns: const <String>['payload_json', 'synced_at'],
      where: 'user_id = ?',
      whereArgs: <Object?>[userId],
      limit: 1,
    );
    if (rows.isEmpty) {
      return null;
    }

    final row = rows.first;
    final payload = row['payload_json'];
    final syncedAt = row['synced_at'];
    if (payload is! String || syncedAt is! String) {
      throw const FormatException('The saved route cache is incomplete.');
    }

    return CollectorRouteCacheSnapshot(
      route: CollectorRoute.fromPayload(jsonDecode(payload)),
      syncedAt: DateTime.parse(syncedAt),
    );
  }

  @override
  Future<void> writeForUser(
    String userId,
    CollectorRoute route,
    DateTime syncedAt,
  ) async {
    final database = await _open();
    await database.insert(
      _table,
      <String, Object?>{
        'user_id': userId,
        'route_date': route.routeDate?.toIso8601String(),
        'synced_at': syncedAt.toUtc().toIso8601String(),
        'payload_json': jsonEncode(route.toJson()),
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }
}
