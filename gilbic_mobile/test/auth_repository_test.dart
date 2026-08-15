import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/auth_repository.dart';
import 'package:gilbic_mobile/src/core/auth/client_registration.dart';
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
  test('submits a pending client registration claim', () async {
    final client = MockClient((request) async {
      expect(request.method, 'POST');
      expect(request.url.path, '/register');
      expect(
        jsonDecode(request.body),
        <String, Object?>{
          'full_name': 'Client One',
          'client_code': 'CLIENT-001',
          'phone_number': '09171234567',
          'email': 'client@example.com',
          'username': 'client.one',
          'password': 'strong-pass-123',
        },
      );
      return http.Response(
        jsonEncode(<String, Object?>{
          'success': true,
          'data': <String, Object?>{
            'requires_email_confirmation': true,
            'approval_status': 'pending',
            'message': 'Wait for Management approval.',
          },
        }),
        201,
      );
    });
    final repository = SpinaAuthRepository(
      client: client,
      registerUri: Uri.parse('https://spina.test/register'),
      loginUri: Uri.parse('https://spina.test/login'),
      logoutUri: Uri.parse('https://spina.test/logout'),
      deviceIdentityProvider: testDeviceIdentityProvider(),
    );

    final result = await repository.registerClient(
      const ClientRegistrationDraft(
        fullName: ' Client One ',
        clientCode: ' CLIENT-001 ',
        phoneNumber: ' 09171234567 ',
        email: ' CLIENT@EXAMPLE.COM ',
        username: ' client.one ',
        password: 'strong-pass-123',
      ),
    );

    expect(result.approvalStatus, 'pending');
    expect(result.requiresEmailConfirmation, isTrue);
    expect(result.message, 'Wait for Management approval.');
  });

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

  test('revalidates server role and permission scope on active device', () async {
    final expiry = DateTime.utc(2030, 1, 2, 3, 4, 5);
    final client = MockClient((request) async {
      expect(request.method, 'GET');
      expect(request.url.path, '/me');
      expect(request.headers['Authorization'], 'Bearer access-current');
      expect(
        request.headers['X-Device-Id'],
        'gilbic-070707070707070707070707070707070707070707070707',
      );
      return http.Response(
        jsonEncode(<String, Object?>{
          'success': true,
          'data': <String, Object?>{
            'user': <String, Object?>{
              'id': 'user-1',
              'username': 'staff.one',
              'full_name': 'Staff One',
              'role': 'employee',
              'permissions': <String>['payroll.view', 'attendance.view'],
            },
          },
        }),
        200,
        headers: <String, String>{'content-type': 'application/json'},
      );
    });
    final repository = SpinaAuthRepository(
      client: client,
      meUri: Uri.parse('https://spina.test/me'),
      deviceIdentityProvider: testDeviceIdentityProvider(),
    );
    final current = UserSession(
      userId: 'user-1',
      username: 'staff.one',
      displayName: 'Staff One',
      role: AppRole.collector,
      rawRole: 'collector',
      accessToken: 'access-current',
      refreshToken: 'refresh-current',
      permissions: const <String>['route.view'],
      expiresAt: expiry,
    );

    final validated = await repository.validate(current);

    expect(validated.userId, 'user-1');
    expect(validated.role, AppRole.employee);
    expect(validated.rawRole, 'employee');
    expect(
      validated.permissions,
      <String>['payroll.view', 'attendance.view'],
    );
    expect(validated.accessToken, 'access-current');
    expect(validated.refreshToken, 'refresh-current');
    expect(validated.expiresAt, expiry);
  });

  test('surfaces revoked-device denial during active session validation', () async {
    final repository = SpinaAuthRepository(
      client: MockClient((request) async {
        expect(request.method, 'GET');
        expect(request.url.path, '/me');
        return http.Response(
          jsonEncode(<String, Object?>{
            'detail': 'This device has been revoked.',
          }),
          403,
        );
      }),
      meUri: Uri.parse('https://spina.test/me'),
      deviceIdentityProvider: testDeviceIdentityProvider(),
    );
    const current = UserSession(
      userId: 'collector-1',
      username: 'collector.one',
      displayName: 'Collector One',
      role: AppRole.collector,
      rawRole: 'collector',
      accessToken: 'access-current',
      permissions: <String>['route.view'],
    );

    await expectLater(
      repository.validate(current),
      throwsA(
        isA<SpinaApiException>()
            .having((error) => error.statusCode, 'statusCode', 403)
            .having(
              (error) => error.message,
              'message',
              'This device has been revoked.',
            ),
      ),
    );
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

  test('shows the server pending-approval message on forbidden login', () async {
    final repository = SpinaAuthRepository(
      client: MockClient((request) async {
        return http.Response(
          jsonEncode(<String, Object?>{
            'detail':
                'Your client account is awaiting Management approval and borrower linking.',
          }),
          403,
        );
      }),
      loginUri: Uri.parse('https://spina.test/login'),
      logoutUri: Uri.parse('https://spina.test/logout'),
      deviceIdentityProvider: testDeviceIdentityProvider(),
    );

    await expectLater(
      repository.signIn(username: 'client.one', password: 'secret'),
      throwsA(
        isA<SpinaApiException>().having(
          (error) => error.message,
          'message',
          'Your client account is awaiting Management approval and borrower linking.',
        ),
      ),
    );
  });
}
