import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'support/treasury_fixture.dart';

void main() {
  test(
    'all native action families serialize frozen backend contracts without authority fields',
    () async {
      final transaction = {
        'amount': '20.01',
        'fee': '0.15',
        'provider': 'gcash',
        'reference': 'Synthetic recipient reference',
        'effective_at': '2026-10-02T00:00:00+08:00',
        'evidence_id': event,
        'recipient_attestation': 'Actual recipient-side evidence checked',
        'reason': 'Synthetic controlled fixture',
      };
      final closing = {
        'reconciliation_id': event,
        'reconciliation_version': 1,
        'opening_id': ledger,
        'movement_watermark': 0,
        'reason': 'Complete synthetic coverage checked',
      };
      final fields = <TreasuryAction, Map<String, dynamic>>{
        TreasuryAction.accountConfigure: {
          'ledger_context_id': ledger,
          'context': 'synthetic',
          'kind': 'gcash',
          'alias': 'Synthetic wallet',
          'ownership': 'synthetic',
          'custodian_user_id': user,
          'designated_receiving': false,
          'active': true,
        },
        TreasuryAction.accountGrant: {
          'user_id': user,
          'permissions': ['treasury.view', 'treasury.proof.review'],
          'private_history': false,
          'enabled': true,
        },
        TreasuryAction.openingPrepare: {
          'cutoff': '2026-10-01T00:00:00+08:00',
          'amount': '0.00',
          'evidence_id': event,
          'reason': 'Observed synthetic zero count',
          'personal_amount': '0.00',
        },
        TreasuryAction.openingActivate: {
          'opening_id': ledger,
          'opening_version': 1,
          'confirmed': true,
          'reason': 'Actual observation checked',
        },
        TreasuryAction.claimReview: {
          'claim_id': event,
          'claim_version': 1,
          'decision': 'correction_required',
          'reason': 'Amount/reference missing',
        },
        TreasuryAction.receiptVerify: {
          'client_id': user,
          'claim_id': event,
          'claim_version': 1,
          'amount': '90071992547409.91',
          'provider': 'gcash',
          'reference': 'Synthetic actual recipient reference',
          'effective_at': '2026-10-02T00:00:00+08:00',
          'evidence_id': ledger,
          'recipient_attestation': 'Checked actual recipient-side statement',
          'reason': 'Synthetic receipt',
        },
        TreasuryAction.receiptApply: {
          'receipt_id': event,
          'digest': 'a' * 64,
          'mode': 'combined',
          'total_amount': '20.01',
          'loans': [
            {'loan_id': ledger, 'expected_version': 0},
            {'loan_id': user, 'expected_version': 1},
          ],
          'intent': 'scheduled',
          'covered_dates': [],
          'extra_choice': 'regular_principal_reduction',
          'regular_past_due_followup': {
            'reason_code': 'promised_to_pay_later',
            'note': 'Synthetic follow-up',
            'promised_payment_date': '2026-10-03',
            'promised_amount': '1.00',
          },
          'effective_date': '2026-10-02',
        },
        TreasuryAction.disbursementRecord: {
          ...transaction,
          'purpose': 'expense',
          'direction': 'debit',
          'source_id': ledger,
          'source_version': 1,
          'payee_id': user,
          'destination_confirmed': false,
        },
        TreasuryAction.transferRecord: {
          ...transaction,
          'transfer_id': event,
          'leg': 'source',
          'other_account_id': ledger,
          'other_account_version': 1,
        },
        TreasuryAction.movementClassify: {
          'event_id': event,
          'event_version': 1,
          'classification': 'owner_withdrawal',
          'reason': 'Synthetic owner purpose',
        },
        TreasuryAction.movementCorrect: {
          'event_id': event,
          'event_version': 1,
          'evidence_id': ledger,
          'correction': 'false_observation',
          'reason': 'Evidence disproved original observation',
        },
        TreasuryAction.receiptApplicationReverse: {
          'receipt_id': event,
          'application_id': ledger,
          'reason': 'Protected official application reversal',
        },
        TreasuryAction.reconciliationObserve: {
          'reconciliation_id': event,
          'coverage_start': '2026-10-01T00:00:00+08:00',
          'cutoff': '2026-10-02T00:00:00+08:00',
          'actual_balance': '0.00',
          'evidence_id': ledger,
          'complete_history': true,
          'rows': [
            {
              'id': user,
              'provider': 'gcash',
              'reference': 'Synthetic row',
              'direction': 'debit',
              'amount': '20.01',
              'effective_at': '2026-10-01T10:00:00+08:00',
            },
          ],
        },
        TreasuryAction.reconciliationMatch: {
          'reconciliation_id': event,
          'reconciliation_version': 1,
          'observation_id': user,
          'event_id': ledger,
          'component': 'fee',
          'exception_reason': 'Synthetic separate fee evidence',
        },
        TreasuryAction.reconciliationClose: closing,
        TreasuryAction.reconciliationSupersede: {
          ...closing,
          'prior_reconciliation_id': user,
        },
      };
      final commands = [
        for (final item in fields.entries)
          TreasuryCommand(
            item.key,
            requestId: requestId,
            accountId: account,
            expectedVersion: item.key == TreasuryAction.accountConfigure
                ? 0
                : 1,
            fields: item.value,
          ).toJson(),
      ];
      expect(commands.length, 16);
      expect(commands.map((c) => c['action']).toSet().length, 16);
      expect(
        commands.any(
          (c) =>
              c.containsKey('actor_user_id') ||
              c.containsKey('verified_balance') ||
              c.containsKey('device_id'),
        ),
        isFalse,
      );
      expect(
        commands.firstWhere((c) => c['action'] == 'receipt_verify')['amount'],
        '90071992547409.91',
      );
      final output = Platform.environment['SPINA_TREASURY_CONTRACT_OUTPUT'];
      if (output != null) {
        await File(output).writeAsString(
          jsonEncode({'contract_version': 1, 'commands': commands}),
          flush: true,
        );
      }
    },
  );
  test(
    'timezone/explicit confirmation and strict follow-up prevent invented facts',
    () {
      expect(
        () => TreasuryCommand(
          TreasuryAction.openingPrepare,
          requestId: requestId,
          accountId: account,
          expectedVersion: 1,
          fields: {
            'cutoff': '2026-10-02T10:30:00',
            'amount': '0.00',
            'evidence_id': event,
            'reason': 'Synthetic',
          },
        ),
        throwsFormatException,
      );
      expect(
        () => TreasuryCommand(
          TreasuryAction.openingActivate,
          requestId: requestId,
          accountId: account,
          expectedVersion: 1,
          fields: {
            'opening_id': event,
            'opening_version': 1,
            'confirmed': false,
            'reason': 'Synthetic',
          },
        ),
        throwsFormatException,
      );
      expect(
        () =>
            const TreasuryField(
              'followup',
              'Past due follow-up',
              TreasuryFieldKind.followup,
            ).parse({
              'reason_code': 'promised_to_pay_later',
              'promised_payment_date': '2026-10-03',
              'promised_amount': '0.00',
            }),
        throwsFormatException,
      );
    },
  );
}
