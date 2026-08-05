import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/auth_repository.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

DeviceIdentityProvider testDeviceIdentityProvider() {
  return DeviceIdentityProvider(
    store: MemoryDeviceIdentityStore(),
    platformResolver: () => 'android',
    appVersionResolver: () async => '0.4.0+4',
    randomByteGenerator: (length) => List<int>.filled(length, 7),
  );
}

void main() {
  test('parses standard SPINA login response and sends device identity', () async {
    final client = MockClient((request) async {
      expect(request.method, 'POST');
      expect(request.url.path, '/login');
      expect(
        jsonDecode(request.body),
        <String, Object?>{
          'username': 'collector.one',
          'password': 'secret',
          'device_id':
              'gilbic-070707070707070707070707070707070707070707070707',
          'platform': 'android',
          'app_version': '0.4.0+4',
        },
      );
      return http.Response(
        jsonEncode(<String, Object?>{
          'success': true,
          'data': <String, Object?>{
            'access_token': 'token-123',
            'refresh_token': 'refresh-123',
            'user': <String, Object?>{
              'account_id': 42,
              'username': 'collector.one',
              'full_name': 'Collector One',
              'role': 'Collector',
              'permissions': <String>['route.view'],
            },
          },
        }),
        200,
        headers: <String, String>{'content-type': 'application/json'},
      );
    });
    final repository = SpinaAuthRepository(
      client: client,
      loginUri: Uri.parse('https://spina.test/login'),
      logoutUri: Uri.parse('https://spina.test/logout'),
      deviceIdentityProvider: testDeviceIdentityProvider(),
    );

    final session = await repository.signIn(
      username: 'collector.one',
      password: 'secret',
    );

    expect(session.userId, '42');
    expect(session.displayName, 'Collector One');
    expect(session.role, AppRole.collector);
    expect(session.accessToken, 'token-123');
    expect(session.permissions, <String>['route.view']);
  });

  test('refreshes a session with its registered installation identity', () async {
    final expiry = DateTime.utc(2030, 1, 2, 3, 4, 5);
    final client = MockClient((request) async {
      expect(request.method, 'POST');
      expect(request.url.path, '/refresh');
      expect(
        request.headers['X-Device-Id'],
        'gilbic-070707070707070707070707070707070707070707070707',
      );
      expect(
        jsonDecode(request.body),
        <String, Object?>{'refresh_token': 'refresh-old'},
      );
      return http.Response(
        jsonEncode(<String, Object?>{
          'success': true,
          'data': <String, Object?>{
            'access_token': 'access-new',
            'refresh_token': 'refresh-new',
            'expires_at': expiry.toIso8601String(),
            'user': <String, Object?>{
              'id': 'collector-1',
              'username': 'collector.one',
              'full_name': 'Collector One',
              'role': 'Collector',
              'permissions': <String>['route.view', 'collection.create'],
            },
          },
        }),
        200,
        headers: <String, String>{'content-type': 'application/json'},
      );
    });
    final repository = SpinaAuthRepository(
      client: client,
      loginUri: Uri.parse('https://spina.test/login'),
      refreshUri: Uri.parse('https://spina.test/refresh'),
      logoutUri: Uri.parse('https://spina.test/logout'),
      deviceIdentityProvider: testDeviceIdentityProvider(),
    );
    const current = UserSession(
      userId: 'collector-1',
      username: 'collector.one',
      displayName: 'Collector One',
      role: AppRole.collector,
      rawRole: 'Collector',
      accessToken: 'access-old',
      refreshToken: 'refresh-old',
      permissions: <String>['route.view', 'collection.create'],
    );

    final refreshed = await repository.refresh(current);

    expect(refreshed.userId, 'collector-1');
    expect(refreshed.accessToken, 'access-new');
    expect(refreshed.refreshToken, 'refresh-new');
    expect(refreshed.expiresAt, expiry);
  });

  test('supports legacy direct session response', () async {
    final repository = SpinaAuthRepository(
      client: MockClient((request) async {
        return http.Response(
          jsonEncode(<String, Object?>{
            'session_id': 'legacy-session',
            'account_id': 7,
            'username': 'manager.one',
            'full_name': 'Manager One',
            'role': 'Manager',
          }),
          200,
        );
      }),
      loginUri: Uri.parse('https://spina.test/login'),
      logoutUri: Uri.parse('https://spina.test/logout'),
      deviceIdentityProvider: testDeviceIdentityProvider(),
    );

    final session = await repository.signIn(
      username: 'manager.one',
      password: 'secret',
    );

    expect(session.role, AppRole.management);
    expect(session.accessToken, 'legacy-session');
  });

  test('returns a generic authentication failure', () async {
    final repository = SpinaAuthRepository(
      client: MockClient((request) async {
        return http.Response(
          jsonEncode(<String, Object?>{
            'success': false,
            'message': 'Invalid username or password.',
          }),
          401,
        );
      }),
      loginUri: Uri.parse('https://spina.test/login'),
      logoutUri: Uri.parse('https://spina.test/logout'),
      deviceIdentityProvider: testDeviceIdentityProvider(),
    );

    await expectLater(
      repository.signIn(username: 'unknown', password: 'wrong'),
      throwsA(
        isA<SpinaApiException>().having(
          (error) => error.message,
          'message',
          'Invalid username or password.',
        ),
      ),
    );
  });
}
