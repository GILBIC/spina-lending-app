import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/account/account_repository.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const _session = UserSession(
  userId: 'user-1',
  username: 'collector.one',
  displayName: 'Collector One',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'access-token',
  permissions: <String>['route.view', 'collection.create'],
);

DeviceIdentityProvider _identity() {
  return DeviceIdentityProvider(
    store: MemoryDeviceIdentityStore(),
    platformResolver: () => 'android',
    appVersionResolver: () async => '0.4.0+4',
    randomByteGenerator: (length) => List<int>.filled(length, 5),
  );
}

void main() {
  test('loads privacy-safe own profile and registered device state', () async {
    final repository = SpinaAccountRepository(
      accountUri: Uri.parse('https://spina.test/account'),
      deviceIdentityProvider: _identity(),
      client: MockClient((request) async {
        expect(request.method, 'GET');
        expect(request.url.path, '/account');
        expect(request.headers['Authorization'], 'Bearer access-token');
        expect(
          request.headers['X-Device-Id'],
          'gilbic-050505050505050505050505050505050505050505050505',
        );
        return http.Response(
          jsonEncode(<String, Object?>{
            'success': true,
            'data': <String, Object?>{
              'profile': <String, Object?>{
                'id': 'user-1',
                'username': 'collector.one',
                'email': 'collector@example.com',
                'full_name': 'Collector One',
                'role': 'Collector',
                'status': 'active',
              },
              'devices': <Object?>[
                <String, Object?>{
                  'id': 'device-current',
                  'platform': 'android',
                  'app_version': '0.4.0+4',
                  'status': 'active',
                  'registered_at': '2026-08-15T01:00:00Z',
                  'last_seen_at': '2026-08-15T02:00:00Z',
                  'is_current': true,
                },
                <String, Object?>{
                  'id': 'device-old',
                  'platform': 'ios',
                  'app_version': '0.3.0+3',
                  'status': 'active',
                  'registered_at': '2026-08-14T01:00:00Z',
                  'last_seen_at': null,
                  'is_current': false,
                },
              ],
            },
          }),
          200,
        );
      }),
    );

    final overview = await repository.fetch(_session);

    expect(overview.profile.fullName, 'Collector One');
    expect(overview.profile.email, 'collector@example.com');
    expect(overview.devices, hasLength(2));
    expect(overview.devices.first.isCurrent, isTrue);
    expect(overview.devices.last.platform, 'ios');
    expect(overview.devices.last.lastSeenAt, isNull);
  });

  test('revokes a selected owned device with the active installation header',
      () async {
    final repository = SpinaAccountRepository(
      accountUri: Uri.parse('https://spina.test/account'),
      deviceIdentityProvider: _identity(),
      client: MockClient((request) async {
        expect(request.method, 'POST');
        expect(
          request.url.path,
          '/api/mobile/v1/account/devices/device-old/revoke',
        );
        expect(request.headers['Authorization'], 'Bearer access-token');
        return http.Response(
          jsonEncode(<String, Object?>{
            'success': true,
            'data': <String, Object?>{
              'device': <String, Object?>{
                'id': 'device-old',
                'platform': 'ios',
                'app_version': '0.3.0+3',
                'status': 'revoked',
                'registered_at': '2026-08-14T01:00:00Z',
                'last_seen_at': '2026-08-14T02:00:00Z',
                'is_current': false,
              },
            },
          }),
          200,
        );
      }),
    );

    final device = await repository.revokeDevice(_session, 'device-old');

    expect(device.status, 'revoked');
    expect(device.isCurrent, isFalse);
  });

  test('changes own password through the protected canonical endpoint', () async {
    final repository = SpinaAccountRepository(
      accountUri: Uri.parse('https://spina.test/account'),
      deviceIdentityProvider: _identity(),
      client: MockClient((request) async {
        expect(request.method, 'PATCH');
        expect(request.url.path, '/api/v1/auth/password');
        expect(request.headers['Authorization'], 'Bearer access-token');
        expect(
          request.headers['X-Device-Id'],
          'gilbic-050505050505050505050505050505050505050505050505',
        );
        expect(request.headers['content-type'], contains('application/json'));
        expect(
          jsonDecode(request.body),
          <String, Object?>{'password': 'new-password-123'},
        );
        return http.Response(
          jsonEncode(<String, Object?>{'success': true}),
          200,
        );
      }),
    );

    await repository.changePassword(_session, 'new-password-123');
  });
}
