import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/management/payout_accounting_evidence.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'management_payout_accounting_page_test.dart'
    show PayoutFixture, pumpPayout, payoutCompletion, lookupPayout;
import 'management_protected_accounting_page_test.dart'
    show id, digest, tap, enter;

UserSession renewalSession() => UserSession(
  userId: id(2),
  username: 'manager',
  displayName: 'Manager',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'token',
  permissions: const [
    'accounting.view',
    'accounting.journal.manage',
    'accounting.renewal_treatment_decision.manage',
  ],
);

Map<String, dynamic> renewalCandidateFixture() => {
  'policy_version': 'native_regular_renewal_measurement_v1',
  'book_id': id(1),
  'payout_id': id(5),
  'execution_id': id(31),
  'old_loan_id': id(32),
  'new_loan_id': id(11),
  'accounting_asset_id': id(32),
  'treasury_account_id': id(3),
  'effective_date': '2026-09-30',
  'source_digest': digest,
  'fresh_cash': '100.00',
  'old_loan_component': '80.00',
  'old_accrued_interest': '10.00',
  'old_allowance': '2.00',
  'old_gross_carrying': '90.00',
  'original_daily_eir': '0.001',
  'revised_pv': '195.00',
  'nominal_settlement': '100.00',
  'contractual_total': '220.00',
  'schedule_id': id(33),
  'retained_review': null,
  'private_snapshot': 'SECRET',
};
Map<String, dynamic> renewalInputsFixture() => {
  'decision': 'modification_no_derecognition',
  'accounting_policy_reference': 'Reviewed policy 1',
  'qualitative_assessment': <String, dynamic>{
    'signed_contract_reviewed': true,
    'cash_flow_terms_reviewed': true,
    'substantial_change_assessed': true,
    'decision_basis':
        'Reviewed contractual changes against the retained accounting policy.',
  },
  'decision_rationale':
      'The reviewed contract changes retain the existing accounting asset.',
  'settlement_consideration': '95.00',
  'settlement_rebate': '5.00',
  'settlement_basis':
      'The signed settlement document specifies this consideration and rebate.',
  'new_initial_fair_value': null,
  'fair_value_effective_date': null,
  'fair_value_basis': null,
  'day_one_difference_rationale': null,
};
Map<String, dynamic> renewalCompletionFixture() => {
  ...payoutCompletion(),
  'accounting_policy_version': 'native_regular_renewal_completion_v1',
  'old_loan_id': id(32),
  'accounting_asset_id': id(32),
  'renewal_review_id': id(41),
  'renewal_decision': 'modification_no_derecognition',
  'measurement': {
    'old_gross_carrying': '90.00',
    'old_allowance': '2.00',
    'fresh_cash': '100.00',
    'new_initial_carrying': '195.00',
    'new_initial_allowance': '2.00',
    'old_asset_difference': '5.00',
    'new_asset_difference': '0.00',
    'accounting_asset_continues': true,
  },
  'lines':
      [
            ('renewed_asset', '1100', '195.00', '0.00', 11),
            ('old_loan_component', '1100', '0.00', '80.00', 32),
            ('old_accrued_interest', '1120', '0.00', '10.00', 32),
            ('fresh_cash_transit', '1050', '0.00', '100.00', 11),
            ('old_allowance', '1190', '2.00', '0.00', 32),
            ('continued_allowance', '1190', '0.00', '2.00', 11),
            ('old_asset_difference', '4020', '0.00', '5.00', 32),
          ].indexed
          .map(
            (item) => {
              'line_number': (item.$1 + 1) * 10,
              'component': item.$2.$1,
              'account_code': item.$2.$2,
              'debit': item.$2.$3,
              'credit': item.$2.$4,
              'loan_id': id(item.$2.$5),
              'account_snapshot': {'name': item.$2.$1},
            },
          )
          .toList(),
};

