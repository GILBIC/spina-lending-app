import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/tax_evidence.dart';
import 'package:gilbic_mobile/src/core/management/tax_evidence_repository.dart';
import 'package:gilbic_mobile/src/features/management/management_tax_evidence_page.dart';

void main() {
  testWidgets(
    'shows exact readiness and intersects server/session permission',
    (tester) async {
      final repository = _FakeTaxEvidenceRepository();
      await _pump(tester, repository, session: _dstOnlySession);

      expect(find.byKey(const Key('tax-evidence-summary')), findsOneWidget);
      expect(
        find.text('Percentage evidence permission is not assigned.'),
        findsOneWidget,
      );
      await tester.scrollUntilVisible(
        find.text('Retained DST evidence is required.'),
        500,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('Retained DST evidence is required.'), findsOneWidget);
      expect(find.byKey(const Key('record-tax-rule')), findsNothing);
      expect(find.byKey(Key('record-dst-$_loanId')), findsOneWidget);
      expect(
        find.byKey(Key('record-percentage-$_transactionId')),
        findsNothing,
      );
    },
  );

  testWidgets('records exact percentage allocation through protected review', (
    tester,
  ) async {
    final repository = _FakeTaxEvidenceRepository();
    await _pump(tester, repository, uuidGenerator: () => _retryId);
    final action = find.byKey(Key('record-percentage-$_transactionId'));
    await tester.scrollUntilVisible(
      action,
      600,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    await tester.tap(action);
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byKey(const Key('tax-percentage-taxable')),
      '100.00',
    );
    await tester.enterText(
      find.byKey(const Key('tax-percentage-principal')),
      '400.00',
    );
    await tester.enterText(find.byKey(const Key('tax-percentage-due')), '5.00');
    await tester.enterText(
      find.byKey(const Key('tax-allocation-reference')),
      'Receipt allocation 2001',
    );
    await tester.enterText(
      find.byKey(const Key('tax-allocation-digest')),
      _digest,
    );
    await tester.enterText(
      find.byKey(const Key('tax-evidence-rationale')),
      'Reviewed the exact protected cash allocation and current tax rule.',
    );
    await tester.tap(find.byKey(const Key('review-percentage-tax-evidence')));
    await tester.pumpAndSettle();

    expect(
      find.byKey(const Key('management-review-tax-evidence')),
      findsOneWidget,
    );
    expect(find.text('500.00'), findsAtLeastNWidgets(1));
    await tester.tap(find.byKey(const Key('confirm-tax-evidence')));
    await tester.pumpAndSettle();

    expect(repository.percentageCalls, 1);
    expect(repository.retryIds.single, _retryId);
    expect(repository.lastPercentage?.taxableLendingReceiptAmount, '100.00');
    expect(repository.loadCalls, 2);
  });
}

