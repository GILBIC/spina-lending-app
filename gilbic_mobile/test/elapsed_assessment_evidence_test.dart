import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/management/elapsed_assessment_evidence.dart';

String elapsedId(int n) =>
    '00000000-0000-4000-8000-${n.toString().padLeft(12, '0')}';
Map<String, dynamic> get elapsedBook => {
  'status': 'configured',
  'book_id': elapsedId(1),
  'kind': 'owner_operations',
  'entity_label': 'Owner books',
};
Map<String, dynamic> get elapsedCandidateFixture => {
  'book': elapsedBook,
  'period_id': elapsedId(3),
  'loan_id': elapsedId(4),
  'ready': true,
  'blockers': <String>[],
  'as_of_date': '2026-09-30',
  'source_digest': 'a' * 64,
  'current_confirmation': false,
  'eir': {
    'cumulative_interest': '62.58',
    'prior_recognized_interest': '31.20',
    'incremental_interest': '31.38',
  },
  'gross_carrying_amount': '5062.58',
  'prior_allowance': '4.00',
  'days_past_due': 0,
  'preparation': null,
  'comprehensive_source_coverage': false,
};
Map<String, dynamic> get elapsedPreparationFixture => {
  'preparation_id': elapsedId(5),
  'book_id': elapsedId(1),
  'period_id': elapsedId(3),
  'loan_id': elapsedId(4),
  'as_of_date': '2026-09-30',
  'source_digest': 'a' * 64,
  'confirmation_digest': 'b' * 64,
  'calculated_at': '2026-10-05T08:12:00+00:00',
  'policy_version': 'historical_original_timing_cash_shortfall_v1',
  'cumulative_interest': '62.58',
  'incremental_interest': '31.38',
  'prior_allowance': '4.00',
  'ecl_amount': '3.50',
  'allowance_delta': '-0.50',
  'scenario_count': 2,
  'review_inputs': validateElapsedInputs(elapsedInputFixture, '2026-09-30'),
  'comprehensive_source_coverage': false,
};
Map<String, dynamic> get elapsedInputFixture => {
  'evidence_reference': 'Risk review 123',
  'review_note': 'Contractual repayment facts reviewed at the selected cutoff.',
  'review_rationale':
      'Reviewed the dated evidence and reasonable expected receipt scenarios.',
  'scenarios': [
    for (var i = 0; i < 2; i++)
      {
        'scenario_key': 'Case ${i + 1}',
        'probability': i == 0 ? '0.7' : '0.3',
        'evidence_reference': 'Forecast ${i + 1}',
        'management_rationale':
            'Documented plausible receipts supported by dated economic evidence.',
        'forward_evidence_ids': [elapsedId(10 + i)],
        'expected_cash_flows': [
          {'cash_date': '2026-10-20', 'amount': '5000.00'},
        ],
      },
  ],
};
const settledRationale =
    'Reviewed the exact posted payoff and complete settlement evidence.';
