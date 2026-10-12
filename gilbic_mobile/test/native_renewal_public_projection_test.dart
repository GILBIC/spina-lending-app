import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/management/current_risk_review.dart';
import 'package:gilbic_mobile/src/core/management/payout_accounting_evidence.dart';
import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';

void main() {
  for (final (name, stage) in [
    ('inherited-risk-context', 'stage_3_credit_impaired'),
    ('inherited-stage-two-context', 'stage_2_lifetime'),
  ]) {
    test(
      'actual protected $stage context keeps predecessor history separate',
      () {
        final raw = accountingObject(
          jsonDecode(
            File('test/fixtures/native-renewal-$name.json').readAsStringSync(),
          ),
        );
        final context = validateCurrentRiskContext(
          raw,
          bookId: raw['book_id'] as String,
          periodId: raw['period_id'] as String,
          loanId: raw['loan_id'] as String,
        );
        expect(context['ready'], isTrue);
        expect(context['prior_review'], isNull);
        expect(context['inherited_review'], raw['inherited_review']);
        expect(
          context['inherited_review']['loan_id'],
          isNot(context['loan_id']),
        );
        expect(context['inherited_review']['stage_label'], stage);
        expect(context.containsKey('credit_impaired_interest'), isFalse);
        expect(context['source_digest'], raw['source_digest']);
      },
    );
  }
  for (final name in [
    'modification_no_derecognition',
    'derecognition',
    'impaired-modification',
  ]) {
    final treatment = name == 'impaired-modification'
        ? 'modification_no_derecognition'
        : name;
    test('genuine synthetic PG $name public candidate and completion', () {
      final raw = accountingObject(
        jsonDecode(
          File('test/fixtures/native-renewal-$name.json').readAsStringSync(),
        ),
      );
      final c = accountingObject(raw['candidate']);
      final candidate = validateRenewalCandidate(
        c,
        bookId: c['book_id'] as String,
        accountId: c['treasury_account_id'] as String,
        payoutId: c['payout_id'] as String,
      );
      final completion = validatePayoutAccounting(
        accountingObject(raw['completion']),
        bookId: c['book_id'] as String,
        accountId: c['treasury_account_id'] as String,
        payoutId: c['payout_id'] as String,
        stage: 'completion',
      );
      expect(candidate['new_loan_id'], completion['loan_id']);
      expect(completion['renewal_decision'], treatment);
      expect(
        completion['measurement']['accounting_asset_continues'],
        treatment == 'modification_no_derecognition',
      );
      if (name == 'impaired-modification') {
        expect(candidate['predecessor_credit_impaired'], isTrue);
        expect(
          candidate['derecognition_blocker'],
          'successor_credit_adjusted_eir_policy_required',
        );
        expect(completion['predecessor_credit_impaired'], isTrue);
        // This current-date protected lifecycle has no aged unwind or adjustment.
        expect(completion['credit_impaired_boundary'], {
          'allowance_before': '0.00',
          'allowance_unwind': '0.00',
          'impairment_adjustment': '0.00',
          'allowance_after': '0.00',
        });
      }
    });
  }
}
