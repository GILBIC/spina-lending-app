import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/tax_adjustment.dart';
import 'package:gilbic_mobile/src/core/management/tax_adjustment_repository.dart';
import 'package:gilbic_mobile/src/core/management/tax_settlement.dart';
import 'package:gilbic_mobile/src/core/management/tax_settlement_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_tax_adjustment_page.dart';
import 'package:gilbic_mobile/src/features/management/management_tax_settlement_page.dart';

void main() {
  testWidgets(
    'return review uses selected server candidate and derived total',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(390, 844));
      addTearDown(() async => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        MaterialApp(
          home: ManagementTaxSettlementPage(
            session: _settlementSession,
            deviceIdentityProvider: _deviceProvider(),
            repository: _FakeSettlementRepository(),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(Key('return-candidate-$_postingId')));
      await tester.pump();
      expect(find.text('Record return • 75.00'), findsOneWidget);
      await tester.tap(find.byKey(const Key('record-tax-return')));
      await tester.pumpAndSettle();
      final fields = find.byType(TextField);
      const values = <String>[
        '2026-08-01',
        '2026-08-31',
        '2026-09-01',
        'BIR-RETURN-100',
        'retained://returns/100',
        _digest,
        'Retained exact return evidence for the selected liabilities.',
      ];
      for (var index = 0; index < values.length; index += 1) {
        await tester.enterText(fields.at(index), values[index]);
      }
      await tester.tap(find.text('Review'));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('management-review-tax-settlement')),
        findsOneWidget,
      );
      expect(find.text('75.00'), findsAtLeastNWidgets(1));
      expect(find.text('GJ-2026-0020'), findsOneWidget);
    },
  );

  testWidgets('correction review displays server-derived kind and amount', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() async => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        home: ManagementTaxAdjustmentPage(
          session: _adjustmentSession,
          deviceIdentityProvider: _deviceProvider(),
          repository: _FakeAdjustmentRepository(),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Record'));
    await tester.pumpAndSettle();
    final fields = find.byType(TextField);
    const values = <String>[
      '2026-08-30',
      'ADJ-100',
      'retained://adjustments/100',
      _digest,
      'Retained exact evidence for the protected correction pair.',
    ];
    for (var index = 0; index < values.length; index += 1) {
      await tester.enterText(fields.at(index), values[index]);
    }
    await tester.tap(find.text('Review'));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const Key('management-review-tax-adjustment')),
      findsOneWidget,
    );
    expect(
      find.text('Recognize settled Tax Recoverable'),
      findsAtLeastNWidgets(1),
    );
    expect(find.text('25.00'), findsAtLeastNWidgets(1));
  });

  testWidgets(
    'uncertain settlement write blocks retry until authoritative refresh',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(390, 844));
      addTearDown(() async => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        MaterialApp(
          home: ManagementTaxSettlementPage(
            session: _settlementSession,
            deviceIdentityProvider: _deviceProvider(),
            repository: _NetworkSettlementRepository(),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(Key('return-candidate-$_postingId')));
      await tester.pump();
      await tester.tap(find.byKey(const Key('record-tax-return')));
      await tester.pumpAndSettle();
      final fields = find.byType(TextField);
      const values = <String>[
        '2026-08-01',
        '2026-08-31',
        '2026-09-01',
        'BIR-RETURN-100',
        'retained://returns/100',
        _digest,
        'Retained exact return evidence for the selected liabilities.',
      ];
      for (var index = 0; index < values.length; index += 1) {
        await tester.enterText(fields.at(index), values[index]);
      }
      await tester.tap(find.text('Review'));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-tax-settlement')));
      await tester.pumpAndSettle();

      expect(find.textContaining('result is uncertain'), findsOneWidget);
      expect(
        tester
            .widget<FilledButton>(find.byKey(const Key('record-tax-return')))
            .onPressed,
        isNull,
      );

      await tester.tap(find.byTooltip('Refresh settlements'));
      await tester.pumpAndSettle();
      expect(
        tester
            .widget<FilledButton>(find.byKey(const Key('record-tax-return')))
            .onPressed,
        isNotNull,
      );
    },
  );

  testWidgets(
    'uncertain correction write blocks retry until authoritative refresh',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(390, 844));
      addTearDown(() async => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        MaterialApp(
          home: ManagementTaxAdjustmentPage(
            session: _adjustmentSession,
            deviceIdentityProvider: _deviceProvider(),
            repository: _NetworkAdjustmentRepository(),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Record'));
      await tester.pumpAndSettle();
      final fields = find.byType(TextField);
      const values = <String>[
        '2026-08-30',
        'ADJ-100',
        'retained://adjustments/100',
        _digest,
        'Retained exact evidence for the protected correction pair.',
      ];
      for (var index = 0; index < values.length; index += 1) {
        await tester.enterText(fields.at(index), values[index]);
      }
      await tester.tap(find.text('Review'));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-tax-adjustment')));
      await tester.pumpAndSettle();

      expect(find.textContaining('result is uncertain'), findsOneWidget);
      expect(
        tester
            .widget<FilledButton>(find.widgetWithText(FilledButton, 'Record'))
            .onPressed,
        isNull,
      );

      await tester.tap(find.byTooltip('Refresh corrections'));
      await tester.pumpAndSettle();
      expect(
        tester
            .widget<FilledButton>(find.widgetWithText(FilledButton, 'Record'))
            .onPressed,
        isNotNull,
      );
    },
  );
}