class RenewalFixture extends PayoutFixture {
  bool lost = false, denyRenewal = false, renewalCompletion = false;
  @override
  Map<String, dynamic> source() =>
      renewalCompletion ? renewalCompletionFixture() : super.source();
  Completer<Map<String, dynamic>>? renewalDelayed;
  @override
  Future<Map<String, dynamic>> read(
    UserSession user, {
    required String deviceId,
    required String path,
  }) async {
    if (path.endsWith('/renewal-measurement')) {
      if (denyRenewal) {
        throw const SpinaApiException(
          'Renewal access removed',
          statusCode: 403,
        );
      }
      return renewalDelayed == null
          ? renewalCandidateFixture()
          : await renewalDelayed!.future;
    }
    return super.read(user, deviceId: deviceId, path: path);
  }

  @override
  Future<Map<String, dynamic>> write(
    UserSession user, {
    required String deviceId,
    required String path,
    required Map<String, dynamic> body,
  }) async {
    if (path.endsWith('/renewal-measurement')) {
      writes.add((path, jsonDecode(jsonEncode(body)) as Map<String, dynamic>));
      if (lost) {
        throw const SpinaApiException(
          'Lost response',
          code: 'network_unavailable',
        );
      }
      return {
        'id': id(41),
        'payout_id': id(5),
        'book_id': id(1),
        'source_digest': digest,
        'request_id': body['request_id'],
        'decision': (body['review'] as Map)['decision'],
        'measurement_digest': 'c' * 64,
      };
    }
    return super.write(user, deviceId: deviceId, path: path, body: body);
  }
}

Future<void> loadRenewal(WidgetTester tester) async {
  await tap(tester, 'payout-account');
  await tester.tap(find.text('Source wallet').last);
  await tester.pumpAndSettle();
  await tap(tester, 'payout-stage');
  await tester.tap(find.text('Borrower completion').last);
  await tester.pumpAndSettle();
  await enter(tester, 'payout-reference', id(5));
  await tap(tester, 'payout-renewal-load');
}

