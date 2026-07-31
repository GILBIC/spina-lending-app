import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_repository.dart';
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

  test('downloads only the authenticated collector route', () async {
    final repository = SpinaCollectorRouteRepository(
      routeUri: Uri.parse('https://spina.test/route'),
      client: MockClient((request) async {
        expect(request.method, 'GET');
        expect(request.headers['authorization'], 'Bearer token-123');
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
}