DeviceIdentityProvider _deviceProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'management-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

class _FakeSettlementRepository implements TaxSettlementRepository {
  @override
  Future<TaxSettlementOverview> load(
    UserSession session, {
    required String deviceId,
    String settlementStatus = 'all',
    int limit = 100,
    int offset = 0,
  }) async => const TaxSettlementOverview(
    summary: TaxSettlementSummary(
      returnCount: 0,
      awaitingPaymentEvidenceCount: 0,
      readyToPrepareCount: 0,
      preparedCount: 0,
      settledCount: 0,
      settledAdjustmentReviewCount: 0,
      settledAdjustmentInProgressCount: 0,
      settledAdjustmentRecordedCount: 0,
      blockedCount: 0,
      settledTaxTotal: '0.00',
    ),
    items: <TaxSettlementItem>[],
    returnLiabilityCandidates: <TaxReturnLiabilityCandidate>[
      TaxReturnLiabilityCandidate(
        taxType: 'documentary_stamp_tax',
        postingId: _postingId,
        evidenceId: _evidenceId,
        evidenceVersion: 1,
        sourceId: _sourceId,
        loanId: _loanId,
        clientId: _clientId,
        recognitionDate: '2026-08-30',
        taxDue: '75.00',
        evidenceDigest: _digest,
        entryNumber: 'GJ-2026-0020',
        fiscalPeriodId: _periodId,
      ),
    ],
    permissions: TaxSettlementPermissions(
      returnEvidenceRecord: true,
      paymentEvidenceRecord: true,
      settlementPrepare: true,
      settlementPost: true,
    ),
    settlementStatus: 'all',
    limit: 100,
    offset: 0,
    notice: 'Exact retained evidence is required.',
  );

  @override
  Future<TaxSettlementItem> post(
    UserSession session, {
    required String deviceId,
    required TaxSettlementItem item,
    required String confirmationToken,
  }) => throw UnimplementedError();
  @override
  Future<TaxSettlementItem> prepare(
    UserSession session, {
    required String deviceId,
    required TaxSettlementItem item,
  }) => throw UnimplementedError();
  @override
  Future<TaxSettlementItem> recordPayment(
    UserSession session, {
    required String deviceId,
    required TaxSettlementItem item,
    required String idempotencyKey,
    required String paymentDate,
    required String cashAccountSystemKey,
    required String paymentReference,
    required String evidenceReference,
    required String evidenceDigest,
    required String evidenceNote,
  }) => throw UnimplementedError();
  @override
  Future<TaxSettlementItem> recordReturn(
    UserSession session, {
    required String deviceId,
    required List<TaxReturnLiabilityCandidate> candidates,
    required String idempotencyKey,
    required String returnPeriodStart,
    required String returnPeriodEnd,
    required String filingDate,
    required String returnReference,
    required String evidenceReference,
    required String evidenceDigest,
    required String evidenceNote,
  }) => throw UnimplementedError();
}

