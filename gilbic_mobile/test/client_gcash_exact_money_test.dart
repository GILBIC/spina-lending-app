import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/payments/client_gcash.dart';

void main() {
  test('GCash allocation round-trip preserves an exact cent beyond double precision', () {
    final allocation = ClientGcashAllocation.fromPayload(
      <String, dynamic>{
        'loan_id': 'regular-loan',
        'amount': '90071992547409.01',
      },
    );

    expect(allocation.toPayload()['amount'], '90071992547409.01');
  });

  test('GCash intent preserves exact server amount text beyond double precision', () {
    final intent = ClientGcashIntent.fromPayload(
      <String, dynamic>{
        'intent_id': 'intent-exact-money',
        'provider': 'test-provider',
        'mode': 'sandbox',
        'provider_reference': null,
        'status': 'provider_pending',
        'currency': 'PHP',
        'amount': '90071992547409.93',
        'checkout_url': null,
        'qr_value': null,
        'expires_at': null,
        'verified_paid_at': null,
        'official_payment_posted': false,
        'official_collection_transaction_id': null,
        'allocations': <Map<String, dynamic>>[
          <String, dynamic>{
            'loan_id': 'regular-loan',
            'amount': '90071992547409.91',
          },
          <String, dynamic>{
            'loan_id': 'seven-loan',
            'amount': '0.02',
          },
        ],
      },
    );

    expect(intent.amount.toString(), '90071992547409.93');
    expect(intent.allocations.first.toPayload()['amount'], '90071992547409.91');
    expect(intent.allocations.last.toPayload()['amount'], '0.02');
  });
}
