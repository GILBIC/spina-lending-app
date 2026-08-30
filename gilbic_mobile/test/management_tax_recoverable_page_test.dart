import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/tax_recoverable.dart';
import 'package:gilbic_mobile/src/core/management/tax_recoverable_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_tax_recoverable_page.dart';

void main() {
  testWidgets('Tax Recoverable separates exact refund and credit workflows', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() async => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        home: ManagementTaxRecoverablePage(
          session: _session,
          deviceIdentityProvider: _deviceProvider(),
          repository: _Repository(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Tax Recoverable'), findsOneWidget);
    expect(find.byKey(const Key('recoverable-refund-summary')), findsOneWidget);
    expect(find.text('Cash refund'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.byKey(const Key('recoverable-credit-summary')),
      250,
    );
    expect(find.text('Tax credit'), findsOneWidget);
    expect(find.byKey(const Key('recoverable-credit-summary')), findsOneWidget);
    expect(
      find.text('No exact cash-refund candidates are eligible.'),
      findsOneWidget,
    );
    expect(
      find.text('No exact tax-credit candidates are eligible.'),
      findsOneWidget,
    );
  });

  testWidgets(
    'uncertain refund evidence locks all writes until authoritative refresh',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(390, 844));
      addTearDown(() async => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        MaterialApp(
          home: ManagementTaxRecoverablePage(
            session: _refundSession,
            deviceIdentityProvider: _deviceProvider(),
            repository: _NetworkRepository(),
            idempotencyKeyGenerator: () => _idempotency,
          ),
        ),
      );
      await tester.pumpAndSettle();

      final candidate = find.byKey(
        const Key('refund-candidate-11111111-1111-4111-8111-111111111111'),
      );
      FilledButton button() => tester.widget<FilledButton>(
        find.descendant(of: candidate, matching: find.byType(FilledButton)),
      );
      expect(button().onPressed, isNotNull);
      await tester.tap(
        find.descendant(of: candidate, matching: find.text('Record')),
      );
      await tester.pumpAndSettle();
      final fields = find.byType(TextField);
      const values = <String>[
        '2026-08-30',
        'BIR-REFUND-1',
        'BIR retained refund authority',
        _digest,
        'Retained exact refund authority and receipt evidence for review.',
      ];
      for (var index = 0; index < values.length; index += 1) {
        await tester.enterText(fields.at(index), values[index]);
      }
      await tester.tap(find.text('Review'));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-tax-recoverable')));
      await tester.pumpAndSettle();

      expect(
        find.textContaining('result is uncertain'),
        findsAtLeastNWidgets(1),
      );
      expect(button().onPressed, isNull);
      await tester.tap(find.byTooltip('Refresh Tax Recoverable'));
      await tester.pumpAndSettle();
      expect(button().onPressed, isNotNull);
    },
  );
}

class _Repository extends Fake implements TaxRecoverableRepository {
  @override
  Future<TaxRecoverableWorkspace> load(
    UserSession session, {
    required String deviceId,
    String refundStatus = 'all',
    String creditStatus = 'all',
    int limit = 100,
    int offset = 0,
  }) async => _emptyWorkspace;
}

class _NetworkRepository extends Fake implements TaxRecoverableRepository {
  @override
  Future<TaxRecoverableWorkspace> load(
    UserSession session, {
    required String deviceId,
    String refundStatus = 'all',
    String creditStatus = 'all',
    int limit = 100,
    int offset = 0,
  }) async => _candidateWorkspace;

  @override
  Future<TaxRecoverableRefundItem> recordRefundEvidence(
    UserSession session, {
    required String deviceId,
    required TaxRecoverableRefundCandidate candidate,
    required String idempotencyKey,
    required String refundDate,
    required String cashAccountCode,
    required String refundReference,
    required String authorityReference,
    required String evidenceDigest,
    required String evidenceNote,
  }) => throw const SpinaApiException(
    'Network result is uncertain.',
    code: 'network_unavailable',
  );
}

const _emptyWorkspace = TaxRecoverableWorkspace(
  refunds: TaxRecoverableRefundOverview(
    summary: TaxRecoverableSummary(
      evidenceCount: 0,
      readyCount: 0,
      preparedCount: 0,
      completedCount: 0,
      blockedCount: 0,
      completedTotal: '0.00',
    ),
    items: <TaxRecoverableRefundItem>[],
    candidates: <TaxRecoverableRefundCandidate>[],
    permissions: TaxRecoverableRefundPermissions(
      evidenceRecord: false,
      prepare: false,
      post: false,
    ),
    status: 'all',
    limit: 100,
    offset: 0,
    notice: 'Exact cash refund only.',
  ),
  credits: TaxRecoverableCreditOverview(
    summary: TaxRecoverableSummary(
      evidenceCount: 0,
      readyCount: 0,
      preparedCount: 0,
      completedCount: 0,
      blockedCount: 0,
      completedTotal: '0.00',
    ),
    items: <TaxRecoverableCreditItem>[],
    candidates: <TaxRecoverableCreditCandidate>[],
    permissions: TaxRecoverableCreditPermissions(
      evidenceRecord: false,
      prepare: false,
      post: false,
    ),
    status: 'all',
    limit: 100,
    offset: 0,
    notice: 'Exact same-tax-type credit only.',
  ),
);

const _candidateWorkspace = TaxRecoverableWorkspace(
  refunds: TaxRecoverableRefundOverview(
    summary: TaxRecoverableSummary(
      evidenceCount: 0,
      readyCount: 0,
      preparedCount: 0,
      completedCount: 0,
      blockedCount: 0,
      completedTotal: '0.00',
    ),
    items: <TaxRecoverableRefundItem>[],
    candidates: <TaxRecoverableRefundCandidate>[
      TaxRecoverableRefundCandidate(
        adjustmentPostingId: '11111111-1111-4111-8111-111111111111',
        adjustmentEvidenceId: '22222222-2222-4222-8222-222222222222',
        taxType: 'documentary_stamp_tax',
        sourceId: '33333333-3333-4333-8333-333333333333',
        loanId: '44444444-4444-4444-8444-444444444444',
        clientId: '55555555-5555-4555-8555-555555555555',
        recoverableAmount: '75.00',
        minimumRefundDate: '2026-08-20',
        adjustmentEvidenceDigest: _digest,
        entryNumber: 'GJ-2026-50',
        fiscalPeriodId: '66666666-6666-4666-8666-666666666666',
      ),
    ],
    permissions: TaxRecoverableRefundPermissions(
      evidenceRecord: true,
      prepare: true,
      post: true,
    ),
    status: 'all',
    limit: 100,
    offset: 0,
    notice: 'Exact cash refund only.',
  ),
  credits: TaxRecoverableCreditOverview(
    summary: TaxRecoverableSummary(
      evidenceCount: 0,
      readyCount: 0,
      preparedCount: 0,
      completedCount: 0,
      blockedCount: 0,
      completedTotal: '0.00',
    ),
    items: <TaxRecoverableCreditItem>[],
    candidates: <TaxRecoverableCreditCandidate>[],
    permissions: TaxRecoverableCreditPermissions(
      evidenceRecord: true,
      prepare: true,
      post: true,
    ),
    status: 'all',
    limit: 100,
    offset: 0,
    notice: 'Exact same-tax-type credit only.',
  ),
);

DeviceIdentityProvider _deviceProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'management-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

const _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>[],
);
const _refundSession = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>['accounting.tax.recoverable_refund_evidence.record'],
);
const _idempotency = '77777777-7777-4777-8777-777777777777';
const _digest =
    '1111111111111111111111111111111111111111111111111111111111111111';