class _FakeAdjustmentRepository implements TaxAdjustmentRepository {
  @override
  Future<TaxAdjustmentOverview> load(
    UserSession session, {
    required String deviceId,
    String adjustmentStatus = 'all',
    int limit = 100,
    int offset = 0,
  }) async => const TaxAdjustmentOverview(
    summary: TaxAdjustmentSummary(
      adjustmentEvidenceCount: 0,
      readyToPrepareCount: 0,
      preparedCount: 0,
      postedReversalCount: 0,
      postedRecoverableCount: 0,
      furtherReviewCount: 0,
      blockedCount: 0,
      postedAdjustmentTotal: '0.00',
    ),
    items: <TaxAdjustmentItem>[],
    adjustmentCandidates: <TaxAdjustmentCandidate>[
      TaxAdjustmentCandidate(
        adjustmentKind: 'recognize_settled_tax_recoverable',
        taxType: 'documentary_stamp_tax',
        taxLiabilityPostingId: _postingId,
        originalEvidenceId: _evidenceId,
        originalEvidenceVersion: 1,
        replacementEvidenceId: _replacementEvidenceId,
        replacementEvidenceVersion: 2,
        sourceId: _sourceId,
        loanId: _loanId,
        clientId: _clientId,
        originalTaxDue: '75.00',
        replacementTaxDue: '50.00',
        adjustmentAmount: '25.00',
        originalEvidenceDigest: _digest,
        replacementEvidenceDigest: _replacementDigest,
        fiscalPeriodId: _periodId,
        fiscalPeriodStart: '2026-08-01',
        fiscalPeriodEnd: '2026-08-31',
        settlementPostingId: _settlementPostingId,
      ),
    ],
    permissions: TaxAdjustmentPermissions(
      adjustmentEvidenceRecord: true,
      adjustmentPrepare: true,
      adjustmentPost: true,
    ),
    adjustmentStatus: 'all',
    limit: 100,
    offset: 0,
    notice: 'Posted history is immutable.',
  );

  @override
  Future<TaxAdjustmentItem> post(
    UserSession session, {
    required String deviceId,
    required TaxAdjustmentItem item,
    required String confirmationToken,
  }) => throw UnimplementedError();
  @override
  Future<TaxAdjustmentItem> prepare(
    UserSession session, {
    required String deviceId,
    required TaxAdjustmentItem item,
  }) => throw UnimplementedError();
  @override
  Future<TaxAdjustmentItem> recordEvidence(
    UserSession session, {
    required String deviceId,
    required TaxAdjustmentCandidate candidate,
    required String idempotencyKey,
    required String adjustmentDate,
    required String adjustmentReference,
    required String evidenceReference,
    required String evidenceDigest,
    required String evidenceNote,
  }) => throw UnimplementedError();
}

class _NetworkSettlementRepository extends _FakeSettlementRepository {
  @override
  Future<TaxSettlementItem> recordReturn(
    UserSession session, {
    required String deviceId,
    required List<TaxReturnLiabilityCandidate> candidates,
    required String idempotencyKey,
    required String returnPeriodStart,
    required String returnPeriodEnd,
    required String filingDate,
    required String returnReference,
    required String evidenceReference,
    required String evidenceDigest,
    required String evidenceNote,
  }) => throw const SpinaApiException(
    'The protected tax-settlement server could not be reached.',
    code: 'network_unavailable',
  );
}

class _NetworkAdjustmentRepository extends _FakeAdjustmentRepository {
  @override
  Future<TaxAdjustmentItem> recordEvidence(
    UserSession session, {
    required String deviceId,
    required TaxAdjustmentCandidate candidate,
    required String idempotencyKey,
    required String adjustmentDate,
    required String adjustmentReference,
    required String evidenceReference,
    required String evidenceDigest,
    required String evidenceNote,
  }) => throw const SpinaApiException(
    'The protected tax-adjustment server could not be reached.',
    code: 'network_unavailable',
  );
}

const _settlementSession = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'token',
  permissions: <String>['accounting.tax.return_evidence.record'],
);
const _adjustmentSession = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'token',
  permissions: <String>['accounting.tax.adjustment_evidence.record'],
);
const _postingId = '11111111-1111-4111-8111-111111111111';
const _evidenceId = '22222222-2222-4222-8222-222222222222';
const _replacementEvidenceId = '33333333-3333-4333-8333-333333333333';
const _sourceId = '44444444-4444-4444-8444-444444444444';
const _loanId = '55555555-5555-4555-8555-555555555555';
const _clientId = '66666666-6666-4666-8666-666666666666';
const _periodId = '77777777-7777-4777-8777-777777777777';
const _settlementPostingId = '88888888-8888-4888-8888-888888888888';
const _digest =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const _replacementDigest =
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
