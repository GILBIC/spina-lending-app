import 'support/treasury_fixture.dart' as f;
import 'package:gilbic_mobile/src/core/treasury/loan_payout_models.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';

const account = '10000000-0000-4000-8000-000000000001';
const source = '20000000-0000-4000-8000-000000000001';
void main() {
  test(
    'loan payout preparation defaults to Collector and preserves exact source authority',
    () {
      final action = TreasuryAction.fromCode('loan_payout_prepare');
      final command = TreasuryCommand(
        action,
        requestId: source,
        accountId: account,
        expectedVersion: 1,
        fields: {
          'source_kind': 'first_loan',
          'source_id': source,
          'recipient_reference': 'Reviewed Collector wallet',
          'authorization_id': source,
          'packet_hash': 'a' * 64,
          'contract_evidence_reference': 'office-evidence:$source',
          'source_digest': 'b' * 64,
        },
      );
      expect(command.toJson()['destination'], 'collector');
      expect(
        () => TreasuryCommand(
          action,
          requestId: source,
          accountId: account,
          expectedVersion: 1,
          fields: {
            'source_kind': 'first_loan',
            'source_id': source,
            'recipient_reference': 'Reviewed wallet',
            'source_digest': 'b' * 64,
          },
        ),
        throwsFormatException,
      );
    },
  );
  test(
    'own acknowledgment carries no whole-account authority and rejects non-boolean receipt',
    () {
      final action = TreasuryAction.fromCode('loan_payout_acknowledge');
      final fields = <String, dynamic>{
        'payout_id': source,
        'payout_version': 3,
        'stage': 'borrower',
        'received': true,
        'reviewed_amount': '1000.00',
        'receipt_method': 'gcash',
        'acknowledged_at': '2026-10-03T08:00:00+08:00',
        'attestation': 'I received the full proceeds.',
      };
      final body = TreasuryCommand(
        action,
        requestId: source,
        fields: fields,
      ).toJson();
      expect(body.containsKey('account_id'), isFalse);
      expect(
        () => TreasuryCommand(
          action,
          requestId: source,
          fields: {...fields, 'received': 'true'},
        ),
        throwsFormatException,
      );
    },
  );

  test(
    'saved acknowledgment must match the reviewed receipt and exclude nested private fields',
    () {
      final prior = <String, dynamic>{
        'id': f.event,
        'version': 3,
        'source_kind': 'renewal',
        'status': 'recipient_confirmed',
        'destination': 'borrower',
        'amount': '1000.00',
      };
      final body = {
        'action': 'loan_payout_acknowledge',
        'payout_id': f.event,
        'payout_version': 3,
        'stage': 'borrower',
        'received': true,
        'reviewed_amount': '1000.00',
        'receipt_method': 'gcash',
        'acknowledged_at': '2026-10-03T04:00:00Z',
      };
      final ack = {
        'received': true,
        'reviewed_amount': '1000.00',
        'receipt_method': 'gcash',
        'acknowledged_at': '2026-10-03T04:00:00+00:00',
      };
      final held = {
        'action': body['action'],
        'body': body,
        'payout_reference': prior,
      };
      TreasuryResult result(Map<String, dynamic> changed) =>
          TreasuryResult.fromJson({
            ...f.outcome(action: 'loan_payout_acknowledge'),
            'version': 4,
            'result': {
              'stage': 'borrower',
              'payout': {
                ...prior,
                'version': 4,
                'acknowledgments': {
                  'borrower': {...ack, ...changed},
                },
              },
            },
          });
      validateLoanPayoutOutcome(result({}), held);
      for (final change in [
        {'received': false},
        {'receipt_method': 'cash'},
        {
          'wallet': {'reference': 'private'},
        },
      ]) {
        expect(
          () => validateLoanPayoutOutcome(result(change), held),
          throwsFormatException,
        );
      }
    },
  );
}
