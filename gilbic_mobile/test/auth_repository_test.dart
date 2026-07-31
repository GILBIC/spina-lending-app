import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/auth_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('parses standard SPINA login response', () async {
    final client = MockClient((request) async {
      expect(request.method, 'POST');
      expect(request.url.path, '/login');
      expect(
        jsonDecode(request.body),
        <String, Object?>{
          'username': 'collector.one',
          'password': 'secret',
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
    );

    expect(
      () => repository.signIn(username: 'unknown', password: 'wrong'),
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
