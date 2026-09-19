import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan.dart';

void main() {
  final payload = <String, dynamic>{
    'loan_id': 'synthetic-loan',
    'loan_number': 'SYNTHETIC-ONLY',
    'loan_type_name': 'Regular',
    'principal': '1000.00',
    'daily_amount': '100.00',
    'status': 'active',
    'remaining_balance': '1200.00',
    'paid_amount': '0.00',
    'pass_count': 0,
    'state_version': 0,
    'payment_count': 0,
    'date_released': '2026-09-19',
  };

  test('first payment is the explicit server date, not inferred from release', () {
    expect(ClientLoan.fromPayload(payload).firstPaymentDate, isNull);
    final loan = ClientLoan.fromPayload({
      ...payload,
      'first_payment_date': '2026-09-28',
    });
    expect(loan.dateReleased, DateTime(2026, 9, 19));
    expect(loan.firstPaymentDate, DateTime(2026, 9, 28));
  });

  test('unreleased and legacy payloads remain compatible with nullable dates', () {
    final loan = ClientLoan.fromPayload({
      ...payload,
      'status': 'approved',
      'date_released': null,
      'first_payment_date': null,
    });
    expect(loan.dateReleased, isNull);
    expect(loan.firstPaymentDate, isNull);
  });
}
