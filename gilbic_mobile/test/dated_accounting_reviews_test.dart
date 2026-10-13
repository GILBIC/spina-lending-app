import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/current_risk_review.dart';
import 'package:gilbic_mobile/src/core/management/elapsed_assessment_evidence.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'elapsed_assessment_evidence_test.dart' as f;
import 'management_elapsed_assessment_page_test.dart' as page;

Map<String, dynamic> get contextFixture => {
  'book_id': f.elapsedId(1),
  'period_id': f.elapsedId(3),
  'loan_id': f.elapsedId(4),
  'ready': true,
  'blockers': <String>[],
  'as_of_date': '2026-09-30',
  'source_digest': 'a' * 64,
  'schedule_id': f.elapsedId(8),
  'schedule_version': 1,
  'days_past_due': 35,
  'due_unpaid_amount': '100.00',
  'thirty_day_sicr_backstop_reached': true,
  'ninety_day_default_backstop_reached': false,
  'prior_review': null,
};
Map<String, dynamic> get riskInputs => {
  'stage_label': 'stage_2_lifetime',
  'default_label': false,
  'write_off_label': 'none',
  'recovery_label': 'none',
  'primary_evidence_basis': 'contractual_dpd',
  'evidence_reference': 'Dated borrower evidence',
  'review_note': 'Reviewed current dated repayment evidence.',
  'sicr_backstop_rebutted': false,
  'default_backstop_rebutted': false,
  'rebuttal_evidence_reference': null,
  'rebuttal_note': null,
  'write_off_evidence_reference': null,
  'write_off_note': null,
  'recovery_transaction_id': null,
};
Map<String, dynamic> get inheritedReview => {
  'id': 53,
  'review_version': 2,
  'loan_id': f.elapsedId(7),
  'stage_label': 'stage_3_credit_impaired',
  'default_label': false,
  'write_off_label': 'none',
  'recovery_label': 'cash_recovery_observed',
  'reviewed_at': '2026-09-29T03:00:00Z',
};
Map<String, dynamic> get cashCandidate => {
  'book': f.elapsedBook,
  'period_id': f.elapsedId(3),
  'loan_id': f.elapsedId(4),
  'application_id': f.elapsedId(5),
  'as_of_date': '2026-09-29',
  'ready': true,
  'blockers': <String>[],
  'source_digest': 'a' * 64,
  'gross_carrying_amount': '510.00',
  'opening_assessment_id': f.elapsedId(6),
  'opening_cutoff_date': '2026-09-28',
  'retained_review_id': null,
  'current_confirmation': false,
  'review': null,
};
Map<String, dynamic> get renewalCashOpening => {
  'opening_assessment_id': null,
  'opening_renewal_review_id': f.elapsedId(41),
  'opening_cutoff_date': '2026-09-29',
};
Map<String, dynamic> get cashInputs => {
  'scenarios': f.elapsedInputFixture['scenarios'],
  'review_rationale': f.elapsedInputFixture['review_rationale'],
};
Map<String, dynamic> get cashReview => {
  'review_id': f.elapsedId(7),
  'book_id': f.elapsedId(1),
  'period_id': f.elapsedId(3),
  'loan_id': f.elapsedId(4),
  'application_id': f.elapsedId(5),
  'as_of_date': '2026-09-29',
  'calculated_at': '2026-10-10T03:00:00Z',
  'source_digest': 'a' * 64,
  'confirmation_digest': 'b' * 64,
  'policy_version': 'native_impaired_cash_expected_receipts_v1',
  'loss_basis': 'gross_carrying_less_expected_pv',
  'opening_assessment_id': f.elapsedId(6),
  'opening_cutoff_date': '2026-09-28',
  'gross_carrying_amount': '510.00',
  'expected_cash_present_value': '110.00',
  'weighted_expected_cash_present_value_raw': '110.00',
  'currency_rounding_adjustment': '0.00',
  'ecl_amount': '400.00',
  'scenario_count': 2,
  'review_inputs': cashInputs,
};

