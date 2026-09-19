import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/areas/area_repository.dart';
import 'package:gilbic_mobile/src/core/management/staff_operations_repository.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

UserSession session({
  AppRole role = AppRole.management,
  List<String> permissions = const [
    'area.manage',
    'area.collector.assign',
    'area.client.assign',
    'area.retire',
    'management.dashboard.view',
    'account.manage',
  ],
}) => UserSession(
  userId: 'staff',
  username: 'staff',
  displayName: 'Staff',
  role: role,
  rawRole: role.name,
  accessToken: 'test-token',
  permissions: permissions,
);
DeviceIdentityProvider identity() => DeviceIdentityProvider(
  store: MemoryDeviceIdentityStore()..value = 'test-device',
  platformResolver: () => 'android',
  appVersionResolver: () async => '1',
);
http.Response ok(Object value) =>
    http.Response(jsonEncode({'success': true, 'data': value}), 200);

void main() {
  test(
    'area writes use exact protected contracts without silent retries',
    () async {
      final requests = <http.Request>[];
      final repository = AreaRepository(
        deviceIdentityProvider: identity(),
        client: MockClient((r) async {
          requests.add(r);
          return ok({
            'area_id': 'a',
            'ordered_area_ids': ['a', 'b'],
          });
        }),
      );
      await repository.move(session(), 'a', null);
      await repository.reorder(session(), null, ['a', 'b']);
      await repository.assignCollector(session(), 'a', 'staff-collector');
      await repository.transfer(session(), 'borrower', 'a');
      expect(requests.map((r) => r.method), ['POST', 'POST', 'PUT', 'POST']);
      expect(jsonDecode(requests[0].body), {'new_parent_area_id': null});
      expect(jsonDecode(requests[1].body), {
        'parent_area_id': null,
        'ordered_area_ids': ['a', 'b'],
      });
      expect(jsonDecode(requests[2].body), {
        'collector_user_id': 'staff-collector',
      });
      expect(jsonDecode(requests[3].body), {'target_area_id': 'a'});
      for (final r in requests) {
        expect(r.headers['Authorization'], 'Bearer test-token');
        expect(r.headers['X-Device-Id'], 'test-device');
      }
    },
  );
  test(
    'Employee cannot retire areas even with permission; Collector cannot read',
    () async {
      var calls = 0;
      final repository = AreaRepository(
        deviceIdentityProvider: identity(),
        client: MockClient((r) async {
          calls++;
          return ok({});
        }),
      );
      expect(
        () => repository.retire(session(role: AppRole.employee), 'a'),
        throwsException,
      );
      await expectLater(
        repository.tree(session(role: AppRole.collector)),
        throwsException,
      );
      expect(calls, 0);
    },
  );
  test(
    'area previews use target query and retain server effective dates',
    () async {
      final repository = AreaRepository(
        deviceIdentityProvider: identity(),
        client: MockClient((r) async {
          expect(r.method, 'GET');
          expect(r.url.path, '/api/v1/clients/borrower/area-transfer-preview');
          expect(r.url.queryParameters, {'target_area_id': 'a'});
          return ok({
            'effective_date': '2026-10-01',
            'timing': 'next_collection_day',
          });
        }),
      );
      final result = await repository.transferPreview(
        session(),
        'borrower',
        'a',
      );
      expect(result['effective_date'], '2026-10-01');
    },
  );
  test(
    'malformed area list cannot become an empty successful result',
    () async {
      final repository = AreaRepository(
        deviceIdentityProvider: identity(),
        client: MockClient(
          (r) async => ok({
            'areas': [
              {'area_id': 'a'},
            ],
          }),
        ),
      );
      await expectLater(repository.tree(session()), throwsException);
    },
  );
  test(
    'server forbidden remains a terminal error even with non-JSON body',
    () async {
      final repository = AreaRepository(
        deviceIdentityProvider: identity(),
        client: MockClient((r) async => http.Response('Access denied', 403)),
      );
      await expectLater(
        repository.tree(session()),
        throwsA(
          isA<Exception>().having(
            (e) => (e as dynamic).statusCode,
            'statusCode',
            403,
          ),
        ),
      );
    },
  );
  test(
    'past-due amounts preserve cents above JavaScript integer precision',
    () async {
      final repository = StaffOperationsRepository(
        deviceIdentityProvider: identity(),
        client: MockClient((r) async {
          expect(r.url.queryParameters['start_date'], '2026-09-01');
          expect(r.url.queryParameters['limit'], '500');
          return ok({
            'schema_available': true,
            'summary': {
              'event_count': 1,
              'total_past_due_amount': '90071992547409.93',
              'remaining_past_due_amount': '0.01',
            },
            'rows': [
              {
                'client_name': 'Sample',
                'reason_label': 'No cash',
                'event_kind_label': 'Unable to pay',
                'event_count': 1,
                'total_past_due_amount': '90071992547409.93',
                'remaining_past_due_amount': '0.01',
              },
            ],
          });
        }),
      );
      final report = await repository.pastDue(session(), {
        'start_date': '2026-09-01',
      });
      expect(report.total, '90071992547409.93');
      expect(report.rows.single.remaining, '0.01');
    },
  );
  test('past-due numeric money is rejected instead of rounded', () async {
    final repository = StaffOperationsRepository(
      deviceIdentityProvider: identity(),
      client: MockClient(
        (r) async => ok({
          'schema_available': true,
          'summary': {
            'event_count': 1,
            'total_past_due_amount': 1.25,
            'remaining_past_due_amount': '0.00',
          },
          'rows': [],
        }),
      ),
    );
    await expectLater(repository.pastDue(session(), {}), throwsException);
  });
  test('managed credentials require Management account.manage', () async {
    var calls = 0;
    final repository = StaffOperationsRepository(
      deviceIdentityProvider: identity(),
      client: MockClient((r) async {
        calls++;
        return ok({});
      }),
    );
    await expectLater(
      repository.candidates(session(role: AppRole.employee), 'Maria'),
      throwsException,
    );
    await expectLater(
      repository.candidates(
        session(permissions: ['client.credential.manage']),
        'Maria',
      ),
      throwsException,
    );
    expect(calls, 0);
  });
  test(
    'managed create sends only chosen existing borrower and email',
    () async {
      final repository = StaffOperationsRepository(
        deviceIdentityProvider: identity(),
        client: MockClient((r) async {
          expect(r.url.path, '/api/v1/management/client-accounts');
          expect(r.method, 'POST');
          expect(jsonDecode(r.body), {
            'client_id': 'borrower',
            'email': 'borrower@example.test',
          });
          return ok({
            'account': {'username': 'client.1'},
            'credentials': {'username': 'client.1', 'password': 'one-time'},
            'delivery': {'sent': false, 'detail': 'Email not sent.'},
          });
        }),
      );
      final result = await repository.createAccount(
        session(),
        'borrower',
        'borrower@example.test',
      );
      expect(result.username, 'client.1');
      expect(result.deliverySent, false);
    },
  );
}
