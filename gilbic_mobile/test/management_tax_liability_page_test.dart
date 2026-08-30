import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/tax_liability.dart';
import 'package:gilbic_mobile/src/core/management/tax_liability_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_tax_liability_page.dart';

void main() {
  testWidgets('post review shows exact coordinates and retry reuses token', (
    tester,
  ) async {
    final repository = _FakeTaxLiabilityRepository(failFirstPost: true);
    var generated = 0;
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() async => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        home: ManagementTaxLiabilityPage(
          session: _session,
          deviceIdentityProvider: _deviceProvider(),
          repository: repository,
          confirmationTokenGenerator: () {
            generated += 1;
            return _token;
          },
        ),
      ),
    );
    await tester.pumpAndSettle();
    final post = find.byKey(Key('post-tax-liability-$_evidenceId'));

    await tester.tap(post);
    await tester.pumpAndSettle();
    expect(
      find.byKey(const Key('management-review-tax-liability')),
      findsOneWidget,
    );
    expect(find.text('5310 Documentary Stamp Tax Expense'), findsOneWidget);
    expect(find.text('2100 Tax Payables'), findsOneWidget);
    expect(find.text('2026-08-30'), findsAtLeastNWidgets(1));
    await tester.tap(find.byKey(const Key('confirm-tax-liability')));
    await tester.pumpAndSettle();
    expect(
      find.text('Connection interrupted after submission.'),
      findsOneWidget,
    );

    await tester.tap(post);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('confirm-tax-liability')));
    await tester.pumpAndSettle();

    expect(repository.postCalls, 2);
    expect(repository.tokens.toSet(), hasLength(1));
    expect(generated, 1);
    expect(repository.loadCalls, 2);
    expect(find.text('Posted'), findsOneWidget);
  });
}

DeviceIdentityProvider _deviceProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'management-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

class _FakeTaxLiabilityRepository implements TaxLiabilityRepository {
  _FakeTaxLiabilityRepository({required this.failFirstPost});
  final bool failFirstPost;
  int loadCalls = 0;
  int postCalls = 0;
  final List<String> tokens = <String>[];

  @override
  Future<TaxLiabilityOverview> load(
    UserSession session, {
    required String deviceId,
    String accountingStatus = 'all',
    int limit = 100,
    int offset = 0,
  }) async {
    loadCalls += 1;
    return TaxLiabilityOverview.fromPayload(
      _overview(_item(postCalls >= 2 ? 'posted' : 'prepared_not_posted')),
    );
  }

  @override
  Future<TaxLiabilityItem> post(
    UserSession session, {
    required String deviceId,
    required TaxLiabilityItem item,
    required String confirmationToken,
  }) async {
    postCalls += 1;
    tokens.add(confirmationToken);
    if (failFirstPost && postCalls == 1) {
      throw const SpinaApiException(
        'Connection interrupted after submission.',
        code: 'network_unavailable',
      );
    }
    return TaxLiabilityItem.fromPayload(_item('posted'));
  }

  @override
  Future<TaxLiabilityItem> prepare(
    UserSession session, {
    required String deviceId,
    required TaxLiabilityItem item,
  }) async => TaxLiabilityItem.fromPayload(_item('prepared_not_posted'));
}

Map<String, Object?> _overview(Map<String, Object?> item) => <String, Object?>{
  'summary': <String, Object>{
    'evidence_item_count': 1,
    'ready_to_prepare_count': 0,
    'prepared_count': item['accounting_status'] == 'prepared_not_posted'
        ? 1
        : 0,
    'posted_count': item['accounting_status'] == 'posted' ? 1 : 0,
    'no_liability_required_count': 0,
    'adjusted_posting_count': 0,
    'covered_replacement_count': 0,
    'blocked_or_adjustment_review_count': 0,
    'posted_tax_liability_total': item['accounting_status'] == 'posted'
        ? '75.00'
        : '0.00',
    'protected_tax_liability_posting_enabled': true,
    'tax_settlement_enabled': true,
    'tax_adjustment_reversal_enabled': true,
    'automatic_source_posting': false,
  },
  'items': <Object?>[item],
  'permissions': <String, Object>{
    'liability_prepare': true,
    'liability_post': true,
  },
  'accounting_status': 'all',
  'limit': 100,
  'offset': 0,
  'protected_tax_liability_posting_enabled': true,
  'tax_settlement_enabled': true,
  'tax_adjustment_reversal_enabled': true,
  'automatic_source_posting': false,
  'notice': 'Exact protected tax liability evidence is required.',
};

Map<String, Object?> _item(String status) {
  final prepared = status == 'prepared_not_posted' || status == 'posted';
  final posted = status == 'posted';
  return <String, Object?>{
    'tax_type': 'documentary_stamp_tax',
    'evidence_id': _evidenceId,
    'evidence_version': 1,
    'source_id': _sourceId,
    'loan_id': _loanId,
    'client_id': _clientId,
    'recognition_date': '2026-08-30',
    'tax_due': '75.00',
    'evidence_digest': _digest,
    'evidence_status': 'evidence_ready',
    'evidence_blocker': null,
    'expense_account_code': '5310',
    'expense_account_name': 'Documentary Stamp Tax Expense',
    'tax_payable_account_code': '2100',
    'tax_payable_account_name': 'Tax Payables',
    'preparation_id': prepared ? _preparationId : null,
    'journal_entry_id': prepared ? _journalId : null,
    'journal_status': prepared ? (posted ? 'posted' : 'draft') : null,
    'entry_number': posted ? 'GJ-2026-0020' : null,
    'fiscal_period_id': prepared ? _periodId : null,
    'prepared_by_user_id': prepared ? _actorId : null,
    'prepared_at': prepared ? '2026-08-30T02:00:00+00:00' : null,
    'posting_id': posted ? _postingId : null,
    'confirmation_digest': posted ? _confirmationDigest : null,
    'posted_by_user_id': posted ? _actorId : null,
    'posted_at': posted ? '2026-08-30T02:10:00+00:00' : null,
    'accounting_status': status,
    'accounting_blocker': null,
    'protected_tax_liability_posting_enabled': true,
    'tax_settlement_enabled': true,
    'tax_adjustment_reversal_enabled': true,
    'automatic_source_posting': false,
  };
}

const _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>[
    'accounting.tax.liability.prepare',
    'accounting.tax.liability.post',
  ],
);
const _evidenceId = '22222222-2222-4222-8222-222222222222';
const _sourceId = '33333333-3333-4333-8333-333333333333';
const _loanId = '44444444-4444-4444-8444-444444444444';
const _clientId = '55555555-5555-4555-8555-555555555555';
const _preparationId = '66666666-6666-4666-8666-666666666666';
const _journalId = '77777777-7777-4777-8777-777777777777';
const _periodId = '88888888-8888-4888-8888-888888888888';
const _postingId = '99999999-9999-4999-8999-999999999999';
const _actorId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const _digest =
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
const _confirmationDigest =
    'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc';
const _token =
    'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd';
