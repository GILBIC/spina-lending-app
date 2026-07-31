import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission.dart';

void main() {
  test('generates RFC 4122 version 4 idempotency keys', () {
    final generator = SecureIdempotencyKeyGenerator(random: Random(7));

    final first = generator.generate();
    final second = generator.generate();

    expect(first, isNot(second));
    expect(
      first,
      matches(
        RegExp(
          r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        ),
      ),
    );
  });

  test('serializes a normal payment without calculating server values', () {
    final draft = _draft(
      entryType: CollectionEntryType.payment,
      amount: 200,
    );

    expect(draft.validate(), isNull);
    expect(
      draft.toJson(),
      containsPair('client_transaction_id', 'transaction-1'),
    );
    expect(draft.toJson(), containsPair('collection_date', '2026-07-31'));
    expect(draft.toJson(), containsPair('entry_type', 'payment'));
    expect(draft.toJson(), containsPair('amount', 200));
    expect(draft.toJson(), containsPair('route_revision', 'route-v3'));
  });

  test('requires ADV coverage and rejects reversed dates', () {
    final missingCoverage = _draft(
      entryType: CollectionEntryType.advance,
      amount: 400,
    );
    final reversedCoverage = _draft(
      entryType: CollectionEntryType.advance,
      amount: 400,
      advanceFrom: DateTime(2026, 8, 2),
      advanceUntil: DateTime(2026, 8, 1),
    );

    expect(missingCoverage.validate(), contains('coverage'));
    expect(reversedCoverage.validate(), contains('cannot end before'));
  });

  test('PASS entries cannot contain money or ADV dates', () {
    final passWithAmount = _draft(
      entryType: CollectionEntryType.pass,
      amount: 200,
    );
    final validPass = _draft(entryType: CollectionEntryType.pass);

    expect(passWithAmount.validate(), contains('cannot contain'));
    expect(validPass.validate(), isNull);
  });

  test('parses duplicate server receipts as a final success', () {
    final result = PaymentSubmissionResult.fromPayload(
      <String, Object?>{
        'duplicate': true,
        'message': 'Previously accepted',
        'transaction': <String, Object?>{
          'transaction_id': 'server-55',
          'receipt_number': 'OR-000055',
          'official_balance': 4600,
          'accepted_at': '2026-07-31T05:20:00Z',
        },
      },
      idempotencyKey: 'transaction-1',
      fallbackDisposition: PaymentSubmissionDisposition.accepted,
    );

    expect(result.disposition, PaymentSubmissionDisposition.duplicate);
    expect(result.isFinalSuccess, isTrue);
    expect(result.serverTransactionId, 'server-55');
    expect(result.receiptNumber, 'OR-000055');
    expect(result.officialBalance, 4600);
  });
}

PaymentSubmissionDraft _draft({
  required CollectionEntryType entryType,
  double? amount,
  DateTime? advanceFrom,
  DateTime? advanceUntil,
}) {
  return PaymentSubmissionDraft(
    idempotencyKey: 'transaction-1',
    routeEntryId: 'route-entry-1',
    clientId: 'client-1',
    loanId: 'loan-1',
    collectionDate: DateTime(2026, 7, 31),
    entryType: entryType,
    amount: amount,
    advanceFrom: advanceFrom,
    advanceUntil: advanceUntil,
    recordedAt: DateTime.utc(2026, 7, 31, 5, 15),
    deviceId: 'device-1',
    deviceSequence: 12,
    note: 'Client paid at home',
    routeRevision: 'route-v3',
  );
}
