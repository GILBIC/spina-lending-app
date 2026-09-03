import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/other_area_client_repository.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  const session = UserSession(
    userId: 'collector-one',
    username: 'collector.one',
    displayName: 'Collector One',
    role: AppRole.collector,
    rawRole: 'Collector',
    accessToken: 'collector-token',
    permissions: <String>['collection.create', 'delegated_area.view'],
  );

  test('loads granted work using the Philippine SPINA business date', () async {
    final deviceStore = MemoryDeviceIdentityStore()
      ..value = 'delegated-work-device';
    final repository = SpinaOtherAreaClientRepository(
      endpoint: Uri.parse('https://spina.test/search'),
      workEndpoint: Uri.parse('https://spina.test/delegated-area/work'),
      deviceIdentityProvider: DeviceIdentityProvider(
        store: deviceStore,
        platformResolver: () => 'android',
        appVersionResolver: () async => '1.0.0-rc',
      ),
      client: MockClient((request) async {
        expect(request.method, 'GET');
        expect(request.url.path, '/delegated-area/work');
        expect(request.url.queryParameters['date'], '2026-08-18');
        expect(request.url.queryParameters['limit'], '500');
        expect(
          request.url.queryParameters['assigned_collector_user_id'],
          'collector-two',
        );
        expect(request.headers['authorization'], 'Bearer collector-token');
        expect(request.headers['x-device-id'], 'delegated-work-device');
        return http.Response.bytes(
          utf8.encode(
            jsonEncode(<String, Object?>{
              'success': true,
              'data': <Object?>[
                <String, Object?>{
                  'route_entry_id': 'loan-other',
                  'client_id': 'client-other',
                  'loan_id': 'loan-other',
                  'client_name': 'Bea Borrower',
                  'client_code': 'C-OTHER',
                  'phone_number': '09170000000',
                  'area': 'Taytay › San Juan',
                  'loan_type': 'Regular',
                  'daily_amount': '200.00',
                  'remaining_balance': '4800.00',
                  'pass_count': 0,
                  'status': 'Pending',
                  'route_revision': 'loan:loan-other:v3',
                  'can_collect_mobile': true,
                  'can_enter_payment': true,
                  'collection_message': 'Delegated other-area work.',
                  'assigned_collector_user_id': 'collector-two',
                  'assigned_collector_name': 'Collector Two',
                  'processed_today': false,
                },
              ],
            }),
          ),
          200,
          headers: const <String, String>{
            'content-type': 'application/json; charset=utf-8',
          },
        );
      }),
    );

    final work = await repository.listWork(
      session,
      DateTime.parse('2026-08-17T16:30:00Z'),
      assignedCollectorUserId: 'collector-two',
    );

    expect(work, hasLength(1));
    expect(work.single.entry.clientName, 'Bea Borrower');
    expect(work.single.entry.area, 'Taytay › San Juan');
    expect(work.single.assignedCollectorName, 'Collector Two');
  });

  test('management search continues to use the search endpoint', () async {
    final deviceStore = MemoryDeviceIdentityStore()
      ..value = 'management-search-device';
    final repository = SpinaOtherAreaClientRepository(
      endpoint: Uri.parse('https://spina.test/other-area-clients/search'),
      workEndpoint: Uri.parse('https://spina.test/delegated-area/work'),
      deviceIdentityProvider: DeviceIdentityProvider(
        store: deviceStore,
        platformResolver: () => 'android',
        appVersionResolver: () async => '1.0.0-rc',
      ),
      client: MockClient((request) async {
        expect(request.url.path, '/other-area-clients/search');
        expect(request.url.queryParameters['q'], 'Bea Borrower');
        expect(request.url.queryParameters['limit'], '25');
        expect(request.url.queryParameters.containsKey('date'), isFalse);
        return http.Response(
          jsonEncode(<String, Object?>{'success': true, 'data': <Object?>[]}),
          200,
        );
      }),
    );

    final result = await repository.search(session, '  Bea   Borrower  ');
    expect(result, isEmpty);
  });
}