Map<String, dynamic> get settledCandidateFixture => {
  ...elapsedCandidateFixture,
  'settled_by_exact_payoff': true,
  'payoff_review_id': elapsedId(20),
  'gross_carrying_amount': '0.00',
  'eir': {
    'cumulative_interest': '62.58',
    'prior_recognized_interest': '62.58',
    'incremental_interest': '0.00',
  },
};
Map<String, dynamic> get settledPreparationFixture => {
  ...elapsedPreparationFixture,
  'settled_by_exact_payoff': true,
  'payoff_review_id': elapsedId(20),
  'policy_version': 'regular_exact_payoff_zero_ecl_v1',
  'scenario_count': 0,
  'incremental_interest': '0.00',
  'ecl_amount': '0.00',
  'allowance_delta': '-4.00',
  'review_inputs': {
    'payoff_review_id': elapsedId(20),
    'review_rationale': settledRationale,
  },
};
Map<String, dynamic> get retainedRiskFixture => {
  'id': 71,
  'stage_label': 'stage_2_lifetime',
  'default_label': false,
  'recovery_label': 'none',
  'write_off_label': 'none',
  'reviewed_at': '2026-09-30T08:00:00+00:00',
  'as_of_date': '2026-09-30',
  'evidence_reference': 'Dated borrower credit review',
  'primary_evidence_basis': 'verified_source_document',
};
Map<String, dynamic> get lifetimeCandidateFixture => {
  ...elapsedCandidateFixture,
  'eligible_credit_risk_review': retainedRiskFixture,
};
Map<String, dynamic> get lifetimePreparationFixture => {
  ...elapsedPreparationFixture,
  'policy_version': 'historical_native_lifetime_cash_shortfall_v1',
  'credit_risk_review_id': 71,
  'stage_label': 'stage_2_lifetime',
  'default_label': false,
  'loss_horizon': 'lifetime',
  'loss_basis': 'contractual_cash_shortfall',
  'review_inputs': {
    'credit_risk_review_id': 71,
    'scenarios': elapsedInputFixture['scenarios'],
    'review_rationale': elapsedInputFixture['review_rationale'],
  },
};
void main() {
  test(
    'lifetime preparation binds exact stage, loss basis and retained review',
    () {
      final c = validateElapsedCandidate(
        lifetimeCandidateFixture,
        bookId: elapsedId(1),
        periodId: elapsedId(3),
        loanId: elapsedId(4),
      );
      Map<String, dynamic> prepare(Map<String, dynamic> value) =>
          validateElapsedPreparation(
            value,
            bookId: elapsedId(1),
            periodId: elapsedId(3),
            loanId: elapsedId(4),
            candidate: c,
          );
      expect(prepare(lifetimePreparationFixture)['credit_risk_review_id'], 71);
      for (final wrong in [
        {'credit_risk_review_id': 72},
        {'default_label': true},
        {'loss_horizon': '12_month'},
        {'loss_basis': 'gross_carrying_less_expected_pv'},
      ]) {
        expect(
          () => prepare({...lifetimePreparationFixture, ...wrong}),
          throwsFormatException,
        );
      }
      expect(() => prepare(elapsedPreparationFixture), throwsFormatException);
    },
  );
  test(
    'eligible retained risk review is exact to the cutoff and private-safe',
    () {
      Map<String, dynamic> candidate(Map<String, dynamic> value) =>
          validateElapsedCandidate(
            value,
            bookId: elapsedId(1),
            periodId: elapsedId(3),
            loanId: elapsedId(4),
          );
      final result = candidate({
        ...lifetimeCandidateFixture,
        'eligible_credit_risk_review': {
          ...retainedRiskFixture,
          'private': 'PRIVATE',
        },
      });
      expect(result['eligible_credit_risk_review'], retainedRiskFixture);
      expect(result.toString(), isNot(contains('PRIVATE')));
      for (final wrong in [
        {'id': '71'},
        {'id': 0},
        {'as_of_date': '2026-10-05'},
        {'stage_label': 'unknown_stage'},
        {'default_label': 'false'},
        {'recovery_label': 'invented_cure'},
        {'reviewed_at': '2026-10-05'},
      ]) {
        expect(
          () => candidate({
            ...lifetimeCandidateFixture,
            'eligible_credit_risk_review': {...retainedRiskFixture, ...wrong},
          }),
          throwsFormatException,
        );
      }
    },
  );
  test(
    'settled cutoff requires exact payoff, zero carrying and zero-ECL policy',
    () {
      Map<String, dynamic> candidate(Map<String, dynamic> value) =>
          validateElapsedCandidate(
            value,
            bookId: elapsedId(1),
            periodId: elapsedId(3),
            loanId: elapsedId(4),
          );
      final settled = candidate(settledCandidateFixture);
      expect(settled['settled_by_exact_payoff'], true);
      Map<String, dynamic> prepared(Map<String, dynamic> value) =>
          validateElapsedPreparation(
            value,
            bookId: elapsedId(1),
            periodId: elapsedId(3),
            loanId: elapsedId(4),
            candidate: settled,
          );
      expect(prepared(settledPreparationFixture)['scenario_count'], 0);
      for (final wrong in [
        {'gross_carrying_amount': '0.01'},
        {'payoff_review_id': null},
        {'settled_by_exact_payoff': 'true'},
      ]) {
        expect(
          () => candidate({...settledCandidateFixture, ...wrong}),
          throwsFormatException,
        );
      }
      for (final wrong in [
        {'ecl_amount': '0.01', 'allowance_delta': '-3.99'},
        {'scenario_count': 2},
        {'payoff_review_id': elapsedId(21)},
      ]) {
        expect(
          () => prepared({...settledPreparationFixture, ...wrong}),
          throwsFormatException,
        );
      }
    },
  );
  test(
    'historical candidate and retained calculation strip private source snapshots',
    () {
      final v = elapsedCandidateFixture;
      v['snapshot'] = {'secret': 'PRIVATE'};
      final result = validateElapsedCandidate(
        v,
        bookId: elapsedId(1),
        periodId: elapsedId(3),
        loanId: elapsedId(4),
      );
      expect(result.containsKey('snapshot'), false);
      final p = validateElapsedPreparation(
        elapsedPreparationFixture,
        bookId: elapsedId(1),
        periodId: elapsedId(3),
        loanId: elapsedId(4),
        candidate: result,
      );
      expect(p['allowance_delta'], '-0.50');
      expect(p['calculated_at'], '2026-10-05T08:12:00+00:00');
    },
  );
  test(
    'wrong scope, invented money and inconsistent allowance are refused',
    () {
      expect(
        () => validateElapsedCandidate(
          elapsedCandidateFixture,
          bookId: elapsedId(99),
          periodId: elapsedId(3),
          loanId: elapsedId(4),
        ),
        throwsFormatException,
      );
      expect(
        () => validateElapsedPreparation(
          {...elapsedPreparationFixture, 'allowance_delta': '0.50'},
          bookId: elapsedId(1),
          periodId: elapsedId(3),
          loanId: elapsedId(4),
        ),
        throwsFormatException,
      );
      expect(
        () => validateElapsedPreparation(
          {...elapsedPreparationFixture, 'ecl_amount': 3.5},
          bookId: elapsedId(1),
          periodId: elapsedId(3),
          loanId: elapsedId(4),
        ),
        throwsFormatException,
      );
    },
  );
  test(
    'risk scenarios preserve exact decimal strings with distinct dated receipts',
    () {
      final result = validateElapsedInputs(elapsedInputFixture, '2026-09-30');
      expect((result['scenarios'] as List).first['probability'], '0.7');
      expect(result['risk_review']['as_of_date'], '2026-09-30');
      final bad = elapsedInputFixture;
      (bad['scenarios'] as List).first['probability'] = 0.7;
      expect(
        () => validateElapsedInputs(bad, '2026-09-30'),
        throwsFormatException,
      );
    },
  );
  test(
    'probabilities must total exactly one and invalid or before-cutoff receipts fail',
    () {
      final bad = elapsedInputFixture;
      (bad['scenarios'] as List).first['probability'] = '0.700000000001';
      expect(
        () => validateElapsedInputs(bad, '2026-09-30'),
        throwsFormatException,
      );
      final dates = elapsedInputFixture;
      (dates['scenarios'] as List)
              .first['expected_cash_flows'][0]['cash_date'] =
          '2026-02-30';
      expect(
        () => validateElapsedInputs(dates, '2026-09-30'),
        throwsFormatException,
      );
    },
  );
}
