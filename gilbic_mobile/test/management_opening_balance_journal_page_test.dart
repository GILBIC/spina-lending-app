import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/opening_balance_journal.dart';
import 'package:gilbic_mobile/src/core/management/opening_balance_journal_repository.dart';
import 'package:gilbic_mobile/src/core/management/opening_balance_workbook.dart';
import 'package:gilbic_mobile/src/core/management/opening_balance_workbook_repository.dart';
import 'package:gilbic_mobile/src/features/management/management_opening_balance_journal_page.dart';

void main() {
  testWidgets('Preparation stays blocked until workbook is review ready', (
    tester,
  ) async {
    final workbookRepository = _FakeWorkbookRepository(status: 'draft');
    final journalRepository = _FakeJournalRepository(workbookStatus: 'draft');

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementOpeningBalanceJournalPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          workbookRepository: workbookRepository,
          journalRepository: journalRepository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Opening Balance Journal'), findsOneWidget);
    expect(find.textContaining('Blocked: Opening Balance Workbook'), findsOneWidget);
    final button = tester.widget<FilledButton>(
      find.byKey(const Key('prepare-opening-journal-draft')),
    );
    expect(button.onPressed, isNull);
    expect(journalRepository.prepared, isFalse);
    expect(journalRepository.posted, isFalse);
  });

  testWidgets('Review ready workbook still shows stricter exact-balance blocker', (
    tester,
  ) async {
    final workbookRepository = _FakeWorkbookRepository(status: 'review_ready');
    final journalRepository = _FakeJournalRepository(
      workbookStatus: 'review_ready',
      preparationReady: false,
      preparationBlocker:
          'Reviewed workbook must balance exactly to the cent before journal preparation.',
    );

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementOpeningBalanceJournalPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          workbookRepository: workbookRepository,
          journalRepository: journalRepository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    final prepareButton = find.byKey(const Key('prepare-opening-journal-draft'));
    await tester.scrollUntilVisible(
      prepareButton,
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();

    expect(
      find.textContaining('Reviewed workbook must balance exactly to the cent'),
      findsOneWidget,
    );
    final button = tester.widget<FilledButton>(prepareButton);
    expect(button.onPressed, isNull);
    expect(journalRepository.prepared, isFalse);
  });

  testWidgets('Draft preparation and ledger posting require separate confirmations', (
    tester,
  ) async {
    final workbookRepository = _FakeWorkbookRepository(status: 'review_ready');
    final journalRepository = _FakeJournalRepository(
      workbookStatus: 'review_ready',
    );

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementOpeningBalanceJournalPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          workbookRepository: workbookRepository,
          journalRepository: journalRepository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    final prepareButton = find.byKey(const Key('prepare-opening-journal-draft'));
    await tester.scrollUntilVisible(
      prepareButton,
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    await tester.tap(prepareButton);
    await tester.pumpAndSettle();
    expect(find.text('Prepare opening journal draft?'), findsOneWidget);
    expect(journalRepository.prepared, isFalse);

    await tester.tap(find.byKey(const Key('confirm-opening-journal-draft')));
    await tester.pumpAndSettle();

    expect(journalRepository.prepared, isTrue);
    expect(journalRepository.posted, isFalse);
    expect(find.text('Draft prepared'), findsOneWidget);

    final postButton = find.byKey(const Key('post-opening-journal'));
    await tester.scrollUntilVisible(
      postButton,
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    final enabledPostButton = tester.widget<FilledButton>(postButton);
    expect(enabledPostButton.onPressed, isNotNull);

    await tester.tap(postButton);
    await tester.pumpAndSettle();
    expect(find.text('Post opening balances to General Ledger?'), findsOneWidget);
    expect(find.textContaining('Debit: ₱1,000.00'), findsOneWidget);
    expect(find.textContaining('Credit: ₱1,000.00'), findsOneWidget);
    expect(journalRepository.posted, isFalse);

    await tester.tap(find.byKey(const Key('confirm-post-opening-journal')));
    await tester.pumpAndSettle();

    expect(journalRepository.posted, isTrue);
    expect(find.text('Posted'), findsWidgets);
    expect(find.text('JE-202608-00000001'), findsOneWidget);
    expect(find.text('Automatic source posting'), findsOneWidget);
    expect(find.text('Disabled'), findsWidgets);
    expect(find.textContaining('corrections require a controlled reversal'), findsWidgets);
  });

  testWidgets('Posting gate stays blocked when server readiness is false', (
    tester,
  ) async {
    final workbookRepository = _FakeWorkbookRepository(status: 'review_ready');
    final journalRepository = _FakeJournalRepository(
      workbookStatus: 'review_ready',
      initiallyPrepared: true,
      postingReady: false,
      postingBlocker: 'Cutover accounting period must remain open before posting.',
    );

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementOpeningBalanceJournalPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          workbookRepository: workbookRepository,
          journalRepository: journalRepository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    final postButton = find.byKey(const Key('post-opening-journal'));
    await tester.scrollUntilVisible(
      postButton,
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();

    expect(
      find.textContaining('Cutover accounting period must remain open'),
      findsOneWidget,
    );
    expect(tester.widget<FilledButton>(postButton).onPressed, isNull);
    expect(journalRepository.posted, isFalse);
  });
}

const UserSession _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>[
    'accounting.view',
    'accounting.opening_balance.prepare',
    'accounting.opening_balance.post',
  ],
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
  _FakeWorkbookRepository({required this.status});

  final String status;

  @override
  Future<OpeningBalanceWorkbookData> load(
    UserSession session, {
    required String deviceId,
  }) async => _workbook(status);

  @override
  Future<OpeningBalanceWorkbookData> create(
    UserSession session, {
    required String deviceId,
    required DateTime cutoverDate,
  }) => throw UnimplementedError();

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
  }) => throw UnimplementedError();

  @override
  Future<OpeningBalanceWorkbookData> updatePolicy(
    UserSession session, {
    required String deviceId,
    required String workbookId,
    required bool confirmed,
    required String? policyNote,
  }) => throw UnimplementedError();

  @override
  Future<OpeningBalanceWorkbookData> changeStatus(
    UserSession session, {
    required String deviceId,
    required String workbookId,
    required String status,
  }) => throw UnimplementedError();
}

class _FakeJournalRepository implements OpeningBalanceJournalRepository {
  _FakeJournalRepository({
    required this.workbookStatus,
    this.preparationReady,
    this.preparationBlocker,
    this.postingReady,
    this.postingBlocker,
    bool initiallyPrepared = false,
  }) : prepared = initiallyPrepared;

  final String workbookStatus;
  final bool? preparationReady;
  final String? preparationBlocker;
  final bool? postingReady;
  final String? postingBlocker;
  bool prepared;
  bool posted = false;

  @override
  Future<OpeningBalanceJournalDraftStatus> load(
    UserSession session, {
    required String deviceId,
    required String workbookId,
  }) async => _status();

  @override
  Future<OpeningBalanceJournalDraftStatus> prepare(
    UserSession session, {
    required String deviceId,
    required String workbookId,
  }) async {
    prepared = true;
    return _status();
  }

  @override
  Future<OpeningBalanceJournalDraftStatus> post(
    UserSession session, {
    required String deviceId,
    required String workbookId,
    required String journalEntryId,
    required double totalDebit,
    required double totalCredit,
  }) async {
    expect(journalEntryId, 'journal-1');
    expect(totalDebit, 1000);
    expect(totalCredit, 1000);
    posted = true;
    return _status();
  }

  OpeningBalanceJournalDraftStatus _status() {
    final prepareReady = !prepared &&
        (preparationReady ?? workbookStatus == 'review_ready');
    final prepareBlocker = prepared
        ? 'Protected opening-balance journal draft is already prepared.'
        : prepareReady
            ? null
            : preparationBlocker ??
                'Opening Balance Workbook must be Review Ready before journal preparation.';
    final postReady = prepared && !posted && (postingReady ?? true);
    final postBlocker = posted
        ? 'Opening-balance journal is already posted.'
        : prepared && !postReady
            ? postingBlocker ?? 'Protected posting requirements are not complete.'
            : prepared
                ? null
                : 'Prepare the protected opening-balance journal draft before posting.';
    return OpeningBalanceJournalDraftStatus(
      workbookId: 'workbook-1',
      cutoverDate: DateTime(2026, 8, 8),
      workbookStatus: workbookStatus,
      journalEntryId: prepared ? 'journal-1' : null,
      journalStatus: prepared ? (posted ? 'posted' : 'draft') : null,
      entryNumber: posted ? 'JE-202608-00000001' : null,
      journalLineCount: prepared ? 3 : 0,
      totalDebit: prepared ? 1000 : 0,
      totalCredit: prepared ? 1000 : 0,
      draftPrepared: prepared,
      preparationReady: prepareReady,
      preparationBlocker: prepareBlocker,
      openingBalancePostingEnabled: true,
      automaticSourcePostingEnabled: false,
      postingReady: postReady,
      postingBlocker: postBlocker,
      postedByUserId: posted ? 'management-1' : null,
      postedAt: posted ? DateTime(2026, 8, 9, 20, 0) : null,
      notice: posted
          ? 'Opening balances are posted and immutable; corrections require a controlled reversal.'
          : 'Protected journal. Explicit Management posting is required.',
    );
  }
}

OpeningBalanceWorkbookData _workbook(String status) {
  return OpeningBalanceWorkbookData(
    summary: OpeningBalanceWorkbookSummary(
      workbookId: 'workbook-1',
      cutoverDate: DateTime(2026, 8, 8),
      status: status,
      lineCount: 11,
      sourceReferenceCount: 4,
      verifiedLineCount: status == 'review_ready' ? 11 : 5,
      pendingLineCount: status == 'review_ready' ? 0 : 6,
      profitLossPolicyConfirmed: status == 'review_ready',
      profitLossPolicyNote: status == 'review_ready' ? 'Approved cutover policy.' : null,
      totalDebit: status == 'review_ready' ? 1000 : 500,
      totalCredit: status == 'review_ready' ? 1000 : 400,
      balanceVariance: status == 'review_ready' ? 0 : 100,
      worksheetBalanced: status == 'review_ready',
      readyForReview: status == 'review_ready',
      readyToPost: false,
      openingBalancePostingEnabled: false,
      automaticSourcePostingEnabled: false,
    ),
    lines: const <OpeningBalanceWorkbookLine>[],
    measurement: const AccountingMeasurementData(
      summary: AccountingMeasurementSummary(
        activeLoanCount: 0,
        measuredLoanCount: 0,
        reviewRequiredCount: 0,
        actualCashReceived: 0,
        effectiveInterestIncome: 0,
        regularLoanComponent: 0,
        sevenBySevenLoanComponent: 0,
        accruedInterestComponent: 0,
        grossCarryingAmount: 0,
        measurementStatus: 'not_measured',
        measurementPolicyVersion: 'test',
        eclIncluded: false,
        readyToPost: false,
      ),
      loans: <LoanAccountingMeasurement>[],
      notice: 'Synthetic test measurement.',
    ),
    managementEnabled: true,
    notice: 'Synthetic test workbook.',
  );
}
