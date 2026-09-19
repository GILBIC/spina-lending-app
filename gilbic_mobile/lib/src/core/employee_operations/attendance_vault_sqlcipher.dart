import 'dart:convert';
import 'dart:math';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path/path.dart' as path;
import 'package:sqflite_sqlcipher/sqflite.dart';
import 'package:gilbic_mobile/src/core/employee_operations/attendance_outbox.dart';

class SqlCipherAttendanceVault implements AttendanceVault {
  SqlCipherAttendanceVault({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();
  final FlutterSecureStorage _storage;
  Future<Database>? _database;
  Future<Database> _open() =>
      _database ??= _create().catchError((Object error) {
        _database = null;
        throw error;
      });
  Future<Database> _create() async {
    const name = 'gilbic.attendance.sqlcipher-key.v1';
    var key = await _storage.read(key: name);
    if (key == null) {
      final random = Random.secure();
      key = base64UrlEncode(List.generate(32, (_) => random.nextInt(256)));
      await _storage.write(key: name, value: key);
    }
    return openDatabase(
      path.join(await getDatabasesPath(), 'gilbic_attendance.db'),
      password: key,
      version: 1,
      onCreate: (db, _) => db.execute(
        'CREATE TABLE attendance_outbox (binding TEXT PRIMARY KEY, payload TEXT NOT NULL)',
      ),
    );
  }

  Map<String, dynamic>? _decode(List<Map<String, Object?>> rows) => rows.isEmpty
      ? null
      : jsonDecode(rows.single['payload'] as String) as Map<String, dynamic>;
  @override
  Future<Map<String, dynamic>?> read(String key) async => _decode(
    await (await _open()).query(
      'attendance_outbox',
      where: 'binding = ?',
      whereArgs: [key],
      limit: 1,
    ),
  );
  @override
  Future<void> update(
    String key,
    Map<String, dynamic> Function(Map<String, dynamic>?) change,
  ) async {
    await (await _open()).transaction((tx) async {
      final rows = await tx.query(
        'attendance_outbox',
        where: 'binding = ?',
        whereArgs: [key],
        limit: 1,
      );
      final row = change(_decode(rows));
      await tx.insert('attendance_outbox', {
        'binding': key,
        'payload': jsonEncode(row),
      }, conflictAlgorithm: ConflictAlgorithm.replace);
    });
  }
}