Future<void> _pump(
  WidgetTester tester,
  _FakeTaxEvidenceRepository repository, {
  UserSession session = _session,
  String Function()? uuidGenerator,
}) async {
  await tester.binding.setSurfaceSize(const Size(390, 844));
  addTearDown(() async => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(
    MaterialApp(
      home: ManagementTaxEvidencePage(
        session: session,
        deviceIdentityProvider: _deviceProvider(),
        repository: repository,
        uuidGenerator: uuidGenerator,
      ),
    ),
  );
  await tester.pumpAndSettle();
}

DeviceIdentityProvider _deviceProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'management-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

class _FakeTaxEvidenceRepository implements TaxEvidenceRepository {
  int loadCalls = 0;
  int percentageCalls = 0;
  final List<String> retryIds = <String>[];
  PercentageTaxEvidenceDraft? lastPercentage;

  @override
  Future<TaxEvidenceOverview> load(
    UserSession session, {
    required String deviceId,
    String readiness = 'all',
    int limit = 100,
    int offset = 0,
  }) async {
    loadCalls += 1;
    return TaxEvidenceOverview.fromPayload(_overview());
  }

  @override
  Future<String> recordPercentage(
    UserSession session, {
    required String deviceId,
    required PercentageTaxReadiness source,
    required PercentageTaxEvidenceDraft draft,
    required String idempotencyKey,
  }) async {
    percentageCalls += 1;
    retryIds.add(idempotencyKey);
    lastPercentage = draft;
    return _percentageEvidenceId;
  }

  @override
  Future<String> recordDst(
    UserSession session, {
    required String deviceId,
    required DstTaxReadiness source,
    required DstEvidenceDraft draft,
    required String idempotencyKey,
  }) async => _dstEvidenceId;

  @override
  Future<String> recordRule(
    UserSession session, {
    required String deviceId,
    required TaxRuleEvidenceDraft draft,
    required String idempotencyKey,
  }) async => _ruleId;
}

Map<String, Object?> _overview() => <String, Object?>{
  'summary': <String, Object>{
    'rule_evidence_count': 2,
    'dst_source_count': 1,
    'dst_ready_count': 0,
    'dst_blocked_count': 1,
    'dst_evidence_tax_total': '0.00',
    'percentage_source_count': 1,
    'percentage_ready_count': 0,
    'percentage_blocked_count': 1,
    'percentage_taxable_receipt_total': '0.00',
    'percentage_evidence_tax_total': '0.00',
    'evidence_backed_tax_readiness_enabled': true,
    'tax_posting_enabled': false,
    'automatic_source_posting': false,
  },
  'rules': <Object?>[
    _rule(_ruleId, 'documentary_stamp_tax'),
    _rule(_percentageRuleId, 'percentage_tax_lending'),
  ],
  'dst': <Object?>[
    <String, Object?>{
      'loan_id': _loanId,
      'client_id': _clientId,
      'disbursement_event_id': _disbursementId,
      'issue_date': '2026-08-30',
      'protected_issue_price': '10000.00',
      'protected_term_days': 90,
      'evidence_id': null,
      'evidence_version': null,
      'rule_evidence_id': null,
      'tax_due': null,
      'calculation_digest': null,
      'tax_status': 'evidence_required',
      'tax_blocker': 'Retained DST evidence is required.',
      'tax_posting_enabled': false,
      'automatic_source_posting': false,
    },
  ],
  'percentage_tax': <Object?>[
    <String, Object?>{
      'transaction_id': _transactionId,
      'loan_id': _loanId,
      'client_id': _clientId,
      'collection_date': '2026-08-30',
      'entry_type': 'payment',
      'source_cash_amount': '500.00',
      'is_voided': false,
      'evidence_id': null,
      'evidence_version': null,
      'rule_evidence_id': null,
      'taxable_lending_receipt_amount': null,
      'principal_receipt_amount': null,
      'tax_due': null,
      'allocation_digest': null,
      'tax_status': 'allocation_evidence_required',
      'tax_blocker': 'Retained allocation evidence is required.',
      'tax_posting_enabled': false,
      'automatic_source_posting': false,
    },
  ],
  'permissions': <String, Object>{
    'rule_evidence_record': true,
    'dst_evidence_record': true,
    'percentage_evidence_record': true,
  },
  'readiness': 'all',
  'limit': 100,
  'offset': 0,
  'evidence_backed_tax_readiness_enabled': true,
  'tax_posting_enabled': false,
  'automatic_source_posting': false,
  'notice': 'Exact retained tax evidence is required.',
};

Map<String, Object?> _rule(String id, String type) => <String, Object?>{
  'id': id,
  'tax_type': type,
  'rule_key': '$type-current',
  'rule_version': 1,
  'effective_from': '2026-08-30',
  'effective_to': null,
  'treatment': 'taxable',
  'rate': type == 'documentary_stamp_tax' ? '0.0075000000' : '0.0500000000',
  'maturity_max_days': type == 'documentary_stamp_tax' ? 365 : null,
  'legal_source': 'Retained legal source',
  'legal_reference': 'Current legal reference',
  'retained_source_reference': 'legal/current.pdf',
  'evidence_digest': _digest,
  'management_rationale': 'Approved current retained legal evidence.',
  'supersedes_rule_id': null,
  'recorded_by_user_id': _actorId,
  'recorded_at': '2026-08-30T01:00:00+00:00',
};

const _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>[
    'accounting.tax.rule_evidence.record',
    'accounting.tax.dst_evidence.record',
    'accounting.tax.percentage_evidence.record',
  ],
);
const _dstOnlySession = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>['accounting.tax.dst_evidence.record'],
);
const _retryId = '11111111-1111-4111-8111-111111111111';
const _ruleId = '22222222-2222-4222-8222-222222222222';
const _percentageRuleId = '22222222-2222-4222-8222-222222222223';
const _dstEvidenceId = '33333333-3333-4333-8333-333333333333';
const _percentageEvidenceId = '33333333-3333-4333-8333-333333333334';
const _loanId = '44444444-4444-4444-8444-444444444444';
const _clientId = '55555555-5555-4555-8555-555555555555';
const _disbursementId = '66666666-6666-4666-8666-666666666666';
const _transactionId = '77777777-7777-4777-8777-777777777777';
const _actorId = '88888888-8888-4888-8888-888888888888';
const _digest =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
