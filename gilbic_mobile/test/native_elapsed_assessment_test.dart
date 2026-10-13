import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/elapsed_assessment_evidence.dart';
import 'elapsed_assessment_evidence_test.dart' as f;
import 'management_elapsed_assessment_page_test.dart' as page;

Map<String, dynamic> get impairedInterest => {
  'basis': 'original_eir_on_reviewed_net_carrying',
  'opening_assessment_id': f.elapsedId(30),
  'opening_cutoff_date': '2026-09-28',
  'impairment_boundary_date': '2026-09-28',
  'gross_interest': '15.10',
  'net_interest': '5.10',
  'allowance_unwind': '10.00',
};
Map<String, dynamic> get impairedCandidate => {
  ...f.lifetimeCandidateFixture,
  'gross_carrying_amount': '515.10',
  'prior_allowance': '600.00',
  'eir': {
    'cumulative_interest': '15.10',
    'prior_recognized_interest': '10.00',
    'incremental_interest': '5.10',
  },
  'eligible_credit_risk_review': {
    ...f.retainedRiskFixture,
    'stage_label': 'stage_3_credit_impaired',
    'default_label': true,
  },
  'credit_impaired_interest': impairedInterest,
};
Map<String, dynamic> get impairedPreparation => {
  ...f.lifetimePreparationFixture,
  'stage_label': 'stage_3_credit_impaired',
  'default_label': true,
  'loss_basis': 'gross_carrying_less_expected_pv',
  'gross_carrying_amount': '515.10',
  'expected_cash_present_value': '111.10',
  'weighted_expected_cash_present_value_raw': '111.10',
  'currency_rounding_adjustment': '0.00',
  'ecl_amount': '404.00',
  'prior_allowance': '600.00',
  'allowance_delta': '-206.00',
  'cumulative_interest': '15.10',
  'incremental_interest': '5.10',
  'credit_impaired_interest': impairedInterest,
};
Map<String, dynamic> get renewedCandidate => {
  ...f.settledCandidateFixture,
  'settled_by_exact_payoff': false,
  'payoff_review_id': null,
  'settled_by_exact_renewal': true,
  'renewal_review_id': f.elapsedId(40),
};
Map<String, dynamic> get renewedPreparation => {
  ...f.settledPreparationFixture,
  'policy_version': 'regular_exact_renewal_zero_ecl_v1',
  'settled_by_exact_payoff': false,
  'payoff_review_id': null,
  'settled_by_exact_renewal': true,
  'renewal_review_id': f.elapsedId(40),
  'review_inputs': {
    'renewal_review_id': f.elapsedId(40),
    'review_rationale': f.settledRationale,
  },
};

class NativeRepo extends page.Repo {
  NativeRepo(this.candidate, this.preparation);
  final Map<String, dynamic> candidate, preparation;
  @override
  Future<Map<String, dynamic>> read(
    UserSession session, {
    required String deviceId,
    required String path,
  }) async => path.contains('/period-elapsed-assessments/')
      ? candidate
      : super.read(session, deviceId: deviceId, path: path);
  @override
  Future<Map<String, dynamic>> write(
    UserSession session, {
    required String deviceId,
    required String path,
    required Map<String, dynamic> body,
  }) async {
    if (path.endsWith('/prepare-renewed') || path.endsWith('/prepare-risk')) {
      writes.add((path, body));
      return preparation;
    }
    return super.write(session, deviceId: deviceId, path: path, body: body);
  }
}

