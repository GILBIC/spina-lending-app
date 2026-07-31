import 'package:gilbic_mobile/src/core/auth/user_session.dart';

abstract interface class SessionStore {
  Future<UserSession?> read();

  Future<void> write(UserSession session);

  Future<void> clear();
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