class ReviewRepo extends page.Repo {
  bool cash = false, lose = false, inherited = false, renewalOpening = false;
  String inheritedStage = 'stage_3_credit_impaired';
  @override
  Future<Map<String, dynamic>> read(
    UserSession session, {
    required String deviceId,
    required String path,
  }) async {
    if (path.endsWith('/risk-review')) {
      return {
        ...contextFixture,
        if (inherited)
          'inherited_review': {
            ...inheritedReview,
            'stage_label': inheritedStage,
          },
      };
    }
    if (path.contains('/impaired-cash/')) {
      return {...cashCandidate, if (renewalOpening) ...renewalCashOpening};
    }
    if (path.contains('/period-elapsed-assessments/')) {
      return {
        ...f.elapsedCandidateFixture,
        'ready': false,
        'blockers': ['dated_review_required'],
        'source_digest': null,
        'eir': null,
        'gross_carrying_amount': null,
        'prior_allowance': null,
        'impaired_cash_reviews': cash
            ? [
                {...cashCandidate, if (renewalOpening) ...renewalCashOpening},
              ]
            : [],
      };
    }
    return super.read(session, deviceId: deviceId, path: path);
  }

  @override
  Future<Map<String, dynamic>> write(
    UserSession session, {
    required String deviceId,
    required String path,
    required Map<String, dynamic> body,
  }) async {
    writes.add((path, jsonDecode(jsonEncode(body)) as Map<String, dynamic>));
    if (lose) {
      throw const SpinaApiException(
        'Lost response',
        code: 'network_unavailable',
      );
    }
    if (path.endsWith('/risk-review')) {
      return {
        'review_id': 71,
        'reviewed_at': '2026-09-30T03:00:00Z',
        'as_of_date': '2026-09-30',
        'stage_label': body['review']['stage_label'],
        'default_label': body['review']['default_label'],
        'recovery_label': body['review']['recovery_label'],
      };
    }
    return {...cashReview, if (renewalOpening) ...renewalCashOpening};
  }
}

