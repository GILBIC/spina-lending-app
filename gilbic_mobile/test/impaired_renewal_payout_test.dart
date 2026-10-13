import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/payout_accounting_evidence.dart';
import 'management_payout_accounting_page_test.dart' show pumpPayout;
import 'management_protected_accounting_page_test.dart' show id, tap;
import 'renewal_payout_accounting_test.dart'
    show
        RenewalFixture,
        renewalCandidateFixture,
        renewalInputsFixture,
        renewalCompletionFixture,
        renewalSession,
        loadRenewal;

Map<String, dynamic> impairedCandidate() => {
  ...renewalCandidateFixture(),
  'predecessor_credit_impaired': true,
  'derecognition_blocker': 'successor_credit_adjusted_eir_policy_required',
  'credit_impaired_boundary': {
    'allowance_before': '2.00',
    'allowance_unwind': '0.00',
    'impairment_adjustment': '0.00',
    'allowance_after': '2.00',
  },
};

// Illustrative arithmetic; actual PostgreSQL lifecycle DTOs are tested separately.
Map<String, dynamic> impairedCompletion() {
  final value = renewalCompletionFixture();
  value['predecessor_credit_impaired'] = true;
  value['credit_impaired_boundary'] = {
    'allowance_before': '2.00',
    'allowance_unwind': '0.50',
    'impairment_adjustment': '-1.00',
    'allowance_after': '1.50',
  };
  (value['measurement'] as Map)['old_allowance'] = '1.50';
  (value['measurement'] as Map)['new_initial_allowance'] = '1.50';
  final lines = List<dynamic>.from(value['lines'] as List);
  value['lines'] = lines;
  lines[4]['debit'] = lines[5]['credit'] = '1.50';
  lines.addAll(
    [
      ('old_asset_allowance_unwind', '4000', '0.50', '0.00'),
      ('old_asset_allowance_unwind', '1190', '0.00', '0.50'),
      ('old_asset_impaired_adjustment', '1190', '1.00', '0.00'),
      ('old_asset_impaired_adjustment', '5000', '0.00', '1.00'),
    ].indexed.map(
      (item) => {
        'line_number': 80 + item.$1,
        'component': item.$2.$1,
        'account_code': item.$2.$2,
        'debit': item.$2.$3,
        'credit': item.$2.$4,
        'loan_id': id(32),
        'account_snapshot': {'name': item.$2.$1},
      },
    ),
  );
  return value;
}

class ImpairedRenewalFixture extends RenewalFixture {
  @override
  Future<Map<String, dynamic>> read(
    UserSession user, {
    required String deviceId,
    required String path,
  }) async => path.endsWith('/renewal-measurement')
      ? {
          ...impairedCandidate(),
          'credit_impaired_boundary': {
            'allowance_before': '2.01',
            'allowance_unwind': '-0.01',
            'impairment_adjustment': '0.00',
            'allowance_after': '2.00',
          },
        }
      : super.read(user, deviceId: deviceId, path: path);
}

