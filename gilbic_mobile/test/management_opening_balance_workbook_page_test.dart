import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/opening_balance_workbook.dart';
import 'package:gilbic_mobile/src/core/management/opening_balance_workbook_repository.dart';
import 'package:gilbic_mobile/src/features/management/management_opening_balance_workbook_page.dart';

void main() {
  testWidgets('Management sees non-posting opening workbook source state', (
    tester,
  ) async {
    final repository = _FakeWorkbookRepository(initialized: false);

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementOpeningBalanceWorkbookPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Opening Balance Workbook'), findsOneWidget);
    expect(find.text('Workbook not initialized'), findsOneWidget);
    expect(find.textContaining('does not post'), findsWidgets);
    expect(
      find.byKey(const Key('initialize-opening-balance-workbook')),
      findsOneWidget,
    );
    expect(find.text('Cash - Collector Custody'), findsOneWidget);
    expect(find.text('₱200.00'), findsOneWidget);
    expect(repository.deviceId, 'management-device');

    await tester.tap(
      find.byKey(const Key('initialize-opening-balance-workbook')),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('OK'));
    await tester.pumpAndSettle();

    expect(
      find.byKey(const Key('management-review-opening-workbook')),
      findsOneWidget,
    );
    expect(
      find.text(
        'The workbook will snapshot approved source references for the selected '
        'cutover date. It will not create or post a journal.',
      ),
      findsOneWidget,
    );
    expect(repository.createdCutoverDate, isNull);

    await tester.tap(find.byKey(const Key('cancel-opening-workbook')));
    await tester.pumpAndSettle();
    expect(repository.createdCutoverDate, isNull);

    await tester.tap(
      find.byKey(const Key('initialize-opening-balance-workbook')),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('OK'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('confirm-opening-workbook')));
    await tester.pumpAndSettle();

    expect(repository.createdCutoverDate, isNotNull);
  });

  testWidgets('Initialized workbook shows protected review gates', (
    tester,
  ) async {
    final repository = _FakeWorkbookRepository(initialized: true);

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementOpeningBalanceWorkbookPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('opening-workbook-summary')), findsOneWidget);
    expect(find.text('2026-08-08'), findsOneWidget);
    expect(find.text('0 / 11'), findsOneWidget);
    expect(find.text('Ready to post'), findsOneWidget);
    expect(find.text('No'), findsWidgets);
    expect(find.byKey(const Key('opening-workbook-policy')), findsOneWidget);

    await tester.scrollUntilVisible(find.text('Cash - Collector Custody'), 250);
    expect(find.byKey(const Key('opening-workbook-line-1020')), findsOneWidget);
    expect(
      find.byKey(const Key('edit-opening-workbook-line-1020')),
      findsOneWidget,
    );

    await tester.scrollUntilVisible(find.text('Review gate'), 250);
    expect(
      find.byKey(const Key('opening-workbook-mark-review-ready')),
      findsOneWidget,
    );
    expect(
      tester
          .widget<FilledButton>(
            find.byKey(const Key('opening-workbook-mark-review-ready')),
          )
          .onPressed,
      isNull,
    );
    expect(
      find.textContaining('Opening journal posting: Disabled'),
      findsOneWidget,
    );
  });

  testWidgets(
    'Workbook line policy and workflow saves are separately reviewed',
    (tester) async {
      final repository = _FakeWorkbookRepository(
        initialized: true,
        readyForReview: true,
      );
      await tester.binding.setSurfaceSize(const Size(360, 640));
      addTearDown(() async => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(
        MaterialApp(
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(
              context,
            ).copyWith(textScaler: const TextScaler.linear(1.3)),
            child: child!,
          ),
          home: ManagementOpeningBalanceWorkbookPage(
            session: _session,
            deviceIdentityProvider: _deviceIdentityProvider(),
            repository: repository,
          ),
        ),
      );
      await tester.pumpAndSettle();

      final editLine = find.byKey(const Key('edit-opening-workbook-line-1020'));
      await tester.dragUntilVisible(
        editLine,
        find.byType(ListView),
        const Offset(0, -300),
      );
      await tester.pumpAndSettle();
      await tester.tap(editLine);
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('opening-line-debit')),
        '200',
      );
      final verificationStatus = find.byKey(
        const Key('opening-line-verification-status'),
      );
      await tester.ensureVisible(verificationStatus);
      await tester.pumpAndSettle();
      await tester.tap(verificationStatus);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Verified').last);
      await tester.ensureVisible(
        find.byKey(const Key('opening-line-evidence-note')),
      );
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('opening-line-evidence-note')),
        'Reconciled to physical collector cash',
      );
      await tester.tap(find.byKey(const Key('save-opening-workbook-line')));
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('management-review-opening-workbook')),
        findsOneWidget,
      );
      expect(repository.updatedAccountCode, isNull);
      await tester.tap(find.byKey(const Key('confirm-opening-workbook')));
      await tester.pumpAndSettle();
      expect(repository.updatedAccountCode, '1020');
      expect(repository.updatedDebit, 200);
      expect(repository.updatedCredit, isNull);
      expect(repository.updatedVerificationStatus, 'verified');
      expect(
        repository.updatedEvidenceNote,
        'Reconciled to physical collector cash',
      );

      final editPolicy = find.byKey(const Key('edit-opening-workbook-policy'));
      await tester.dragUntilVisible(
        editPolicy,
        find.byType(ListView),
        const Offset(0, 300),
      );
      await tester.pumpAndSettle();
      await tester.tap(editPolicy);
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('opening-policy-note')),
        'Approved retained earnings conversion policy',
      );
      final policyConfirmed = find.byKey(const Key('opening-policy-confirmed'));
      final policySwitch = find.descendant(
        of: policyConfirmed,
        matching: find.byType(Switch),
      );
      final policyDialogScroll = find
          .descendant(
            of: find.byType(AlertDialog),
            matching: find.byType(SingleChildScrollView),
          )
          .first;
      await tester.drag(policyDialogScroll, const Offset(0, -180));
      await tester.pumpAndSettle();
      await tester.tap(policySwitch);
      await tester.pump();
      await tester.tap(find.byKey(const Key('save-opening-workbook-policy')));
      await tester.pumpAndSettle();

      expect(repository.policyConfirmed, isNull);
      expect(
        find.text(
          'The workbook policy evidence will be saved. No opening balance or '
          'General Ledger entry will be posted.',
        ),
        findsOneWidget,
      );
      await tester.tap(find.byKey(const Key('confirm-opening-workbook')));
      await tester.pumpAndSettle();
      expect(repository.policyConfirmed, isTrue);
      expect(
        repository.policyNote,
        'Approved retained earnings conversion policy',
      );

      final markReady = find.byKey(
        const Key('opening-workbook-mark-review-ready'),
      );
      await tester.dragUntilVisible(
        markReady,
        find.byType(ListView),
        const Offset(0, -300),
      );
      await tester.pumpAndSettle();
      await tester.tap(markReady);
      await tester.pumpAndSettle();
      expect(find.text('Change workbook to Review Ready'), findsWidgets);
      expect(repository.changedStatus, isNull);
      await tester.tap(find.byKey(const Key('confirm-opening-workbook')));
      await tester.pumpAndSettle();
      expect(repository.changedStatus, 'review_ready');
    },
  );
}

