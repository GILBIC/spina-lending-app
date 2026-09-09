import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_repository.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  const session = UserSession(
    userId: '12',
    username: 'collector.one',
    displayName: 'Collector One',
    role: AppRole.collector,
    rawRole: 'Collector',
    accessToken: 'token-123',
  );

  test('downloads only the authenticated collector route from active device', () async {
    final deviceStore = MemoryDeviceIdentityStore()
      ..value = 'gilbic-route-device';
    final repository = SpinaCollectorRouteRepository(
      routeUri: Uri.parse('https://spina.test/route'),
      deviceIdentityProvider: DeviceIdentityProvider(
        store: deviceStore,
        platformResolver: () => 'android',
        appVersionResolver: () async => '0.4.0+4',
      ),
      client: MockClient((request) async {
        expect(request.method, 'GET');
        expect(request.headers['authorization'], 'Bearer token-123');
        expect(request.headers['x-device-id'], 'gilbic-route-device');
        return http.Response(
          jsonEncode(<String, Object?>{
            'success': true,
            'data': <String, Object?>{
              'route_date': '2026-07-31',
              'collector_name': 'Collector One',
              'areas': <String>['Cardona'],
              'expected_total': 400,
              'entries': <Object?>[
                <String, Object?>{
                  'route_entry_id': 'entry-1',
                  'client_id': 'client-1',
                  'loan_id': 'loan-1',
                  'client_name': 'Ana Client',
                  'area': 'Cardona',
                  'loan_type': 'Regular',
                  'daily_amount': 200,
                  'remaining_balance': 4800,
                  'pass_count': 1,
                  'status': 'Pending',
                },
                <String, Object?>{
                  'route_entry_id': 'entry-2',
                  'client_id': 'client-2',
                  'loan_id': 'loan-2',
                  'client_name': 'Ben Client',
                  'area': 'Cardona',
                  'loan_type': '7x7',
                  'daily_amount': 200,
                  'remaining_balance': 3000,
                  'advance_until': '2026-08-02',
                  'status': 'Advance',
                },
              ],
            },
          }),
          200,
        );
      }),
    );

    final route = await repository.fetchToday(session);

    expect(route.collectorName, 'Collector One');
    expect(route.areas, <String>['Cardona']);
    expect(route.expectedTotal, 400);
    expect(route.entries, hasLength(2));
    expect(route.entries.first.clientName, 'Ana Client');
    expect(route.entries.first.passCount, 1);
    expect(route.entries.last.advanceUntil, DateTime(2026, 8, 2));
  });

  test('parses ordered stable Area hierarchy metadata from the route payload', () async {
    final deviceStore = MemoryDeviceIdentityStore()
      ..value = 'gilbic-route-hierarchy-device';
    final repository = SpinaCollectorRouteRepository(
      routeUri: Uri.parse('https://spina.test/route'),
      deviceIdentityProvider: DeviceIdentityProvider(
        store: deviceStore,
        platformResolver: () => 'android',
        appVersionResolver: () async => '0.4.0+4',
      ),
      client: MockClient((request) async {
        return http.Response(
          jsonEncode(<String, Object?>{
            'success': true,
            'data': <String, Object?>{
              'route_date': '2026-09-09',
              'collector_name': 'Collector One',
              'areas': <String>['Cardona › Calahan'],
              'expected_total': 200,
              'area_nodes': <Object?>[
                <String, Object?>{
                  'area_uid': 'cardona',
                  'parent_area_uid': null,
                  'name': 'Cardona',
                  'full_path': 'Cardona',
                  'depth': 0,
                  'sort_order': 0,
                  'is_legacy_unmapped': false,
                },
                <String, Object?>{
                  'area_uid': 'calahan',
                  'parent_area_uid': 'cardona',
                  'name': 'Calahan',
                  'full_path': 'Cardona › Calahan',
                  'depth': 1,
                  'sort_order': 0,
                  'is_legacy_unmapped': false,
                },
                <String, Object?>{
                  'area_uid': 'balayong',
                  'parent_area_uid': 'calahan',
                  'name': 'Balayong',
                  'full_path': 'Cardona › Calahan › Balayong',
                  'depth': 2,
                  'sort_order': 0,
                  'is_legacy_unmapped': false,
                },
              ],
              'entries': <Object?>[
                <String, Object?>{
                  'route_entry_id': 'entry-hierarchy',
                  'client_id': 'client-hierarchy',
                  'loan_id': 'loan-hierarchy',
                  'client_name': 'Ana Client',
                  'area': 'Cardona › Calahan › Balayong',
                  'area_uid': 'balayong',
                  'loan_type': 'Regular',
                  'daily_amount': 200,
                  'remaining_balance': 4800,
                  'pass_count': 0,
                  'status': 'Pending',
                },
              ],
            },
          }),
          200,
        );
      }),
    );

    final route = await repository.fetchToday(session);

    expect(
      route.areaNodes.map((node) => node.areaUid),
      <String>['cardona', 'calahan', 'balayong'],
    );
    expect(
      route.areaNodes.map((node) => node.name),
      <String>['Cardona', 'Calahan', 'Balayong'],
    );
    expect(route.areaNodes[1].parentAreaUid, 'cardona');
    expect(route.areaNodes.last.fullPath, 'Cardona › Calahan › Balayong');
    expect(route.areaNodes.last.depth, 2);
    expect(route.areaNodes.last.sortOrder, 0);
    expect(route.areaNodes.last.isLegacyUnmapped, isFalse);
    expect(route.entries.single.areaUid, 'balayong');
    expect(route.areas, <String>['Cardona › Calahan']);
  });
}
