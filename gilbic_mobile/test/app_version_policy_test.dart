import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/auth_repository.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

DeviceIdentityProvider _deviceIdentity() {
  return DeviceIdentityProvider(
    store: MemoryDeviceIdentityStore(),
    platformResolver: () => 'android',
    appVersionResolver: () async => '0.4.0+4',
    randomByteGenerator: (length) => List<int>.filled(length, 9),
  );
}

const UserSession _session = UserSession(
  userId: 'collector-1',
  username: 'collector.one',
  displayName: 'Collector One',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'access-current',
  refreshToken: 'refresh-current',
  permissions: <String>['route.view', 'collection.create'],
);

void main() {
  test('refresh sends platform/version and surfaces required update', () async {
    final repository = SpinaAuthRepository(
      client: MockClient((request) async {
        expect(request.method, 'POST');
        expect(request.url.path, '/refresh');
        expect(request.headers['X-App-Platform'], 'android');
        expect(request.headers['X-App-Version'], '0.4.0+4');
        expect(jsonDecode(request.body), <String, Object?>{
          'refresh_token': 'refresh-current',
        });
        return http.Response(
          jsonEncode(<String, Object?>{
            'detail':
                'This Gilbic Android version is no longer supported. Update to version 0.5.0+5 or later before continuing.',
          }),
          426,
        );
      }),
      refreshUri: Uri.parse('https://spina.test/refresh'),
      deviceIdentityProvider: _deviceIdentity(),
    );

    await expectLater(
      repository.refresh(_session),
      throwsA(
        isA<SpinaApiException>()
            .having((error) => error.statusCode, 'statusCode', 426)
            .having(
              (error) => error.message,
              'message',
              contains('Update to version 0.5.0+5'),
            ),
      ),
    );
  });

  test('active session validation sends platform/version metadata', () async {
    final repository = SpinaAuthRepository(
      client: MockClient((request) async {
        expect(request.method, 'GET');
        expect(request.url.path, '/me');
        expect(request.headers['Authorization'], 'Bearer access-current');
        expect(request.headers['X-App-Platform'], 'android');
        expect(request.headers['X-App-Version'], '0.4.0+4');
        return http.Response(
          jsonEncode(<String, Object?>{
            'detail':
                'This Gilbic Android version is no longer supported. Update to version 0.5.0+5 or later before continuing.',
          }),
          426,
        );
      }),
      meUri: Uri.parse('https://spina.test/me'),
      deviceIdentityProvider: _deviceIdentity(),
    );

    await expectLater(
      repository.validate(_session),
      throwsA(
        isA<SpinaApiException>()
            .having((error) => error.statusCode, 'statusCode', 426)
            .having(
              (error) => error.message,
              'message',
              contains('no longer supported'),
            ),
      ),
    );
  });
}
