import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/loans/client_schedule_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const _session = UserSession(
  userId: 'client-1',
  username: 'testregular1',
  displayName: 'TEST CLIENT REGULAR',
  role: AppRole.client,
  rawRole: 'Client',
  accessToken: 'client-token',
  permissions: <String>[],
);

void main() {
  test('loads the authenticated Client authoritative schedule', () async {
    final repository = SpinaClientScheduleRepository(
      client: MockClient((request) async {
        expect(request.method, 'GET');
        expect(
          request.url.path,
          '/api/mobile/v1/client/loans/regular-loan/schedule',
        );
        expect(request.headers['Authorization'], 'Bearer client-token');
        expect(request.headers['X-Device-Id'], 'client-device');
        return http.Response(
          jsonEncode(<String, Object?>{
            'success': true,
            'data': <String, Object?>{
              'loan_id': 'regular-loan',
              'loan_number': 'TEST-REG-20260802',
              'loan_type': 'Regular',
              'calculation_mode': 'fixed_total',
              'is_7x7': false,
              'payment_frequency': 'daily',
              'read_only': true,
              'past_due_amount': '90071992547409.91',
              'past_due_count': 1,
              'schedule_extension_slots': 2,
              'contractual_maturity': '2026-10-10',
              'operational_maturity': '2026-10-12',
              'maturity_status': 'extended',
              'rows': <Object?>[
                <String, Object?>{
                  'payment_date': '2026-09-12',
                  'amount': '90071992547409.91',
                  'status': 'Due Today',
                  'details': <String, Object?>{
                    'remaining_amount': '90071992547409.90',
                    'note': 'Management-approved extension',
                  },
                },
              ],
            },
          }),
          200,
          headers: const <String, String>{
            'content-type': 'application/json',
          },
        );
      }),
    );

    final schedule = await repository.loadSchedule(
      _session,
      deviceId: 'client-device',
      loanId: 'regular-loan',
    );

    expect(schedule.loanId, 'regular-loan');
    expect(schedule.contractualMaturity, DateTime(2026, 10, 10));
    expect(schedule.operationalMaturity, DateTime(2026, 10, 12));
    expect(schedule.pastDueAmount, '90071992547409.91');
    expect(schedule.rows.single.amount, '90071992547409.91');
    expect(schedule.rows.single.remainingAmount, '90071992547409.90');
    expect(schedule.rows.single.note, 'Management-approved extension');
  });

  test('preserves the controlled schedule-unavailable server error', () async {
    final repository = SpinaClientScheduleRepository(
      client: MockClient((request) async {
        return http.Response(
          jsonEncode(<String, Object?>{
            'detail': <String, Object?>{
              'code': 'client_loan_schedule_unavailable',
              'message':
                  'A verified contractual schedule is not yet available for this loan.',
            },
          }),
          409,
          headers: const <String, String>{
            'content-type': 'application/json',
          },
        );
      }),
    );

    await expectLater(
      repository.loadSchedule(
        _session,
        deviceId: 'client-device',
        loanId: 'regular-loan',
      ),
      throwsA(
        isA<SpinaApiException>()
            .having(
              (error) => error.code,
              'code',
              'client_loan_schedule_unavailable',
            )
            .having((error) => error.statusCode, 'statusCode', 409),
      ),
    );
  });
}
