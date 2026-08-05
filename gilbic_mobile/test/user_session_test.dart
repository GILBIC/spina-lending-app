import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';

void main() {
  test('serializes and restores an authenticated session', () {
    final expiry = DateTime.utc(2030, 1, 2, 3, 4, 5);
    final original = UserSession(
      userId: '42',
      username: 'collector.one',
      displayName: 'Collector One',
      role: AppRole.collector,
      rawRole: 'Collector',
      accessToken: 'access-token',
      refreshToken: 'refresh-token',
      permissions: const <String>['route.view'],
      expiresAt: expiry,
    );

    final restored = UserSession.fromJson(original.toJson());

    expect(restored, isNotNull);
    expect(restored!.userId, original.userId);
    expect(restored.username, original.username);
    expect(restored.role, AppRole.collector);
    expect(restored.accessToken, original.accessToken);
    expect(restored.refreshToken, original.refreshToken);
    expect(restored.permissions, original.permissions);
    expect(restored.expiresAt, expiry);
  });

  test('open screens see refreshed tokens through the same session object', () {
    final expiry = DateTime.utc(2030, 1, 2, 3, 4, 5);
    const current = UserSession(
      userId: 'collector-refresh-test',
      username: 'collector.one',
      displayName: 'Collector One',
      role: AppRole.collector,
      rawRole: 'Collector',
      accessToken: 'access-old',
      refreshToken: 'refresh-old',
    );
    final refreshed = UserSession(
      userId: 'collector-refresh-test',
      username: 'collector.one',
      displayName: 'Collector One',
      role: AppRole.collector,
      rawRole: 'Collector',
      accessToken: 'access-new',
      refreshToken: 'refresh-new',
      expiresAt: expiry,
    );

    current.applyRefresh(refreshed);

    expect(current.accessToken, 'access-new');
    expect(current.refreshToken, 'refresh-new');
    expect(current.expiresAt, expiry);
    expect(current.toJson()['access_token'], 'access-new');

    current.clearRefreshOverride();
    expect(current.accessToken, 'access-old');
  });

  test('rejects incomplete secure-session data', () {
    expect(
      UserSession.fromJson(<String, Object?>{
        'user_id': '42',
        'username': 'collector.one',
        'role': 'Collector',
      }),
      isNull,
    );
  });
}
