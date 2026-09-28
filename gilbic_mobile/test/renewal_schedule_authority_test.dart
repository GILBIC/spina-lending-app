import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow.dart';
import 'package:gilbic_mobile/src/core/renewals/renewal_request.dart';

void main() {
  test('client renewal accepts unavailable signed total and percentage', () {
    final loan = RenewalLoanOption.fromPayload({
      'loan_id': 'loan-1',
      'loan_number': 'REG-1',
      'loan_type_name': 'Regular',
      'calculation_mode': 'fixed_daily',
      'principal': '3000.00',
      'contractual_total': null,
      'remaining_balance': '2000.00',
      'paid_amount': '1000.00',
      'paid_percent': null,
      'daily_amount': '50.00',
      'date_released': '2026-09-01',
      'due_date': '2026-12-30',
      'status': 'active',
      'eligible': false,
      'eligibility_message': 'A verified signed schedule is required.',
    });
    expect(loan.contractualTotal, isNull);
    expect(loan.paidPercent, isNull);
    expect(loan.canRequest, isFalse);
  });

  test(
    'staff renewal accepts unavailable schedule while retaining applied cash',
    () {
      final request = CollectorRenewalRequest.fromPayload({
        'request_id': 'request-1',
        'client_id': 'client-1',
        'client_code': 'C-1',
        'client_name': 'Borrower',
        'area': 'Area 1',
        'loan_id': 'loan-1',
        'loan_number': 'REG-1',
        'loan_type_name': 'Regular',
        'is_7x7': false,
        'current_principal': '3000.00',
        'remaining_balance': '2000.00',
        'contractual_total': null,
        'paid_cash': '1000.00',
        'paid_percent': null,
        'regular_50_percent_eligible': false,
        'requested_amount': '3000.10',
        'status': 'pending',
        'submitted_at': '2026-09-27T00:00:00Z',
        'signer_readiness_status': 'pending',
        'handover_proof_status': 'not_started',
        'activation_status': 'not_started',
        'signers': [],
      });
      expect(request.contractualTotal, isNull);
      expect(request.paidPercent, isNull);
      expect(request.paidCash, 1000);
      expect(request.regular50PercentEligible, isFalse);
    },
  );
}
