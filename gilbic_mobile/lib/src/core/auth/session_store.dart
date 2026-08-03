import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';

abstract interface class SessionStore {
  Future<UserSession?> read();

  Future<void> write(UserSession session);

  Future<void> clear();
}

class SecureSessionStore implements SessionStore {
  SecureSessionStore({FlutterSecureStorage? storage})
      : _storage = storage ?? FlutterSecureStorage();

  static const String _sessionKey = 'gilbic.authenticated_session.v1';
  final FlutterSecureStorage _storage;

  @override
  Future<void> clear() => _storage.delete(key: _sessionKey);

  @override
  Future<UserSession?> read() async {
    final raw = await _storage.read(key: _sessionKey);
    if (raw == null || raw.trim().isEmpty) {
      return null;
    }

    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map) {
        await clear();
        return null;
      }
      final session = UserSession.fromJson(
        decoded.map((key, value) => MapEntry(key.toString(), value)),
      );
      if (session == null) {
        await clear();
        return null;
      }
      final refreshToken = session.refreshToken?.trim() ?? '';
      if (session.isExpired && refreshToken.isEmpty) {
        await clear();
        return null;
      }
      return session;
    } on FormatException {
      await clear();
      return null;
    }
  }

  @override
  Future<void> write(UserSession session) {
    return _storage.write(
      key: _sessionKey,
      value: jsonEncode(session.toJson()),
    );
  }
}

class MemorySessionStore implements SessionStore {
  UserSession? _session;

  @override
  Future<void> clear() async {
    _session = null;
  }

  @override
  Future<UserSession?> read() async => _session;

  @override
  Future<void> write(UserSession session) async {
    _session = session;
  }
}