const _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>['accounting.cutover.manage'],
);

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'management-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

class _FakeWorkbookRepository implements OpeningBalanceWorkbookRepository {
  _FakeWorkbookRepository({
    required this.initialized,
    this.readyForReview = false,
  });

  bool initialized;
  final bool readyForReview;
  String workbookStatus = 'draft';
  String? deviceId;
  DateTime? createdCutoverDate;
  String? updatedAccountCode;
  double? updatedDebit;
  double? updatedCredit;
  String? updatedVerificationStatus;
  String? updatedEvidenceNote;
  bool? policyConfirmed;
  String? policyNote;
  String? changedStatus;

  OpeningBalanceWorkbookData _data() {
    return OpeningBalanceWorkbookData(
      managementEnabled: true,
      notice:
          'Stage 5D workbook values remain outside the General Ledger. Saving and verifying do not post an opening journal.',
      summary: OpeningBalanceWorkbookSummary(
        workbookId: initialized ? 'workbook-1' : null,
        cutoverDate: initialized ? DateTime(2026, 8, 8) : null,
        status: initialized ? workbookStatus : 'source_review_required',
        lineCount: 11,
        sourceReferenceCount: 4,
        verifiedLineCount: 0,
        pendingLineCount: 11,
        profitLossPolicyConfirmed: false,
        profitLossPolicyNote: null,
        totalDebit: 0,
        totalCredit: 0,
        balanceVariance: 0,
        worksheetBalanced: false,
        readyForReview: readyForReview,
        readyToPost: false,
        openingBalancePostingEnabled: false,
        automaticSourcePostingEnabled: false,
      ),
      lines: <OpeningBalanceWorkbookLine>[
        OpeningBalanceWorkbookLine(
          workbookId: initialized ? 'workbook-1' : null,
          accountCode: '1020',
          systemKey: 'cash_collector_custody',
          accountName: 'Cash - Collector Custody',
          accountType: 'asset',
          normalBalance: 'debit',
          sourceReferenceAmount: 200,
          sourceBasis: 'collection_custody_reference',
          requirementType: 'reconciliation_required',
          guidance: 'Reconcile to physical collector cash.',
          proposedDebit: null,
          proposedCredit: null,
          verificationStatus: 'pending',
          evidenceNote: null,
          measurementReferenceAmount: null,
          measurementStatus: null,
          measurementNote: null,
        ),
      ],
      measurement: AccountingMeasurementData(
        notice: 'Measurement is reference only and does not post.',
        summary: AccountingMeasurementSummary(
          activeLoanCount: initialized ? 7 : 0,
          measuredLoanCount: initialized ? 7 : 0,
          reviewRequiredCount: 0,
          actualCashReceived: initialized ? 450 : 0,
          effectiveInterestIncome: initialized ? 793.11 : 0,
          regularLoanComponent: initialized ? 19723.77 : 0,
          sevenBySevenLoanComponent: initialized ? 9000 : 0,
          accruedInterestComponent: initialized ? 619.36 : 0,
          grossCarryingAmount: initialized ? 29343.11 : 0,
          measurementStatus: initialized
              ? 'measured'
              : 'cutover_workbook_required',
          measurementPolicyVersion: 'eir_cutover_v1',
          eclIncluded: false,
          readyToPost: false,
        ),
        loans: const <LoanAccountingMeasurement>[],
      ),
    );
  }

