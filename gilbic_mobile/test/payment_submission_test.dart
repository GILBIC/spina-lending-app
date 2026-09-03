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

  test('serializes a normal payment with the collection date', () {
    final draft = _draft(
      entryType: CollectionEntryType.payment,
      amount: 200,
      coveredDates: <DateTime>[DateTime(2026, 7, 31)],
    );

    expect(draft.validate(), isNull);
    expect(
      draft.toJson(),
      containsPair('client_transaction_id', 'transaction-1'),
    );
    expect(draft.toJson(), containsPair('collection_date', '2026-07-31'));
    expect(draft.toJson(), containsPair('entry_type', 'payment'));
    expect(draft.toJson(), containsPair('amount', 200));
    expect(
      draft.toJson(),
      containsPair('covered_dates', <String>['2026-07-31']),
    );
    expect(draft.toJson(), containsPair('route_revision', 'route-v3'));
  });

  test('serializes only individually selected covered dates', () {
    final draft = _draft(
      entryType: CollectionEntryType.advance,
      amount: 600,
      advanceFrom: DateTime(2026, 7, 31),
      advanceUntil: DateTime(2026, 8, 3),
      coveredDates: <DateTime>[
        DateTime(2026, 8, 3),
        DateTime(2026, 7, 31),
        DateTime(2026, 8, 2),
      ],
    );

    expect(draft.validate(), isNull);
    expect(
      draft.toJson()['covered_dates'],
      <String>['2026-07-31', '2026-08-02', '2026-08-03'],
    );
    expect(
      (draft.toJson()['covered_dates'] as List<Object?>).contains('2026-08-01'),
      isFalse,
    );
  });

  test('requires exact covered dates and matching bounds', () {
    final missingCoverage = _draft(
      entryType: CollectionEntryType.advance,
      amount: 400,
    );
    final mismatchedBounds = _draft(
      entryType: CollectionEntryType.advance,
      amount: 400,
      advanceFrom: DateTime(2026, 8, 1),
      advanceUntil: DateTime(2026, 8, 3),
      coveredDates: <DateTime>[
        DateTime(2026, 8, 2),
        DateTime(2026, 8, 3),
      ],
    );

    expect(missingCoverage.validate(), contains('Choose at least one'));
    expect(mismatchedBounds.validate(), contains('earliest selected date'));
  });

  test('unable-to-pay requires structured Past Due reason', () {
    final passWithAmount = _draft(
      entryType: CollectionEntryType.pass,
      amount: 200,
      pastDueFollowup: const PastDueFollowupDraft(
        reasonCode: PastDueReasonCode.noCash,
      ),
    );
    final passWithDate = _draft(
      entryType: CollectionEntryType.pass,
      coveredDates: <DateTime>[DateTime(2026, 7, 31)],
      pastDueFollowup: const PastDueFollowupDraft(
        reasonCode: PastDueReasonCode.noCash,
      ),
    );
    final missingReason = _draft(entryType: CollectionEntryType.pass);
    final validPass = _draft(
      entryType: CollectionEntryType.pass,
      pastDueFollowup: const PastDueFollowupDraft(
        reasonCode: PastDueReasonCode.noCash,
        note: 'No cash available today',
      ),
    );

    expect(passWithAmount.validate(), contains('cannot contain'));
    expect(passWithDate.validate(), contains('cannot contain'));
    expect(missingReason.validate(), contains('Past Due reason'));
    expect(validPass.validate(), isNull);
    expect(
      validPass.toJson()['past_due_followup'],
      <String, Object?>{
        'reason_code': 'no_cash',
        'note': 'No cash available today',
        'promised_payment_date': null,
        'promised_amount': null,
      },
    );
  });

  test('promise follow-up requires date and supports a partial promised amount', () {
    final missingDate = _draft(
      entryType: CollectionEntryType.pass,
      pastDueFollowup: const PastDueFollowupDraft(
        reasonCode: PastDueReasonCode.promisedToPayLater,
        promisedAmount: 100,
      ),
    );
    final promised = _draft(
      entryType: CollectionEntryType.pass,
      pastDueFollowup: PastDueFollowupDraft(
        reasonCode: PastDueReasonCode.promisedToPayLater,
        note: 'After salary',
        promisedPaymentDate: DateTime(2026, 8, 2),
        promisedAmount: 100,
      ),
    );

    expect(missingDate.validate(), contains('promised payment date'));
    expect(promised.validate(), isNull);
    expect(
      promised.toJson()['past_due_followup'],
      <String, Object?>{
        'reason_code': 'promised_to_pay_later',
        'note': 'After salary',
        'promised_payment_date': '2026-08-02',
        'promised_amount': 100,
      },
    );
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
  List<DateTime> coveredDates = const <DateTime>[],
  PastDueFollowupDraft? pastDueFollowup,
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
    coveredDates: coveredDates,
    recordedAt: DateTime.utc(2026, 7, 31, 5, 15),
    deviceId: 'device-1',
    deviceSequence: 12,
    note: 'Client paid at home',
    routeRevision: 'route-v3',
    pastDueFollowup: pastDueFollowup,
  );
}
