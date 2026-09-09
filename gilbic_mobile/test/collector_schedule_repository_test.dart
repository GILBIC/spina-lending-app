import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_schedule_repository.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  const session = UserSession(
    userId: 'collector-1',
    username: 'collector.one',
    displayName: 'Collector One',
    role: AppRole.collector,
    rawRole: 'Collector',
    accessToken: 'collector-token',
  );

  test('parses the authoritative read-only Regular schedule row by row', () async {
    final deviceStore = MemoryDeviceIdentityStore()
      ..value = 'collector-schedule-device';
    final repository = SpinaCollectorScheduleRepository(
      deviceIdentityProvider: DeviceIdentityProvider(
        store: deviceStore,
        platformResolver: () => 'android',
        appVersionResolver: () async => '0.4.0+4',
      ),
      client: MockClient((request) async {
        expect(request.method, 'GET');
        expect(
          request.url.path,
          '/api/mobile/v1/collector/loans/loan-regular/schedule',
        );
        expect(request.headers['authorization'], 'Bearer collector-token');
        expect(request.headers['x-device-id'], 'collector-schedule-device');

        return http.Response(
          jsonEncode(<String, Object?>{
            'success': true,
            'data': <String, Object?>{
              'loan_id': 'loan-regular',
              'loan_number': 'LN-R-1001',
              'client_id': 'client-1',
              'client_name': 'Ana Client',
              'loan_type': 'Regular',
              'calculation_mode': 'fixed_total',
              'is_7x7': false,
              'schedule_id': 'schedule-regular',
              'schedule_version': 4,
              'payment_frequency': 'daily',
              'contract_reference': 'CTR-R-1001',
              'as_of_date': '2026-09-09',
              'read_only': true,
              'past_due_amount': '60.00',
              'past_due_count': 1,
              'schedule_extension_slots': 2,
              'maturity_extended': true,
              'base_maturity': '2026-12-01',
              'updated_maturity': '2026-12-03',
              'maturity_projection_status': 'extended',
              'rows': <Object?>[
                <String, Object?>{
                  'kind': 'installment',
                  'date': '2026-09-07',
                  'status': 'Paid',
                  'amount': '100.00',
                  'contractual_amount': '100.00',
                  'paid_amount': '100.00',
                  'prepaid_amount': '0.00',
                  'remaining_amount': '0.00',
                  'installment_id': 1,
                  'installment_number': 1,
                  'contractual_due_date': '2026-09-07',
                  'principal_component': '80.00',
                  'interest_component': '20.00',
                  'principal_reduction_amount': '0.00',
                  'past_due_reason_code': null,
                  'past_due_reason_note': null,
                  'promised_for_date': null,
                  'promise_remaining_amount': '0.00',
                  'promise_status': null,
                  'no_collection_reason': null,
                },
                <String, Object?>{
                  'kind': 'installment',
                  'date': '2026-09-09',
                  'status': 'Due Today',
                  'amount': '100.00',
                  'contractual_amount': '100.00',
                  'paid_amount': '0.00',
                  'prepaid_amount': '0.00',
                  'remaining_amount': '100.00',
                  'installment_id': 2,
                  'installment_number': 2,
                  'contractual_due_date': '2026-09-09',
                  'principal_component': '80.00',
                  'interest_component': '20.00',
                  'principal_reduction_amount': '0.00',
                  'past_due_reason_code': null,
                  'past_due_reason_note': null,
                  'promised_for_date': null,
                  'promise_remaining_amount': '0.00',
                  'promise_status': null,
                  'no_collection_reason': null,
                },
                <String, Object?>{
                  'kind': 'installment',
                  'date': '2026-09-08',
                  'status': 'Past Due',
                  'amount': '100.00',
                  'contractual_amount': '100.00',
                  'paid_amount': '40.00',
                  'prepaid_amount': '0.00',
                  'remaining_amount': '60.00',
                  'installment_id': 3,
                  'installment_number': 3,
                  'contractual_due_date': '2026-09-08',
                  'principal_component': '80.00',
                  'interest_component': '20.00',
                  'principal_reduction_amount': '0.00',
                  'past_due_reason_code': 'business_slow',
                  'past_due_reason_note': 'Sales were low',
                  'promised_for_date': '2026-09-10',
                  'promise_remaining_amount': '60.00',
                  'promise_status': 'active',
                  'no_collection_reason': null,
                },
                <String, Object?>{
                  'kind': 'installment',
                  'date': '2026-09-10',
                  'status': 'Paid in Advance',
                  'amount': '100.00',
                  'contractual_amount': '100.00',
                  'paid_amount': '100.00',
                  'prepaid_amount': '100.00',
                  'remaining_amount': '0.00',
                  'installment_id': 4,
                  'installment_number': 4,
                  'contractual_due_date': '2026-09-10',
                  'principal_component': '80.00',
                  'interest_component': '20.00',
                  'principal_reduction_amount': '0.00',
                  'past_due_reason_code': null,
                  'past_due_reason_note': null,
                  'promised_for_date': null,
                  'promise_remaining_amount': '0.00',
                  'promise_status': null,
                  'no_collection_reason': null,
                },
                <String, Object?>{
                  'kind': 'installment',
                  'date': '2026-09-11',
                  'status': 'Scheduled',
                  'amount': '100.00',
                  'contractual_amount': '100.00',
                  'paid_amount': '0.00',
                  'prepaid_amount': '0.00',
                  'remaining_amount': '100.00',
                  'installment_id': 5,
                  'installment_number': 5,
                  'contractual_due_date': '2026-09-11',
                  'principal_component': '80.00',
                  'interest_component': '20.00',
                  'principal_reduction_amount': '0.00',
                  'past_due_reason_code': null,
                  'past_due_reason_note': null,
                  'promised_for_date': null,
                  'promise_remaining_amount': '0.00',
                  'promise_status': null,
                  'no_collection_reason': null,
                },
              ],
            },
          }),
          200,
        );
      }),
    );

    final schedule = await repository.fetchSchedule(
      session,
      loanId: 'loan-regular',
    );

    expect(schedule.loanId, 'loan-regular');
    expect(schedule.loanNumber, 'LN-R-1001');
    expect(schedule.clientName, 'Ana Client');
    expect(schedule.loanType, 'Regular');
    expect(schedule.calculationMode, 'fixed_total');
    expect(schedule.isSevenBySeven, isFalse);
    expect(schedule.readOnly, isTrue);
    expect(schedule.pastDueAmount, 60);
    expect(schedule.pastDueCount, 1);
    expect(schedule.scheduleExtensionSlots, 2);
    expect(schedule.maturityExtended, isTrue);
    expect(schedule.baseMaturity, DateTime(2026, 12, 1));
    expect(schedule.updatedMaturity, DateTime(2026, 12, 3));
    expect(schedule.rows, hasLength(5));
    expect(
      schedule.rows.map((row) => row.status),
      <String>[
        'Paid',
        'Due Today',
        'Past Due',
        'Paid in Advance',
        'Scheduled',
      ],
    );

    final pastDue = schedule.rows[2];
    expect(pastDue.remainingAmount, 60);
    expect(pastDue.pastDueReasonCode, 'business_slow');
    expect(pastDue.pastDueReasonNote, 'Sales were low');
    expect(pastDue.promisedForDate, DateTime(2026, 9, 10));
    expect(pastDue.promiseRemainingAmount, 60);
    expect(pastDue.promiseStatus, 'active');

    final prepaid = schedule.rows[3];
    expect(prepaid.prepaidAmount, 100);
    expect(prepaid.remainingAmount, 0);

    final paid = schedule.rows.first;
    expect(paid.kind, 'installment');
    expect(paid.principalComponent, 80);
    expect(paid.interestComponent, 20);
  });

  test('preserves the authoritative 7x7 loan type and schedule kind', () async {
    final deviceStore = MemoryDeviceIdentityStore()
      ..value = 'collector-schedule-device';
    final repository = SpinaCollectorScheduleRepository(
      deviceIdentityProvider: DeviceIdentityProvider(
        store: deviceStore,
        platformResolver: () => 'android',
        appVersionResolver: () async => '0.4.0+4',
      ),
      client: MockClient((request) async {
        expect(
          request.url.path,
          '/api/mobile/v1/collector/loans/loan-7x7/schedule',
        );
        return http.Response(
          jsonEncode(<String, Object?>{
            'success': true,
            'data': <String, Object?>{
              'loan_id': 'loan-7x7',
              'loan_number': 'LN-7-1001',
              'client_id': 'client-1',
              'client_name': 'Ana Client',
              'loan_type': '7x7',
              'calculation_mode': 'seven_by_seven',
              'is_7x7': true,
              'schedule_id': 'schedule-7x7',
              'schedule_version': 1,
              'payment_frequency': 'daily',
              'contract_reference': 'CTR-7-1001',
              'as_of_date': '2026-09-09',
              'read_only': true,
              'past_due_amount': '0.00',
              'past_due_count': 0,
              'schedule_extension_slots': 0,
              'maturity_extended': false,
              'base_maturity': '2026-10-20',
              'updated_maturity': '2026-10-20',
              'maturity_projection_status': 'contractual',
              'rows': <Object?>[
                <String, Object?>{
                  'kind': 'installment',
                  'date': '2026-09-09',
                  'status': 'Due Today',
                  'amount': '50.00',
                  'contractual_amount': '50.00',
                  'paid_amount': '0.00',
                  'prepaid_amount': '0.00',
                  'remaining_amount': '50.00',
                  'installment_id': 1,
                  'installment_number': 1,
                  'contractual_due_date': '2026-09-09',
                  'principal_component': '43.00',
                  'interest_component': '7.00',
                  'principal_reduction_amount': '0.00',
                  'past_due_reason_code': null,
                  'past_due_reason_note': null,
                  'promised_for_date': null,
                  'promise_remaining_amount': '0.00',
                  'promise_status': null,
                  'no_collection_reason': null,
                },
              ],
            },
          }),
          200,
        );
      }),
    );

    final schedule = await repository.fetchSchedule(
      session,
      loanId: 'loan-7x7',
    );

    expect(schedule.loanType, '7x7');
    expect(schedule.calculationMode, 'seven_by_seven');
    expect(schedule.isSevenBySeven, isTrue);
    expect(schedule.rows.single.kind, 'installment');
    expect(schedule.rows.single.interestComponent, 7);
    expect(schedule.readOnly, isTrue);
  });
}