void main() {
  Map<String, dynamic> signedInterest() => {
    ...impairedInterest,
    'gross_interest': '1.63',
    'net_interest': '1.64',
    'allowance_unwind': '-0.01',
    'currency_rounding_adjustment': '-0.01',
  };
  Map<String, dynamic> signedCandidate() => {
    ...impairedCandidate,
    'gross_carrying_amount': '1008.16',
    'prior_allowance': '0.01',
    'eir': {
      'cumulative_interest': '8.16',
      'prior_recognized_interest': '6.53',
      'incremental_interest': '1.63',
    },
    'credit_impaired_interest': signedInterest(),
  };
  Map<String, dynamic> signedPreparation() => {
    ...impairedPreparation,
    'gross_carrying_amount': '1008.16',
    'prior_allowance': '0.01',
    'expected_cash_present_value': '1008.15',
    'weighted_expected_cash_present_value_raw': '1008.15',
    'ecl_amount': '0.01',
    'allowance_delta': '0.01',
    'cumulative_interest': '8.16',
    'incremental_interest': '1.63',
    'credit_impaired_interest': signedInterest(),
  };
  test(
    'cent rounding retains source gross and direct net with signed reconciliation disclosure',
    () {
      Map<String, dynamic> candidate(Map<String, dynamic> v) =>
          validateElapsedCandidate(
            v,
            bookId: f.elapsedId(1),
            periodId: f.elapsedId(3),
            loanId: f.elapsedId(4),
          );
      final c = candidate(signedCandidate());
      Map<String, dynamic> prepare(Map<String, dynamic> v) =>
          validateElapsedPreparation(
            v,
            bookId: f.elapsedId(1),
            periodId: f.elapsedId(3),
            loanId: f.elapsedId(4),
            candidate: c,
          );
      expect(c['credit_impaired_interest'], signedInterest());
      expect(prepare(signedPreparation())['allowance_delta'], '0.01');
      for (final patch in <Map<String, dynamic>>[
        {'allowance_unwind': '-0.02'},
        {'allowance_unwind': -0.01},
        {'allowance_unwind': '-10000000000000000.00'},
        {'currency_rounding_adjustment': null},
        {'currency_rounding_adjustment': '0.00'},
        {'currency_rounding_adjustment': '1.64'},
        {'gross_interest': '-0.01'},
        {'net_interest': '-0.01'},
      ]) {
        expect(
          () => candidate({
            ...signedCandidate(),
            'credit_impaired_interest': {...signedInterest(), ...patch},
          }),
          throwsFormatException,
        );
      }
      final absent = signedInterest()..remove('currency_rounding_adjustment');
      expect(
        () => candidate({
          ...signedCandidate(),
          'credit_impaired_interest': absent,
        }),
        throwsFormatException,
      );
      for (final patch in <Map<String, dynamic>>[
        {'allowance_delta': '-0.01'},
        {'prior_allowance': '-0.01'},
        {'ecl_amount': '-0.01'},
        {
          'credit_impaired_interest': {
            ...signedInterest(),
            'currency_rounding_adjustment': '-0.02',
          },
        },
      ]) {
        expect(
          () => prepare({...signedPreparation(), ...patch}),
          throwsFormatException,
        );
      }
    },
  );
  testWidgets(
    'signed source interest shows reconciliation and rounding separately',
    (tester) async {
      final repo = NativeRepo({
        ...signedCandidate(),
        'preparation': signedPreparation(),
      }, signedPreparation());
      await page.pump(tester, repo);
      await page.lookup(tester);
      await page.tap(tester, 'elapsed-post');
      for (final label in [
        'Period net interest revenue: 1.64',
        'Gross/net allowance reconciliation: -0.01',
        'Interest currency rounding adjustment: -0.01',
      ]) {
        await tester.scrollUntilVisible(
          find.textContaining(label),
          250,
          scrollable: find.byType(Scrollable).first,
        );
        await tester.pumpAndSettle();
        expect(find.textContaining(label), findsOneWidget);
      }
    },
  );
  test(
    'renewal opening interest keeps distinct provenance and rejects mixed or future boundaries',
    () {
      final interest = {
        ...impairedInterest,
        'opening_assessment_id': null,
        'opening_renewal_review_id': f.elapsedId(41),
      };
      Map<String, dynamic> candidate(Map<String, dynamic> opening) =>
          validateElapsedCandidate(
            {...impairedCandidate, 'credit_impaired_interest': opening},
            bookId: f.elapsedId(1),
            periodId: f.elapsedId(3),
            loanId: f.elapsedId(4),
          );
      final c = candidate(interest);
      expect(c['credit_impaired_interest']['opening_assessment_id'], isNull);
      expect(
        c['credit_impaired_interest']['opening_renewal_review_id'],
        f.elapsedId(41),
      );
      Map<String, dynamic> prepare(Map<String, dynamic> opening) =>
          validateElapsedPreparation(
            {...impairedPreparation, 'credit_impaired_interest': opening},
            bookId: f.elapsedId(1),
            periodId: f.elapsedId(3),
            loanId: f.elapsedId(4),
            candidate: c,
          );
      expect(
        prepare(
          interest,
        )['credit_impaired_interest']['opening_renewal_review_id'],
        f.elapsedId(41),
      );
      for (final patch in [
        {'opening_assessment_id': f.elapsedId(30)},
        {'opening_renewal_review_id': null},
        {
          'opening_cutoff_date': '2026-10-01',
          'impairment_boundary_date': '2026-10-01',
        },
        {'basis': 'gross_before_initial_impaired_cutoff'},
      ]) {
        expect(() => candidate({...interest, ...patch}), throwsFormatException);
      }
      expect(
        () => prepare({
          ...interest,
          'opening_renewal_review_id': f.elapsedId(42),
        }),
        throwsFormatException,
      );
    },
  );
  testWidgets(
    'recovered net-interest review identifies its opening renewal without a fiscal assessment',
    (tester) async {
      final interest = {
        ...impairedInterest,
        'opening_assessment_id': null,
        'opening_renewal_review_id': f.elapsedId(41),
      };
      final preparation = {
        ...impairedPreparation,
        'credit_impaired_interest': interest,
      };
      final repo = NativeRepo({
        ...impairedCandidate,
        'credit_impaired_interest': interest,
        'preparation': preparation,
      }, preparation);
      await page.pump(tester, repo);
      await page.lookup(tester);
      await page.tap(tester, 'elapsed-post');
      await tester.scrollUntilVisible(
        find.textContaining('Opening renewal review:'),
        250,
        scrollable: find.byType(Scrollable).first,
      );
      expect(
        find.textContaining('Opening renewal review: ${f.elapsedId(41)}'),
        findsOneWidget,
      );
      expect(
        find.textContaining('Opening assessment reference:'),
        findsNothing,
      );
      expect(repo.writes, isEmpty);
    },
  );
  test(
    'stage remains independent from actual default and cash recovery labels',
    () {
      final c = validateElapsedCandidate(
        {
          ...f.lifetimeCandidateFixture,
          'eligible_credit_risk_review': {
            ...f.retainedRiskFixture,
            'default_label': true,
            'recovery_label': 'cash_recovery_observed',
          },
        },
        bookId: f.elapsedId(1),
        periodId: f.elapsedId(3),
        loanId: f.elapsedId(4),
      );
      expect(
        validateElapsedPreparation(
          {...f.lifetimePreparationFixture, 'default_label': true},
          bookId: f.elapsedId(1),
          periodId: f.elapsedId(3),
          loanId: f.elapsedId(4),
          candidate: c,
        )['loss_basis'],
        'contractual_cash_shortfall',
      );
      final impaired = validateElapsedCandidate(
        {
          ...impairedCandidate,
          'eligible_credit_risk_review': {
            ...f.retainedRiskFixture,
            'stage_label': 'stage_3_credit_impaired',
            'default_label': false,
          },
        },
        bookId: f.elapsedId(1),
        periodId: f.elapsedId(3),
        loanId: f.elapsedId(4),
      );
      expect(
        validateElapsedPreparation(
          {...impairedPreparation, 'default_label': false},
          bookId: f.elapsedId(1),
          periodId: f.elapsedId(3),
          loanId: f.elapsedId(4),
          candidate: impaired,
        )['loss_basis'],
        'gross_carrying_less_expected_pv',
      );
      expect(
        () => validateElapsedCandidate(
          {
            ...f.lifetimeCandidateFixture,
            'eligible_credit_risk_review': {
              ...f.retainedRiskFixture,
              'stage_label': 'stage_1_12_month',
              'default_label': true,
            },
          },
          bookId: f.elapsedId(1),
          periodId: f.elapsedId(3),
          loanId: f.elapsedId(4),
        ),
        throwsFormatException,
      );
    },
  );
  test(
    'reviewed Stage 1 preserves exact retained rebuttal authority and 12-month policy',
    () {
      final c = validateElapsedCandidate(
        {
          ...f.lifetimeCandidateFixture,
          'days_past_due': 35,
          'eligible_credit_risk_review': {
            ...f.retainedRiskFixture,
            'stage_label': 'stage_1_12_month',
          },
        },
        bookId: f.elapsedId(1),
        periodId: f.elapsedId(3),
        loanId: f.elapsedId(4),
      );
      final p = {
        ...f.lifetimePreparationFixture,
        'policy_version':
            'historical_native_reviewed_12_month_cash_shortfall_v1',
        'stage_label': 'stage_1_12_month',
        'loss_horizon': '12_month',
      };
      Map<String, dynamic> prepare(Map<String, dynamic> value) =>
          validateElapsedPreparation(
            value,
            bookId: f.elapsedId(1),
            periodId: f.elapsedId(3),
            loanId: f.elapsedId(4),
            candidate: c,
          );
      expect(prepare(p)['loss_horizon'], '12_month');
      expect(
        () => prepare({
          ...p,
          'policy_version': 'historical_native_lifetime_cash_shortfall_v1',
          'loss_horizon': 'lifetime',
        }),
        throwsFormatException,
      );
    },
  );
  test(
    'Stage 3 gross-minus-PV and aggregate unwind are exact, with no hidden fallback',
    () {
      final c = validateElapsedCandidate(
        impairedCandidate,
        bookId: f.elapsedId(1),
        periodId: f.elapsedId(3),
        loanId: f.elapsedId(4),
      );
      Map<String, dynamic> prepare(Map<String, dynamic> p) =>
          validateElapsedPreparation(
            p,
            bookId: f.elapsedId(1),
            periodId: f.elapsedId(3),
            loanId: f.elapsedId(4),
            candidate: c,
          );
      expect(prepare(impairedPreparation)['allowance_delta'], '-206.00');
      for (final bad in [
        {'loss_basis': 'contractual_cash_shortfall'},
        {'expected_cash_present_value': '110.00'},
        {'allowance_delta': '-196.00'},
        {
          'credit_impaired_interest': {
            ...impairedInterest,
            'allowance_unwind': '9.99',
          },
        },
      ]) {
        expect(
          () => prepare({...impairedPreparation, ...bad}),
          throwsFormatException,
        );
      }
      expect(
        prepare({
          ...impairedPreparation,
          'expected_cash_present_value': '0.00',
          'weighted_expected_cash_present_value_raw': '0.00',
          'currency_rounding_adjustment': '0.00',
          'ecl_amount': '515.10',
          'allowance_delta': '-94.90',
        })['ecl_amount'],
        '515.10',
      );
    },
  );
  testWidgets('renewed old loan uses separate reviewed zero assessment', (
    tester,
  ) async {
    final repo = NativeRepo(renewedCandidate, renewedPreparation);
    await page.pump(tester, repo);
    await page.lookup(tester);
    expect(find.byKey(const Key('elapsed-prepare')), findsNothing);
    await page.enter(tester, 'elapsed-renewed-rationale', f.settledRationale);
    await page.tap(tester, 'elapsed-prepare-renewed');
    expect(repo.writes, isEmpty);
    await page.tap(tester, 'elapsed-confirm');
    expect(repo.writes.single.$1, endsWith('/prepare-renewed'));
    expect(repo.writes.single.$2['renewal_review_id'], f.elapsedId(40));
    expect(repo.writes.single.$2.containsKey('scenarios'), false);
    await page.tap(tester, 'elapsed-post');
    expect(repo.writes.length, 1);
  });
  testWidgets(
    'recovered Stage 3 assessment separates net interest, gross tail and allowance adjustment',
    (tester) async {
      final repo = NativeRepo({
        ...impairedCandidate,
        'preparation': impairedPreparation,
      }, impairedPreparation);
      await page.pump(tester, repo);
      await page.lookup(tester);
      await page.tap(tester, 'elapsed-post');
      for (final label in [
        'Period net interest revenue: 5.10',
        'Impairment adjustment: -206.00',
        'Total allowance balance change: -196.00',
      ]) {
        await tester.scrollUntilVisible(
          find.textContaining(label),
          250,
          scrollable: find.byType(Scrollable).first,
        );
        await tester.pumpAndSettle();
        expect(find.textContaining(label), findsOneWidget);
      }
    },
  );
}