void main() {
  test(
    'same-day successor cash binds an opening renewal without inventing a fiscal assessment',
    () {
      Map<String, dynamic> project(Map<String, dynamic> value) =>
          validateImpairedCashCandidate(
            value,
            bookId: f.elapsedId(1),
            periodId: f.elapsedId(3),
            loanId: f.elapsedId(4),
            applicationId: f.elapsedId(5),
          );
      final raw = {...cashCandidate, ...renewalCashOpening}, c = project(raw);
      expect(c['opening_assessment_id'], isNull);
      expect(c['opening_renewal_review_id'], f.elapsedId(41));
      final p = {...cashReview, ...renewalCashOpening};
      Map<String, dynamic> retained(Map<String, dynamic> value) =>
          validateImpairedCashReview(
            value,
            bookId: f.elapsedId(1),
            periodId: f.elapsedId(3),
            loanId: f.elapsedId(4),
            applicationId: f.elapsedId(5),
            candidate: c,
          );
      expect(retained(p)['opening_renewal_review_id'], f.elapsedId(41));
      for (final patch in [
        {'opening_assessment_id': f.elapsedId(6)},
        {'opening_renewal_review_id': null},
        {'opening_cutoff_date': '2026-09-30'},
      ]) {
        expect(() => project({...raw, ...patch}), throwsFormatException);
      }
      expect(
        () => project({...cashCandidate, 'opening_cutoff_date': '2026-09-29'}),
        throwsFormatException,
      );
      expect(
        () => retained({...p, 'opening_renewal_review_id': f.elapsedId(42)}),
        throwsFormatException,
      );
    },
  );
  test(
    'inherited impairment context is exact to a different predecessor and strips private proof',
    () {
      Map<String, dynamic> project(Map<String, dynamic> inherited) =>
          validateCurrentRiskContext(
            {...contextFixture, 'inherited_review': inherited},
            bookId: f.elapsedId(1),
            periodId: f.elapsedId(3),
            loanId: f.elapsedId(4),
          );
      final current = project({
        ...inheritedReview,
        'private_snapshot': 'PRIVATE',
      });
      expect(current['inherited_review'], inheritedReview);
      expect(current['prior_review'], isNull);
      expect(jsonEncode(current), isNot(contains('PRIVATE')));
      for (final stage in ['stage_1_12_month', 'stage_2_lifetime']) {
        final predecessor = {
          ...inheritedReview,
          'stage_label': stage,
          'recovery_label': 'none',
        };
        final current = project(predecessor);
        expect(current['inherited_review'], predecessor);
        expect(current['prior_review'], isNull);
        expect(current.containsKey('credit_impaired_interest'), isFalse);
      }
      for (final patch in [
        {'loan_id': f.elapsedId(4)},
        {'loan_id': 'unknown'},
        {'stage_label': 'unknown'},
        {'review_version': 0},
        {'default_label': 'false'},
        {'reviewed_at': '2026-09-29'},
      ]) {
        expect(
          () => project({...inheritedReview, ...patch}),
          throwsFormatException,
        );
      }
      expect(
        validateCurrentRiskInputs({
          ...riskInputs,
          'recovery_label': 'cured',
          'primary_evidence_basis': 'verified_source_document',
        }, current)['recovery_label'],
        'cured',
      );
    },
  );
  test(
    'half-cent expected PV rounds final loss once without binary arithmetic',
    () {
      final c = validateImpairedCashCandidate(
        {...cashCandidate, 'gross_carrying_amount': '100.00'},
        bookId: f.elapsedId(1),
        periodId: f.elapsedId(3),
        loanId: f.elapsedId(4),
        applicationId: f.elapsedId(5),
      );
      final p = {
        ...cashReview,
        'gross_carrying_amount': '100.00',
        'expected_cash_present_value': '100.00',
        'weighted_expected_cash_present_value_raw': '99.995',
        'currency_rounding_adjustment': '0.01',
        'ecl_amount': '0.01',
      };
      Map<String, dynamic> review(Map<String, dynamic> value) =>
          validateImpairedCashReview(
            value,
            bookId: f.elapsedId(1),
            periodId: f.elapsedId(3),
            loanId: f.elapsedId(4),
            applicationId: f.elapsedId(5),
            candidate: c,
          );
      expect(review(p)['ecl_amount'], '0.01');
      expect(
        () => review({
          ...p,
          'ecl_amount': '0.00',
          'currency_rounding_adjustment': '0.00',
        }),
        throwsFormatException,
      );
    },
  );
  test(
    'current review rejects scope/DPD mismatch and requires explicit substantiated choices',
    () {
      final c = validateCurrentRiskContext(
        contextFixture,
        bookId: f.elapsedId(1),
        periodId: f.elapsedId(3),
        loanId: f.elapsedId(4),
      );
      expect(validateCurrentRiskInputs(riskInputs, c), riskInputs);
      for (final bad in [
        {'default_label': ''},
        {'stage_label': 'stage_1_12_month'},
        {'sicr_backstop_rebutted': true},
      ]) {
        expect(
          () => validateCurrentRiskInputs({...riskInputs, ...bad}, c),
          throwsFormatException,
        );
      }
      expect(
        () => validateCurrentRiskContext(
          {...contextFixture, 'thirty_day_sicr_backstop_reached': false},
          bookId: f.elapsedId(1),
          periodId: f.elapsedId(3),
          loanId: f.elapsedId(4),
        ),
        throwsFormatException,
      );
      final rebuttal = {
        ...riskInputs,
        'stage_label': 'stage_1_12_month',
        'primary_evidence_basis': 'verified_source_document',
        'sicr_backstop_rebutted': true,
        'rebuttal_evidence_reference': 'Separate evidence',
        'rebuttal_note': 'Separately supported review rationale.',
      };
      expect(
        validateCurrentRiskInputs(rebuttal, c)['stage_label'],
        'stage_1_12_month',
      );
    },
  );
  test(
    'cash date evidence binds exact event, carrying and retained request',
    () {
      final c = validateImpairedCashCandidate(
        cashCandidate,
        bookId: f.elapsedId(1),
        periodId: f.elapsedId(3),
        loanId: f.elapsedId(4),
        applicationId: f.elapsedId(5),
      );
      Map<String, dynamic> review(Map<String, dynamic> v) =>
          validateImpairedCashReview(
            v,
            bookId: f.elapsedId(1),
            periodId: f.elapsedId(3),
            loanId: f.elapsedId(4),
            applicationId: f.elapsedId(5),
            candidate: c,
          );
      expect(review(cashReview)['ecl_amount'], '400.00');
      for (final bad in [
        {'application_id': f.elapsedId(99)},
        {'expected_cash_present_value': '109.00'},
        {'opening_assessment_id': f.elapsedId(99)},
      ]) {
        expect(() => review({...cashReview, ...bad}), throwsFormatException);
      }
    },
  );
  for (final stage in ['stage_3_credit_impaired', 'stage_2_lifetime']) {
    testWidgets(
      '$stage inherited history leaves current labels blank and retains only explicit unchanged review evidence',
      (tester) async {
        final repo = ReviewRepo()
          ..lose = true
          ..inherited = true
          ..inheritedStage = stage;
        final reviewedInputs = {
          ...riskInputs,
          'recovery_label': stage == 'stage_3_credit_impaired'
              ? 'cured'
              : 'none',
          'primary_evidence_basis': 'verified_source_document',
        };
        final base = page.session();
        final actor = UserSession(
          userId: base.userId,
          username: base.username,
          displayName: base.displayName,
          role: base.role,
          rawRole: base.rawRole,
          accessToken: base.accessToken,
          permissions: [
            ...base.permissions,
            'accounting.ecl.credit_risk_label.review',
          ],
        );
        await page.pump(tester, repo, actor: actor);
        await page.lookup(tester);
        await page.tap(tester, 'elapsed-current-risk');
        const inheritedTitle = 'Inherited credit-risk review';
        await tester.scrollUntilVisible(
          find.textContaining('$inheritedTitle:'),
          250,
          scrollable: find.byType(Scrollable).first,
        );
        expect(find.textContaining('$inheritedTitle: 53'), findsOneWidget);
        await page.tap(tester, 'elapsed-current-risk-review');
        expect(repo.writes, isEmpty);
        expect(find.byKey(const Key('elapsed-confirm')), findsNothing);
        await tester.scrollUntilVisible(
          find.byKey(const Key('elapsed-current-risk-stage_label')),
          -250,
          scrollable: find.byType(Scrollable).first,
        );
        await tester.pumpAndSettle();
        for (final key in [
          'stage_label',
          'default_label',
          'write_off_label',
          'recovery_label',
          'primary_evidence_basis',
          'sicr_backstop_rebutted',
          'default_backstop_rebutted',
        ]) {
          await page.tap(tester, 'elapsed-current-risk-$key');
          await tester.tap(
            find.text(reviewedInputs[key].toString().replaceAll('_', ' ')).last,
          );
          await tester.pumpAndSettle();
        }
        await page.enter(
          tester,
          'elapsed-current-risk-evidence_reference',
          riskInputs['evidence_reference'] as String,
        );
        await page.enter(
          tester,
          'elapsed-current-risk-review_note',
          riskInputs['review_note'] as String,
        );
        await page.tap(tester, 'elapsed-current-risk-review');
        expect(repo.writes, isEmpty);
        await page.tap(tester, 'elapsed-confirm');
        repo.lose = false;
        await page.tap(tester, 'elapsed-retry');
        expect(repo.writes[0].$2, repo.writes[1].$2);
        expect(
          repo.writes[0].$2['review']['recovery_label'],
          reviewedInputs['recovery_label'],
        );
        expect(
          find.textContaining('Credit-risk review retained'),
          findsOneWidget,
        );
        expect(find.byKey(const Key('elapsed-post')), findsNothing);
      },
    );
  }
  testWidgets(
    'blocked fiscal assessment can retain dated cash measurement without posting',
    (tester) async {
      final repo = ReviewRepo()
        ..cash = true
        ..renewalOpening = true;
      await page.pump(tester, repo);
      await page.lookup(tester);
      await page.tap(tester, 'elapsed-cash-${f.elapsedId(5)}');
      expect(
        find.textContaining('Opening renewal review: ${f.elapsedId(41)}'),
        findsOneWidget,
      );
      expect(find.byKey(const Key('elapsed-evidence_reference')), findsNothing);
      final inputs = f.elapsedInputFixture,
          scenarios = inputs['scenarios'] as List;
      for (var i = 0; i < 2; i++) {
        final s = scenarios[i] as Map;
        for (final key in [
          'scenario_key',
          'probability',
          'evidence_reference',
          'management_rationale',
        ]) {
          await page.enter(tester, 'elapsed-s$i-$key', s[key] as String);
        }
        await page.tap(tester, 'elapsed-s$i-evidence');
        await tester.tap(
          find.text('Forecast ${i + 1} · Forecast reference ${i + 1}').last,
        );
        await tester.pumpAndSettle();
        await page.enter(tester, 'elapsed-s$i-c0-date', '2026-10-20');
        await page.enter(tester, 'elapsed-s$i-c0-amount', '5000.00');
      }
      await page.enter(
        tester,
        'elapsed-review_rationale',
        inputs['review_rationale'] as String,
      );
      await page.tap(tester, 'elapsed-prepare');
      expect(repo.writes, isEmpty);
      await page.tap(tester, 'elapsed-confirm');
      expect(repo.writes.single.$1, endsWith('/review'));
      expect(repo.writes.single.$2.containsKey('target_allowance'), false);
      expect(
        find.textContaining('Cash-date measurement retained'),
        findsOneWidget,
      );
      expect(find.byKey(const Key('elapsed-post')), findsNothing);
    },
  );
}
