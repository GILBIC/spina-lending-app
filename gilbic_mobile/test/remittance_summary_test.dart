import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance.dart';

void main() {
  test('counts exact covered dates from remittance items', () {
    final summary = RemittanceSummary.fromPayload(<String, Object?>{
      'collection_date': '2026-08-03',
      'collector_name': 'Test Collector',
      'transaction_count': 1,
      'payment_count': 1,
      'unable_to_pay_count': 0,
      'covered_payment_count': 0,
      'client_count': 1,
      'total_amount': '50.00',
      'items': <Object?>[
        <String, Object?>{
          'transaction_id': 'tx-1',
          'client_name': 'Test Client',
          'loan_type': 'Regular',
          'entry_type': 'payment',
          'amount': '50.00',
          'receipt_number': 'GBC-1',
          'covered_dates': <String>['2026-08-03'],
          'note': '',
        },
      ],
    });

    expect(summary.coveredPaymentCount, 1);
    expect(summary.items.single.coveredDates, <DateTime>[DateTime(2026, 8, 3)]);
  });

  test('uses server count when a compact payload omits items', () {
    final summary = RemittanceSummary.fromPayload(<String, Object?>{
      'collector_name': 'Test Collector',
      'covered_payment_count': 2,
    });

    expect(summary.coveredPaymentCount, 2);
  });
}