  @override
  Future<OpeningBalanceWorkbookData> load(
    UserSession session, {
    required String deviceId,
  }) async {
    this.deviceId = deviceId;
    return _data();
  }

  @override
  Future<OpeningBalanceWorkbookData> create(
    UserSession session, {
    required String deviceId,
    required DateTime cutoverDate,
  }) async {
    this.deviceId = deviceId;
    initialized = true;
    createdCutoverDate = cutoverDate;
    return _data();
  }

  @override
  Future<OpeningBalanceWorkbookData> updateLine(
    UserSession session, {
    required String deviceId,
    required String workbookId,
    required String accountCode,
    required double? debit,
    required double? credit,
    required String verificationStatus,
    required String? evidenceNote,
  }) async {
    this.deviceId = deviceId;
    updatedAccountCode = accountCode;
    updatedDebit = debit;
    updatedCredit = credit;
    updatedVerificationStatus = verificationStatus;
    updatedEvidenceNote = evidenceNote;
    return _data();
  }

  @override
  Future<OpeningBalanceWorkbookData> updatePolicy(
    UserSession session, {
    required String deviceId,
    required String workbookId,
    required bool confirmed,
    required String? policyNote,
  }) async {
    this.deviceId = deviceId;
    policyConfirmed = confirmed;
    this.policyNote = policyNote;
    return _data();
  }

  @override
  Future<OpeningBalanceWorkbookData> changeStatus(
    UserSession session, {
    required String deviceId,
    required String workbookId,
    required String status,
  }) async {
    this.deviceId = deviceId;
    changedStatus = status;
    workbookStatus = status;
    return _data();
  }
}
