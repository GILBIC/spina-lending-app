import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/renewals/renewal_request.dart';

void main() {
  test('approved renewal remains locked while completion is pending', () {
    final loan = RenewalLoanOption.fromPayload(<String, dynamic>{
      'loan_id': 'regular-loan',
      'loan_number': 'TEST-REG-20260802',
      'loan_type_name': 'Regular',
      'calculation_mode': 'fixed_daily',
      'principal': '5000.00',
      'contractual_total': '6000.00',
      'remaining_balance': '4900.00',
      'paid_amount': '100.00',
      'paid_percent': '1.7',
      'daily_amount': '50.00',
      'date_released': '2026-08-01',
      'due_date': '2026-11-29',
      'status': 'active',
      'eligible': true,
      'eligibility_message':
          'Your approved renewal is awaiting completion.',
      'pending_request_id': 'approved-request-1',
      'blocking_request_status': 'approved',
    });

    expect(loan.canRequest, isFalse);
    expect(loan.isAwaitingProcessing, isTrue);
    expect(loan.requestButtonLabel, 'Renewal approved');
  });
}
