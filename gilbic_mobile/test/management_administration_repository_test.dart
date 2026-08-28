import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/management_administration_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('uses the protected contract for every staff administration call', () async {
    final requests = <http.Request>[];
    final repository = SpinaManagementAdministrationRepository(
      client: MockClient((request) async {
        requests.add(request);
        expect(request.headers['authorization'], 'Bearer access-token');
        expect(request.headers['x-device-id'], 'management-phone');
        expect(request.headers['x-session-id'], isNull);

        if (request.method == 'GET' &&
            request.url.path == '/api/v1/management/accounts') {
          return _jsonResponse(<String, Object?>{
            'accounts': <Object?>[_staffPayload],
          });
        }
        if (request.method == 'POST' &&
            request.url.path == '/api/v1/management/accounts/invite') {
          final body = jsonDecode(request.body) as Map<String, dynamic>;
          expect(body, <String, Object?>{
            'username': 'collector.one',
            'email': 'collector@example.com',
            'full_name': 'Collector One',
            'role': 'collector',
          });
          expect(body.containsKey('password'), isFalse);
          return _jsonResponse(<String, Object?>{
            'invitation_sent': true,
            'account': _staffPayload,
          }, statusCode: 201);
        }
        if (request.method == 'PATCH' &&
            request.url.path ==
                '/api/v1/management/accounts/11111111-1111-4111-8111-111111111111/role') {
          expect(jsonDecode(request.body), <String, Object?>{
            'role': 'employee',
          });
          return _jsonResponse(<String, Object?>{
            'account': <String, Object?>{
              ..._staffPayload,
              'roles': <Object?>['employee'],
            },
          });
        }
        if (request.method == 'PATCH' &&
            request.url.path ==
                '/api/v1/management/accounts/11111111-1111-4111-8111-111111111111/status') {
          expect(jsonDecode(request.body), <String, Object?>{
            'status': 'inactive',
          });
          return _jsonResponse(<String, Object?>{
            'account': <String, Object?>{
              ..._staffPayload,
              'status': 'inactive',
            },
          });
        }
        if (request.method == 'GET' &&
            request.url.path ==
                '/api/v1/management/accounts/11111111-1111-4111-8111-111111111111/devices') {
          return _jsonResponse(<String, Object?>{
            'devices': <Object?>[_devicePayload],
          });
        }
        if (request.method == 'PATCH' &&
            request.url.path ==
                '/api/v1/management/devices/22222222-2222-4222-8222-222222222222/status') {
          expect(jsonDecode(request.body), <String, Object?>{
            'status': 'active',
          });
          return _jsonResponse(<String, Object?>{
            'device': <String, Object?>{..._devicePayload, 'status': 'active'},
          });
        }
        fail('Unexpected request: ${request.method} ${request.url}');
      }),
    );

    final page = await repository.loadStaff(
      _session,
      deviceId: 'management-phone',
      query: '  Ana+West  ',
      role: 'collector',
      status: 'active',
      limit: 25,
      offset: 50,
    );
    final invited = await repository.inviteStaff(
      _session,
      deviceId: 'management-phone',
      username: ' collector.one ',
      email: ' Collector@Example.com ',
      fullName: ' Collector One ',
      role: 'collector',
    );
    final roleChanged = await repository.setRole(
      _session,
      deviceId: 'management-phone',
      userId: '11111111-1111-4111-8111-111111111111',
      role: 'employee',
    );
    final statusChanged = await repository.setAccountStatus(
      _session,
      deviceId: 'management-phone',
      userId: '11111111-1111-4111-8111-111111111111',
      status: 'inactive',
    );
    final devices = await repository.loadDevices(
      _session,
      deviceId: 'management-phone',
      userId: '11111111-1111-4111-8111-111111111111',
    );
    final deviceChanged = await repository.setDeviceStatus(
      _session,
      deviceId: 'management-phone',
      userId: '11111111-1111-4111-8111-111111111111',
      managedDeviceId: '22222222-2222-4222-8222-222222222222',
      status: 'active',
    );

    final search = requests.first.url.queryParameters;
    expect(search, <String, String>{
      'staff_only': 'true',
      'limit': '25',
      'offset': '50',
      'q': 'Ana+West',
      'role': 'collector',
      'status': 'active',
    });
    expect(page.items.single.id, '11111111-1111-4111-8111-111111111111');
    expect(page.nextOffset, 51);
    expect(page.hasMore, isFalse);
    expect(invited.email, 'collector@example.com');
    expect(roleChanged.roles, <String>['employee']);
    expect(statusChanged.status, 'inactive');
    expect(devices.single.id, '22222222-2222-4222-8222-222222222222');
    expect(deviceChanged.status, 'active');
    expect(requests, hasLength(6));
  });

  test('rejects the Client role before invitation network I/O', () async {
    var requests = 0;
    final repository = SpinaManagementAdministrationRepository(
      client: MockClient((request) async {
        requests += 1;
        return _jsonResponse(const <String, Object?>{});
      }),
    );

    await expectLater(
      repository.inviteStaff(
        _session,
        deviceId: 'management-phone',
        username: 'client.one',
        email: 'client@example.com',
        fullName: 'Client One',
        role: 'client',
      ),
      throwsA(isA<ArgumentError>()),
    );
    expect(requests, 0);
  });

  for (final invalid in <String, Map<String, Object?>>{
    'UUID': <String, Object?>{..._staffPayload, 'id': 'not-a-uuid'},
    'role': <String, Object?>{
      ..._staffPayload,
      'roles': <Object?>['client'],
    },
    'status': <String, Object?>{..._staffPayload, 'status': 'deleted'},
    'timestamp': <String, Object?>{..._staffPayload, 'created_at': 'yesterday'},
  }.entries) {
    test(
      'rejects malformed staff ${invalid.key} as an invalid response',
      () async {
        final repository = SpinaManagementAdministrationRepository(
          client: MockClient((request) async {
            return _jsonResponse(<String, Object?>{
              'accounts': <Object?>[invalid.value],
            });
          }),
        );

        await expectLater(
          repository.loadStaff(_session, deviceId: 'management-phone'),
          throwsA(
            isA<SpinaApiException>().having(
              (error) => error.code,
              'code',
              'invalid_server_response',
            ),
          ),
        );
      },
    );
  }

  test('rejects a malformed staff collection as an invalid response', () async {
    final repository = SpinaManagementAdministrationRepository(
      client: MockClient((request) async {
        return _jsonResponse(<String, Object?>{'accounts': 'not-a-list'});
      }),
    );

    await expectLater(
      repository.loadStaff(_session, deviceId: 'management-phone'),
      throwsA(
        isA<SpinaApiException>().having(
          (error) => error.code,
          'code',
          'invalid_server_response',
        ),
      ),
    );
  });

  test('rejects malformed device status as an invalid response', () async {
    final repository = SpinaManagementAdministrationRepository(
      client: MockClient((request) async {
        return _jsonResponse(<String, Object?>{
          'devices': <Object?>[
            <String, Object?>{..._devicePayload, 'status': 'unknown'},
          ],
        });
      }),
    );

    await expectLater(
      repository.loadDevices(
        _session,
        deviceId: 'management-phone',
        userId: '11111111-1111-4111-8111-111111111111',
      ),
      throwsA(
        isA<SpinaApiException>().having(
          (error) => error.code,
          'code',
          'invalid_server_response',
        ),
      ),
    );
  });
}

