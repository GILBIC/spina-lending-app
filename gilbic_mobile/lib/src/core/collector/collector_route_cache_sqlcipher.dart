import 'dart:convert';

import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache.dart';
import 'package:path/path.dart' as path_helper;
import 'package:sqflite_sqlcipher/sqflite.dart';

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