void main() {
  testWidgets('ordinary journal permission does not expose renewal treatment', (
    tester,
  ) async {
    final repo = RenewalFixture();
    await pumpPayout(tester, repo);
    expect(find.byKey(const Key('payout-renewal-load')), findsNothing);
    expect(repo.writes, isEmpty);
  });
  test('renewal completion rejects cash and altered loan dimensions', () {
    Map<String, dynamic> validate(Map<String, dynamic> v) =>
        validatePayoutAccounting(
          v,
          bookId: id(1),
          accountId: id(3),
          payoutId: id(5),
          stage: 'completion',
        );
    expect(
      (validate(renewalCompletionFixture())['measurement']
          as Map)['new_initial_carrying'],
      '195.00',
    );
    final cash = renewalCompletionFixture();
    (cash['lines'] as List)[3]['account_code'] = '1030';
    expect(() => validate(cash), throwsFormatException);
    final wrongLoan = renewalCompletionFixture();
    (wrongLoan['lines'] as List)[1]['loan_id'] = id(11);
    expect(() => validate(wrongLoan), throwsFormatException);
    final wrongGain = renewalCompletionFixture();
    (wrongGain['measurement'] as Map)['old_asset_difference'] = '0.00';
    expect(() => validate(wrongGain), throwsFormatException);
    expect(
      () => validate(
        renewalCompletionFixture()..['renewal_decision'] = 'derecognition',
      ),
      throwsFormatException,
    );
  });
  testWidgets(
    'renewal completion separately prepares and posts the retained dimensional journal',
    (tester) async {
      final repo = RenewalFixture()..renewalCompletion = true;
      await pumpPayout(tester, repo, user: renewalSession());
      await lookupPayout(tester, completion: true);
      await tap(tester, 'payout-prepare');
      expect(repo.writes, isEmpty);
      await tap(tester, 'payout-confirm');
      await tap(tester, 'payout-post');
      await tap(tester, 'payout-confirm');
      expect(repo.writes, hasLength(2));
      expect(repo.writes.last.$2['confirm'], isTrue);
    },
  );
  test(
    'renewal values retain exact settlement and explicit dated treatment',
    () {
      Map<String, dynamic> candidate(Map<String, dynamic> v) =>
          validateRenewalCandidate(
            v,
            bookId: id(1),
            accountId: id(3),
            payoutId: id(5),
          );
      final c = candidate(renewalCandidateFixture());
      for (final answer in [null, false, 'true']) {
        final input = renewalInputsFixture();
        (input['qualitative_assessment'] as Map)['signed_contract_reviewed'] =
            answer;
        expect(
          () => validateRenewalReviewInputs(input, c),
          throwsFormatException,
        );
      }
      expect(jsonEncode(c), isNot(contains('SECRET')));
      expect(
        () => candidate(
          renewalCandidateFixture()..['old_gross_carrying'] = '91.00',
        ),
        throwsFormatException,
      );
      expect(
        () => candidate(
          renewalCandidateFixture()..['treasury_account_id'] = id(99),
        ),
        throwsFormatException,
      );
      expect(
        validateRenewalReviewInputs(renewalInputsFixture(), c),
        renewalInputsFixture(),
      );
      for (final patch in [
        {'decision': ''},
        {'settlement_rebate': '0.00'},
        {'qualitative_assessment': <String, dynamic>{}},
        {'new_initial_fair_value': '200.00'},
      ]) {
        expect(
          () => validateRenewalReviewInputs({
            ...renewalInputsFixture(),
            ...patch,
          }, c),
          throwsFormatException,
        );
      }
      final derecognition = {
        ...renewalInputsFixture(),
        'decision': 'derecognition',
        'new_initial_fair_value': '190.00',
        'fair_value_effective_date': '2026-09-30',
        'fair_value_basis':
            'Independent evidence supports this effective-date fair value.',
        'day_one_difference_rationale':
            'The difference from consideration has been explicitly reviewed.',
      };
      expect(
        validateRenewalReviewInputs(derecognition, c)['decision'],
        'derecognition',
      );
      expect(
        () => validateRenewalReviewInputs({
          ...derecognition,
          'fair_value_effective_date': '2026-09-29',
        }, c),
        throwsFormatException,
      );
    },
  );
  testWidgets(
    'renewal retains explicit evidence with unchanged recovery before journal preparation',
    (tester) async {
      final repo = RenewalFixture()..lost = true;
      await pumpPayout(tester, repo, user: renewalSession());
      await loadRenewal(tester);
      expect(find.textContaining('SECRET'), findsNothing);
      await enter(tester, 'renewal-evidence_id', id(40));
      await tap(tester, 'renewal-decision');
      await tester.tap(
        find.text('Modification — accounting asset continues').last,
      );
      await tester.pumpAndSettle();
      final inputs = renewalInputsFixture();
      await enter(
        tester,
        'renewal-accounting_policy_reference',
        inputs['accounting_policy_reference'] as String,
      );
      await tap(tester, 'renewal-signed_contract_reviewed');
      await tap(tester, 'renewal-cash_flow_terms_reviewed');
      await tap(tester, 'renewal-substantial_change_assessed');
      await enter(
        tester,
        'renewal-qualitative_basis',
        (inputs['qualitative_assessment'] as Map)['decision_basis'] as String,
      );
      for (final key in [
        'decision_rationale',
        'settlement_consideration',
        'settlement_rebate',
        'settlement_basis',
      ]) {
        await enter(tester, 'renewal-$key', inputs[key] as String);
      }
      await tap(tester, 'renewal-review');
      expect(repo.writes, isEmpty);
      await tap(tester, 'payout-confirm');
      repo.lost = false;
      await tap(tester, 'payout-retry');
      expect(repo.writes.first.$2, repo.writes.last.$2);
      expect(repo.writes.last.$2['evidence_id'], id(40));
      expect(repo.writes.last.$2['review'], renewalInputsFixture());
      expect(find.byKey(const Key('payout-post')), findsNothing);
      await tester.scrollUntilVisible(
        find.text('Renewal treatment retained'),
        220,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      expect(find.text('Renewal treatment retained'), findsOneWidget);
    },
  );
  testWidgets('renewal denial clears private measurement and commands', (
    tester,
  ) async {
    final repo = RenewalFixture()..denyRenewal = true;
    await pumpPayout(tester, repo, user: renewalSession());
    await loadRenewal(tester);
    expect(find.byKey(const Key('renewal-review')), findsNothing);
    expect(find.byKey(const Key('payout-account')), findsNothing);
    expect(repo.writes, isEmpty);
  });
}
