import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/payments/collection_correction.dart';

void main() {
  test('correction draft requires and sends the reviewed route revision', () {
    final draft = CollectionCorrectionDraft(
      transactionId: 'tx-1',
      entryType: 'payment',
      amount: 100,
      coveredDates: <DateTime>[DateTime(2026, 8, 16)],
      note: 'Correct amount',
      reason: 'Wrong amount entered',
      expectedRouteRevision: 'loan:loan-1:v7',
    );

    expect(draft.validate(), isNull);
    expect(draft.toJson()['expected_route_revision'], 'loan:loan-1:v7');
  });

  test('correction draft fails closed without a route revision', () {
    final draft = CollectionCorrectionDraft(
      transactionId: 'tx-1',
      entryType: 'payment',
      amount: 100,
      coveredDates: <DateTime>[DateTime(2026, 8, 16)],
      reason: 'Wrong amount entered',
      expectedRouteRevision: '',
    );

    expect(draft.validate(), contains('Refresh before editing'));
  });
}
