import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/loans/client_schedule.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

void main() {
  test('Client schedule preserves authoritative post-maturity money as exact text', () {
    final schedule = ClientLoanSchedule.fromPayload(
      _schedulePayload(
        exactPayoffTotal: '90071992547409.93',
        projectedPenalty: '5.13',
        assessedPenaltyBalance: '1.25',
      ),
    );
    final dynamic authoritative = schedule;

    expect(authoritative.penaltyStatus, 'projected');
    expect(authoritative.projectedPenalty, '5.13');
    expect(authoritative.assessedPenaltyBalance, '1.25');
    expect(authoritative.penaltyBase, '89.00');
    expect(authoritative.remainingCostHeadroom, '4993.62');
    expect(authoritative.exactPayoffTotal, '90071992547409.93');
    expect(authoritative.managementReviewRequiredReason, '');
  });

  test('Client schedule preserves Management review authority without inventing payoff', () {
    final schedule = ClientLoanSchedule.fromPayload(
      _schedulePayload(
        penaltyStatus: 'management_review_required',
        exactPayoffTotal: '0.00',
        managementReviewRequiredReason: 'Exact signed authority is missing.',
      ),
    );
    final dynamic authoritative = schedule;

    expect(authoritative.penaltyStatus, 'management_review_required');
    expect(
      authoritative.managementReviewRequiredReason,
      'Exact signed authority is missing.',
    );
    expect(authoritative.exactPayoffTotal, '0.00');
  });

  test('Client schedule rejects non-string authoritative payoff money', () {
    final payload = _schedulePayload();
    payload['exact_payoff_total'] = 90071992547409.93;

    expect(
      () => ClientLoanSchedule.fromPayload(payload),
      throwsA(
        isA<SpinaApiException>().having(
          (error) => error.code,
          'code',
          'invalid_client_schedule_payload',
        ),
      ),
    );
  });

  test('Android Client Home is wired to protected schedule authority for 7x7 summary', () {
    final source = File(
      'lib/src/features/client/client_dashboard.dart',
    ).readAsStringSync();

    expect(source, contains('ClientScheduleRepository'));
    expect(source, contains('loadSchedule('));
    expect(source, contains('Exact payoff'));
    expect(source, contains('Management review required'));
  });
}

Map<String, dynamic> _schedulePayload({
  String penaltyStatus = 'projected',
  String projectedPenalty = '5.13',
  String assessedPenaltyBalance = '1.25',
  String exactPayoffTotal = '96.38',
  String managementReviewRequiredReason = '',
}) {
  return <String, dynamic>{
    'loan_id': 'seven-loan',
    'loan_number': '7X7-001',
    'loan_type': '7x7',
    'calculation_mode': 'seven_by_seven',
    'is_7x7': true,
    'payment_frequency': 'daily',
    'read_only': true,
    'past_due_amount': '89.00',
    'past_due_count': 2,
    'schedule_extension_slots': 0,
    'contractual_maturity': '2026-08-26',
    'operational_maturity': '2026-08-26',
    'maturity_status': 'past_due',
    'penalty_status': penaltyStatus,
    'projected_penalty': projectedPenalty,
    'assessed_penalty_balance': assessedPenaltyBalance,
    'penalty_base': '89.00',
    'remaining_cost_headroom': '4993.62',
    'exact_payoff_total': exactPayoffTotal,
    'management_review_required_reason': managementReviewRequiredReason,
    'rows': <Object>[],
  };
}
