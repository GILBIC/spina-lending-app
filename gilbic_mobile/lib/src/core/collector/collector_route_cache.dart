import 'dart:async';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
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

// The interface above is the storage boundary. Session users must use these
// leases so invalidation and storage completion share one ordering domain.
extension CollectorRouteCacheSessions on CollectorRouteCache {
  CollectorRouteCacheSession forSession(UserSession session) =>
      _routeCacheFence(this).forSession(session);

  // Only equivalent verified authority preserves mounted pages' lifetime.
  void continueSession(UserSession previous, UserSession refreshed) =>
      _routeCacheFence(this).continueSession(previous, refreshed);

  // Invalidates synchronously, before the first asynchronous storage operation.
  Future<void> invalidateSession(UserSession session) =>
      _routeCacheFence(this).invalidateSession(session);
}

final _routeCacheFences = Expando<_CollectorRouteCacheFence>();
_CollectorRouteCacheFence _routeCacheFence(CollectorRouteCache cache) =>
    _routeCacheFences[cache] ??= _CollectorRouteCacheFence(cache);

class _CollectorRouteCacheFence {
  _CollectorRouteCacheFence(this.storage);
  final CollectorRouteCache storage;
  final _sessions = Expando<CollectorRouteCacheSession>();
  final _current = <String, CollectorRouteCacheSession>{};
  final _unreadable = <String>{};
  Future<void> _work = Future<void>.value();

  CollectorRouteCacheSession forSession(UserSession session) {
    final known = _sessions[session];
    if (known != null) return known;
    final lease = CollectorRouteCacheSession._(this, session.userId);
    final previous = _current[session.userId];
    if (previous != null) {
      // Replacement is a revocation boundary even without an explicit logout.
      // Mark unreadable synchronously and queue cleanup before publishing the
      // replacement, whose storage operations must run after that cleanup.
      unawaited(_invalidate(previous).catchError((Object _) {}));
    }
    _current[session.userId] = lease;
    _sessions[session] = lease;
    return lease;
  }

  void continueSession(UserSession previous, UserSession refreshed) {
    final lease =
        _sessions[previous] ??
        (_current[previous.userId] == null ? forSession(previous) : null);
    // A late refresh from an old alias cannot replace current authority.
    if (lease == null ||
        !lease._valid ||
        !identical(_current[previous.userId], lease)) {
      return;
    }
    if (previous.authorizationScopeKey == refreshed.authorizationScopeKey) {
      _sessions[refreshed] = lease;
    } else {
      // Known permission/membership changes revoke before any async work.
      // Reuse replacement ordering so a delayed old write is then deleted.
      unawaited(_invalidate(lease).catchError((Object _) {}));
      forSession(refreshed);
    }
  }

  Future<T> ordered<T>(Future<T> Function() action) {
    final operation = _work.then((_) => action());
    _work = operation.then<void>((_) {}, onError: (Object _, StackTrace __) {});
    return operation;
  }

  Future<void> invalidateSession(UserSession session) {
    final known = _sessions[session];
    final current = _current[session.userId];
    // An old logout/denial cannot clear a newly authorized session for this user.
    if (current != null && !identical(current, known)) return Future.value();
    return _invalidate(known ?? forSession(session));
  }

  Future<void> _invalidate(CollectorRouteCacheSession lease) {
    if (!lease._valid) return Future.value();
    lease._valid = false;
    _unreadable.add(lease._userId);
    // A write already at the platform boundary finishes before this deletion;
    // new-session writes queue after it, so old cleanup cannot erase them.
    return ordered(() => storage.clearForUser(lease._userId));
  }
}

class CollectorRouteCacheSession {
  CollectorRouteCacheSession._(this._fence, this._userId);
  final _CollectorRouteCacheFence _fence;
  final String _userId;
  bool _valid = true;

  void checkCurrent() {
    if (!_valid || !identical(_fence._current[_userId], this)) {
      throw const SpinaApiException(
        'This route session is no longer authorized. Sign in again.',
        statusCode: 403,
        code: 'route_context_lost',
      );
    }
  }

  Future<void> write(CollectorRoute route, DateTime syncedAt) =>
      _fence.ordered(() async {
        checkCurrent();
        await _fence.storage.writeForUser(_userId, route, syncedAt);
        checkCurrent();
        _fence._unreadable.remove(_userId);
      });

  Future<CollectorRouteCacheSnapshot?> read() => _fence.ordered(() async {
    checkCurrent();
    if (_fence._unreadable.contains(_userId)) return null;
    final snapshot = await _fence.storage.readForUser(_userId);
    checkCurrent();
    return snapshot;
  });
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