http.Response _jsonResponse(Map<String, Object?> data, {int statusCode = 200}) {
  return http.Response(
    jsonEncode(<String, Object?>{'success': true, 'data': data}),
    statusCode,
    headers: const <String, String>{'content-type': 'application/json'},
  );
}

const _session = UserSession(
  userId: '99999999-9999-4999-8999-999999999999',
  username: 'manager.one',
  displayName: 'Manager One',
  role: AppRole.management,
  rawRole: 'management',
  accessToken: 'access-token',
  permissions: <String>['account.manage', 'device.manage'],
);

const _staffPayload = <String, Object?>{
  'id': '11111111-1111-4111-8111-111111111111',
  'username': 'collector.one',
  'email': 'collector@example.com',
  'full_name': 'Collector One',
  'status': 'active',
  'roles': <Object?>['collector'],
  'device_count': 1,
  'created_at': '2026-08-28T08:00:00+00:00',
  'updated_at': '2026-08-28T09:00:00+00:00',
};

const _devicePayload = <String, Object?>{
  'id': '22222222-2222-4222-8222-222222222222',
  'user_id': '11111111-1111-4111-8111-111111111111',
  'platform': 'android',
  'app_version': '0.4.0+4',
  'status': 'pending',
  'registered_at': '2026-08-28T08:15:00+00:00',
  'last_seen_at': '2026-08-28T09:15:00+00:00',
};