void main() {
  test(
    'negative renewal reconciliation reverses only its exact old-asset journal pair',
    () {
      Map<String, dynamic> fixture() {
        final v = impairedCompletion();
        v['credit_impaired_boundary'] = Map<String, dynamic>.from(
          v['credit_impaired_boundary'] as Map,
        );
        v['credit_impaired_boundary']['allowance_unwind'] = '-0.01';
        v['credit_impaired_boundary']['impairment_adjustment'] = '-0.49';
        v['lines'][7]['debit'] = v['lines'][8]['credit'] = '0.00';
        v['lines'][7]['credit'] = v['lines'][8]['debit'] = '0.01';
        v['lines'][9]['debit'] = v['lines'][10]['credit'] = '0.49';
        return v;
      }

      Map<String, dynamic> validate(Map<String, dynamic> v) =>
          validatePayoutAccounting(
            v,
            bookId: id(1),
            accountId: id(3),
            payoutId: id(5),
            stage: 'completion',
          );
      expect(
        validate(fixture())['credit_impaired_boundary']['allowance_unwind'],
        '-0.01',
      );
      for (final mutate in <void Function(Map<String, dynamic>)>[
        (v) => v['credit_impaired_boundary']['allowance_unwind'] = '-0.02',
        (v) => v['credit_impaired_boundary']['allowance_unwind'] = -0.01,
        (v) => v['credit_impaired_boundary']['allowance_unwind'] =
            '-10000000000000000.00',
        (v) => v['credit_impaired_boundary']['allowance_after'] = '-0.01',
        (v) {
          v['lines'][7]['debit'] = v['lines'][8]['credit'] = '0.01';
          v['lines'][7]['credit'] = v['lines'][8]['debit'] = '0.00';
        },
        (v) => v['lines'][7]['loan_id'] = id(11),
        (v) => (v['lines'] as List).removeAt(7),
      ]) {
        final v = fixture();
        mutate(v);
        expect(() => validate(v), throwsFormatException);
      }
      final candidate = impairedCandidate();
      candidate['credit_impaired_boundary'] = <String, dynamic>{
        ...candidate['credit_impaired_boundary'] as Map,
        'allowance_before': '2.01',
        'allowance_unwind': '-0.01',
      };
      expect(
        validateRenewalCandidate(
          candidate,
          bookId: id(1),
          accountId: id(3),
          payoutId: id(5),
        )['credit_impaired_boundary']['allowance_unwind'],
        '-0.01',
      );
    },
  );
  test(
    'impaired candidate retains the boundary and blocks unsupported derecognition',
    () {
      Map<String, dynamic> validate(Map<String, dynamic> v) =>
          validateRenewalCandidate(
            v,
            bookId: id(1),
            accountId: id(3),
            payoutId: id(5),
          );
      final candidate = validate(impairedCandidate());
      expect(candidate['predecessor_credit_impaired'], isTrue);
      expect(
        (candidate['credit_impaired_boundary'] as Map)['allowance_after'],
        '2.00',
      );
      expect(
        validateRenewalReviewInputs(
          renewalInputsFixture(),
          candidate,
        )['decision'],
        'modification_no_derecognition',
      );
      expect(
        () => validateRenewalReviewInputs({
          ...renewalInputsFixture(),
          'decision': 'derecognition',
          'new_initial_fair_value': '190.00',
          'fair_value_effective_date': '2026-09-30',
          'fair_value_basis': 'Supported effective-date fair value evidence.',
          'day_one_difference_rationale':
              'Explicit reviewed initial difference rationale.',
        }, candidate),
        throwsFormatException,
      );
      for (final patch in [
        {'predecessor_credit_impaired': 'true'},
        {'predecessor_credit_impaired': false},
        {'derecognition_blocker': null},
        {'derecognition_blocker': 'unknown_policy'},
        {'credit_impaired_boundary': null},
        {'old_allowance': '2.01'},
      ]) {
        expect(
          () => validate({...impairedCandidate(), ...patch}),
          throwsFormatException,
        );
      }
    },
  );

  test(
    'impaired completion verifies signed adjustment and exact paired journal roles',
    () {
      Map<String, dynamic> validate(Map<String, dynamic> v) =>
          validatePayoutAccounting(
            v,
            bookId: id(1),
            accountId: id(3),
            payoutId: id(5),
            stage: 'completion',
          );
      final result = validate(impairedCompletion());
      expect(
        (result['credit_impaired_boundary'] as Map)['allowance_after'],
        '1.50',
      );
      expect(result['lines'], hasLength(11));
      for (final mutate in <void Function(Map<String, dynamic>)>[
        (v) =>
            (v['credit_impaired_boundary'] as Map)['allowance_after'] = '2.00',
        (v) => (v['credit_impaired_boundary'] as Map)['impairment_adjustment'] =
            '1.00',
        (v) => (v['lines'] as List)[7]['loan_id'] = id(11),
        (v) => (v['lines'] as List)[9]['account_code'] = '5000',
        (v) => (v['lines'] as List).add({
          ...v['lines'][7] as Map,
          'line_number': 99,
        }),
        (v) => v.remove('credit_impaired_boundary'),
        (v) => v['predecessor_credit_impaired'] = false,
        (v) => v['renewal_decision'] = 'derecognition',
      ]) {
        final changed = impairedCompletion();
        mutate(changed);
        expect(() => validate(changed), throwsFormatException);
      }
      final positive = impairedCompletion();
      positive['credit_impaired_boundary']['impairment_adjustment'] = '1.00';
      positive['credit_impaired_boundary']['allowance_after'] = '3.50';
      positive['measurement']['old_allowance'] = '3.50';
      positive['measurement']['new_initial_allowance'] = '3.50';
      final lines = positive['lines'] as List;
      lines[4]['debit'] = lines[5]['credit'] = '3.50';
      lines[9]['debit'] = lines[10]['credit'] = '0.00';
      lines[9]['credit'] = lines[10]['debit'] = '1.00';
      expect(
        (validate(positive)['credit_impaired_boundary']
            as Map)['allowance_after'],
        '3.50',
      );
    },
  );

  testWidgets(
    'impaired treatment shows retained basis and leaves treatment unselected',
    (tester) async {
      final repo = ImpairedRenewalFixture();
      await pumpPayout(tester, repo, user: renewalSession());
      await loadRenewal(tester);
      await tester.scrollUntilVisible(
        find.textContaining('Derecognition unavailable:'),
        250,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.textContaining('credit-adjusted EIR policy'), findsOneWidget);
      expect(
        find.textContaining('Allowance before impaired boundary: PHP 2.01'),
        findsOneWidget,
      );
      expect(
        find.textContaining('Gross/net allowance reconciliation: PHP -0.01'),
        findsOneWidget,
      );
      await tap(tester, 'renewal-decision');
      final dropdown = tester.widget<DropdownButtonFormField<String>>(
        find.byKey(const Key('renewal-decision')),
      );
      expect(dropdown.initialValue, isNull);
      final option = tester.widget<DropdownMenuItem<String>>(
        find
            .ancestor(
              of: find.text('Derecognition — new accounting asset').last,
              matching: find.byType(DropdownMenuItem<String>),
            )
            .last,
      );
      expect(option.enabled, isFalse);
      expect(repo.writes, isEmpty);
    },
  );
}
