import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/ecl_allowance_posting.dart';
import 'package:gilbic_mobile/src/core/management/ecl_allowance_posting_repository.dart';
import 'package:gilbic_mobile/src/core/management/financial_accounting.dart';
import 'package:gilbic_mobile/src/core/management/financial_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/management/period_close.dart';
import 'package:gilbic_mobile/src/core/management/period_close_repository.dart';
import 'package:gilbic_mobile/src/features/management/management_financial_accounting_page.dart';
import 'package:gilbic_mobile/src/features/management/management_ecl_allowance_posting_page.dart';
import 'package:gilbic_mobile/src/features/management/management_period_close_page.dart';

void main() {
  testWidgets('Management guidance hides obsolete backend stage labels', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: ManagementFinancialAccountingPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: _FakeAccountingRepository(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('Stage 5B'), findsNothing);
    expect(
      find.byKey(const Key('financial-accounting-management-guidance')),
      findsOneWidget,
    );
    expect(
      find.textContaining(
        'Official amounts come from protected server records',
      ),
      findsOneWidget,
    );
  });

  testWidgets('Detailed cutover loan evidence starts collapsed', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: ManagementFinancialAccountingPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: _FakeAccountingRepository(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    final cutover = find.byKey(
      const Key('financial-accounting-cutover-readiness'),
    );
    await tester.scrollUntilVisible(
      cutover,
      400,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();

    expect(find.text('Accounting Cutover Readiness'), findsOneWidget);
    expect(find.text('7x7 validated base contract schedule'), findsNothing);

    await tester.tap(find.text('Accounting Cutover Readiness'));
    await tester.pumpAndSettle();

    expect(find.text('7x7 validated base contract schedule'), findsOneWidget);
  });

  testWidgets('Management sees accounting cutover readiness and worksheet', (
    tester,
  ) async {
    final repository = _FakeAccountingRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementFinancialAccountingPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Financial Accounting'), findsOneWidget);
    expect(find.text('Operational outstanding'), findsOneWidget);
    expect(find.text('Unremitted cash'), findsOneWidget);
    expect(find.text('₱28,550.00'), findsOneWidget);
    expect(repository.deviceId, 'management-device');

    final readiness = find.byKey(const Key('financial-accounting-readiness'));
    await tester.scrollUntilVisible(
      readiness,
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    expect(find.text('Posting readiness'), findsOneWidget);
    expect(find.text('Ready'), findsOneWidget);
    expect(find.textContaining('23 / 23 posting'), findsOneWidget);
    expect(find.textContaining('Manual ready'), findsOneWidget);
    expect(find.textContaining('Available'), findsOneWidget);

    final cutover = find.byKey(
      const Key('financial-accounting-cutover-readiness'),
    );
    await tester.scrollUntilVisible(
      cutover,
      400,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    expect(find.text('Accounting Cutover Readiness'), findsOneWidget);
    expect(find.text('7 / 7 loan sources ready'), findsOneWidget);
    await tester.tap(find.text('Accounting Cutover Readiness'));
    await tester.pumpAndSettle();
    expect(find.text('Opening balances required'), findsOneWidget);
    expect(find.text('3 validated'), findsOneWidget);
    expect(find.text('7x7 validated base contract schedule'), findsOneWidget);
    expect(find.text('₱2,520.00'), findsWidgets);
    expect(find.text('₱5,520.00'), findsWidgets);
    expect(find.text('0.7000%'), findsWidgets);

    final worksheet = find.byKey(
      const Key('financial-accounting-opening-balance-worksheet'),
    );
    await tester.scrollUntilVisible(
      worksheet,
      450,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    expect(find.text('Opening Balance / Cutover Worksheet'), findsOneWidget);
    await tester.tap(worksheet);
    await tester.pumpAndSettle();
    expect(find.text('Not selected'), findsOneWidget);
    expect(find.textContaining('Source review required'), findsOneWidget);
    expect(find.text('Cash - Collector Custody'), findsOneWidget);
    expect(find.text('Loans Receivable - Regular'), findsOneWidget);
    expect(find.text('₱200.00'), findsWidgets);
    expect(find.text('₱19,550.00'), findsWidgets);
    expect(find.text('Disabled'), findsWidgets);

    final periods = find.byKey(
      const Key('financial-accounting-fiscal-periods'),
    );
    await tester.scrollUntilVisible(
      periods,
      500,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    expect(find.text('Fiscal Periods'), findsOneWidget);
    expect(find.text('August 2026'), findsOneWidget);
    expect(find.text('2026-08-01 – 2026-08-31'), findsOneWidget);
    expect(find.text('Send to review'), findsOneWidget);
    expect(find.byKey(const Key('create-accounting-period')), findsOneWidget);

    final chart = find.byKey(
      const Key('financial-accounting-chart-of-accounts'),
    );
    await tester.scrollUntilVisible(
      chart,
      500,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    expect(find.text('Chart of Accounts'), findsOneWidget);
    await tester.tap(chart);
    await tester.pumpAndSettle();
    expect(find.text('Cash - Office'), findsOneWidget);
    expect(find.text('Interest Income - Regular'), findsOneWidget);

    final sevenBySeven = find.byKey(
      const Key('financial-accounting-policy-seven_by_seven_mobile_test'),
    );
    await tester.scrollUntilVisible(
      sevenBySeven,
      600,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    expect(find.text('7x7'), findsOneWidget);
    expect(find.text('₱7.00 / ₱1,000'), findsOneWidget);
    expect(find.text('Disabled'), findsWidgets);
    expect(find.textContaining('Cash release = new principal'), findsOneWidget);
  });

  testWidgets('Management can move an open period to review', (tester) async {
    final repository = _FakeAccountingRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementFinancialAccountingPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    final reviewButton = find.byKey(const Key('period-review-period-aug-2026'));
    await tester.scrollUntilVisible(
      reviewButton,
      600,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    await tester.tap(reviewButton);
    await tester.pumpAndSettle();

    expect(
      find.byKey(const Key('management-review-fiscal-period')),
      findsOneWidget,
    );
    expect(find.text('Change period to Review'), findsWidgets);
    expect(
      find.text(
        'The period will move to Management review and the server will apply '
        'review-state restrictions. Posted journals remain unchanged.',
      ),
      findsOneWidget,
    );
    expect(repository.lastStatus, isNull);

    await tester.tap(find.byKey(const Key('cancel-fiscal-period')));
    await tester.pumpAndSettle();
    expect(repository.lastStatus, isNull);

    await tester.tap(reviewButton);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('confirm-fiscal-period')));
    await tester.pumpAndSettle();

    expect(repository.lastStatus, 'review');
    expect(find.text('Review'), findsWidgets);
    expect(find.text('Close period'), findsNothing);
    expect(find.text('Reopen'), findsOneWidget);
  });

  testWidgets('Formal close launcher replaces rejected direct status close', (
    tester,
  ) async {
    final repository = _FakeAccountingRepository(initialStatus: 'review');
    final periodCloseRepository = _FakePeriodCloseRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementFinancialAccountingPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
          periodCloseRepository: periodCloseRepository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('period-close-period-aug-2026')), findsNothing);
    final formalClose = find.byKey(const Key('formal-period-close'));
    await tester.scrollUntilVisible(
      formalClose,
      600,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    await tester.tap(formalClose);
    await tester.pumpAndSettle();

    expect(find.byType(ManagementPeriodClosePage), findsOneWidget);
    expect(find.text('Formal Period Close'), findsOneWidget);
    expect(periodCloseRepository.loadCalls, 1);
    expect(repository.lastStatus, isNull);
  });

  testWidgets('Initial ECL launcher opens the protected server queue', (
    tester,
  ) async {
    final repository = _FakeAccountingRepository();
    final eclRepository = _FakeEclAllowancePostingRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementFinancialAccountingPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
          eclAllowanceRepository: eclRepository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    final launcher = find.byKey(const Key('initial-ecl-allowance'));
    await tester.scrollUntilVisible(
      launcher,
      600,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    await tester.tap(launcher);
    await tester.pumpAndSettle();

    expect(find.byType(ManagementEclAllowancePostingPage), findsOneWidget);
    expect(find.text('Initial ECL Allowance'), findsOneWidget);
    expect(eclRepository.loadCalls, 1);
  });

  testWidgets('Creating a fiscal period is reviewed before repository write', (
    tester,
  ) async {
    final repository = _FakeAccountingRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementFinancialAccountingPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    final create = find.byKey(const Key('create-accounting-period'));
    await tester.scrollUntilVisible(
      create,
      600,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(create);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('accounting-period-label')),
      'Reviewed Test Period',
    );
    await tester.tap(find.byKey(const Key('save-accounting-period')));
    await tester.pumpAndSettle();

    expect(
      find.byKey(const Key('management-review-fiscal-period')),
      findsOneWidget,
    );
    expect(find.text('Create fiscal period'), findsWidgets);
    expect(
      find.text(
        'A new open fiscal period will be created. This does not post a journal '
        'or change any account balance.',
      ),
      findsOneWidget,
    );
    expect(repository.createdLabel, isNull);

    await tester.tap(find.byKey(const Key('cancel-fiscal-period')));
    await tester.pumpAndSettle();
    expect(repository.createdLabel, isNull);

    await tester.tap(create);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('accounting-period-label')),
      'Reviewed Test Period',
    );
    await tester.tap(find.byKey(const Key('save-accounting-period')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('confirm-fiscal-period')));
    await tester.pumpAndSettle();

    expect(repository.createdLabel, 'Reviewed Test Period');
    expect(repository.createdStartDate, isNotNull);
    expect(repository.createdEndDate, isNotNull);
    expect(
      repository.createdEndDate!.isBefore(repository.createdStartDate!),
      isFalse,
    );
  });
}

const UserSession _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>[],
);

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'management-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

class _FakePeriodCloseRepository implements PeriodCloseRepository {
  int loadCalls = 0;

  @override
  Future<PeriodCloseOverview> load(
    UserSession session, {
    required String deviceId,
    String status = 'all',
  }) async {
    loadCalls += 1;
    return const PeriodCloseOverview(
      summary: PeriodCloseSummary(
        periodCount: 0,
        readyForReviewCount: 0,
        readyToPrepareCount: 0,
        preparedCount: 0,
        protectedClosedCount: 0,
        blockedCount: 0,
        closedNetIncomeTotal: '0.00',
        protectedPeriodCloseEnabled: true,
        retainedEarningsCloseEnabled: true,
        closedPeriodPostingProtectionEnabled: true,
        periodReopenEnabled: false,
        automaticSourcePosting: false,
      ),
      items: <PeriodCloseItem>[],
      permissions: PeriodClosePermissions(
        closePrepare: false,
        closePost: false,
      ),
      notice: 'No formal close is ready.',
    );
  }

  @override
  Future<PeriodCloseItem> prepare(
    UserSession session, {
    required String deviceId,
    required String fiscalPeriodId,
  }) {
    throw UnsupportedError('No test period is ready to prepare.');
  }

  @override
  Future<PeriodCloseItem> post(
    UserSession session, {
    required String deviceId,
    required PeriodCloseItem item,
    required String confirmationToken,
  }) {
    throw UnsupportedError('No test period is ready to post.');
  }
}

class _FakeEclAllowancePostingRepository
    implements EclAllowancePostingRepository {
  int loadCalls = 0;

  @override
  Future<EclAllowancePostingOverview> load(
    UserSession session, {
    required String deviceId,
    String status = 'all',
    int limit = 100,
    int offset = 0,
  }) async {
    loadCalls += 1;
    return EclAllowancePostingOverview(
      summary: const EclAllowancePostingSummary(
        loanCount: 0,
        measurementNotAuthoritativeCount: 0,
        noAllowanceRequiredCount: 0,
        preparationRequiredCount: 0,
        postingReadyCount: 0,
        postedCurrentCount: 0,
        a5RemeasurementRequiredCount: 0,
        postingAuditIncompleteCount: 0,
        protectedAllowanceBalanceTotal: '0.00',
        account1190PostingEnabled: true,
        automaticSourcePosting: false,
      ),
      items: const <EclAllowancePostingItem>[],
      permissions: const EclAllowancePostingPermissions(
        prepare: false,
        post: false,
      ),
      notice: 'No initial allowance actions are ready.',
      filter: status,
      limit: limit,
      offset: offset,
    );
  }

  @override
  Future<EclAllowanceActionReceipt> prepare(
    UserSession session, {
    required String deviceId,
    required EclAllowancePostingItem item,
    required String reviewToken,
  }) {
    throw UnsupportedError('No test item is ready to prepare.');
  }

  @override
  Future<EclAllowanceActionReceipt> post(
    UserSession session, {
    required String deviceId,
    required EclAllowancePostingItem item,
    required String reviewToken,
  }) {
    throw UnsupportedError('No test item is ready to post.');
  }
}

class _FakeAccountingRepository implements FinancialAccountingRepository {
  _FakeAccountingRepository({String initialStatus = 'open'})
    : _status = initialStatus;

  String? deviceId;
  String? lastStatus;
  bool? lastConfirmClose;
  String? createdLabel;
  DateTime? createdStartDate;
  DateTime? createdEndDate;
  String _status;

  @override
  Future<FinancialAccountingOverview> loadOverview(
    UserSession session, {
    required String deviceId,
  }) async {
    this.deviceId = deviceId;
    return FinancialAccountingOverview(
      notice:
          'Stage 5B cutover readiness and opening-balance source worksheet.',
      foundationStatus: 'ready',
      fiscalPeriodStatus: _status == 'open' ? 'open' : 'configured',
      periodManagementEnabled: true,
      journalStatus: 'manual_ready',
      trialBalanceStatus: 'available',
      summary: const FinancialAccountingSummary(
        activeLoanCount: 7,
        activePrincipal: 29000,
        operationalOutstanding: 28550,
        regularOutstanding: 19550,
        sevenBySevenOutstanding: 9000,
        unremittedCash: 200,
        receivedRemittanceTotal: 250,
        validCollectionCount: 9,
        correctionCount: 1,
        voidCount: 1,
      ),
      foundation: AccountingFoundationSummary(
        accountCount: 23,
        postingAccountCount: 23,
        fiscalPeriodCount: 1,
        openPeriodCount: _status == 'open' ? 1 : 0,
        journalEntryCount: 2,
        draftJournalCount: 0,
        postedJournalCount: 2,
        reversalDraftCount: 0,
      ),
      accounts: const <AccountingAccount>[
        AccountingAccount(
          code: '1010',
          systemKey: 'cash_office',
          name: 'Cash - Office',
          accountType: 'asset',
          normalBalance: 'debit',
          isPosting: true,
          isActive: true,
        ),
        AccountingAccount(
          code: '4000',
          systemKey: 'interest_income_regular',
          name: 'Interest Income - Regular',
          accountType: 'income',
          normalBalance: 'credit',
          isPosting: true,
          isActive: true,
        ),
      ],
      fiscalPeriods: <AccountingFiscalPeriod>[
        AccountingFiscalPeriod(
          periodId: 'period-aug-2026',
          label: 'August 2026',
          startDate: DateTime(2026, 8, 1),
          endDate: DateTime(2026, 8, 31),
          status: _status,
          journalCount: 2,
          draftJournalCount: 0,
          postedJournalCount: 2,
          closedByName: _status == 'closed' ? 'Management' : null,
        ),
      ],
      policies: const <LoanAccountingPolicy>[
        LoanAccountingPolicy(
          code: 'regular_mobile_test',
          name: 'Regular',
          termDays: 120,
          calculationMode: 'fixed_daily',
          dailyInterestPer1000: 0,
          mobileCollectionsEnabled: true,
          operationalRule: 'Fixed contractual interest and daily collection.',
          accountingRule: 'Use an effective-interest schedule.',
          renewalRule: 'Close the old loan and create a new loan.',
        ),
        LoanAccountingPolicy(
          code: 'seven_by_seven_mobile_test',
          name: '7x7',
          termDays: 120,
          calculationMode: 'seven_by_seven',
          dailyInterestPer1000: 7,
          mobileCollectionsEnabled: false,
          operationalRule:
              'Daily interest stays based on the original principal until principal reaches zero.',
          accountingRule:
              'Validated daily-interest plus maturity-principal cash-flow schedule.',
          renewalRule:
              'Cash release = new principal minus old principal outstanding minus accrued unpaid interest.',
        ),
      ],
      cutoverSummary: const AccountingCutoverReadinessSummary(
        activeLoanCount: 7,
        sourceReadyCount: 7,
        contractValidationCount: 0,
        blockedCount: 0,
        openingBalancesConfigured: false,
        automaticSourcePostingEnabled: false,
        overallStatus: 'opening_balances_required',
      ),
      cutoverLoans: <AccountingCutoverLoan>[
        AccountingCutoverLoan(
          loanNumber: 'TEST-REG-20260802',
          clientCode: 'TEST-REG-001',
          clientName: 'TEST CLIENT REGULAR',
          loanTypeName: 'Regular',
          calculationMode: 'fixed_daily',
          termDays: 120,
          principal: 5000,
          dailyAmount: 50,
          interestRate: 20,
          dateReleased: DateTime(2026, 8, 1),
          dueDate: DateTime(2026, 11, 29),
          operationalBalance: 4900,
          regularContractTotal: 6000,
          regularScheduledTotal: 6000,
          sevenBySevenExpectedDailyInterest: null,
          sevenBySevenContractInterestTotal: null,
          sevenBySevenContractTotalIfPrincipalAtMaturity: null,
          sevenBySevenBaseDailyRatePercent: null,
          readinessStatus: 'source_ready',
          blockers: const <String>[],
        ),
        ...List<AccountingCutoverLoan>.generate(
          3,
          (index) => AccountingCutoverLoan(
            loanNumber: 'TEST-7X7-${index + 1}',
            clientCode: 'TEST-7X7-${index + 1}',
            clientName: 'TEST CLIENT 7X7 ${index + 1}',
            loanTypeName: '7x7',
            calculationMode: 'seven_by_seven',
            termDays: 120,
            principal: 3000,
            dailyAmount: 21,
            interestRate: null,
            dateReleased: DateTime(2026, 8, 2),
            dueDate: DateTime(2026, 11, 30),
            operationalBalance: 3000,
            regularContractTotal: null,
            regularScheduledTotal: null,
            sevenBySevenExpectedDailyInterest: 21,
            sevenBySevenContractInterestTotal: 2520,
            sevenBySevenContractTotalIfPrincipalAtMaturity: 5520,
            sevenBySevenBaseDailyRatePercent: 0.7,
            readinessStatus: 'source_ready',
            blockers: const <String>[],
          ),
        ),
      ],
      openingBalanceSummary: const OpeningBalanceCutoverSummary(
        cutoverDate: null,
        worksheetStatus: 'source_review_required',
        worksheetLineCount: 11,
        sourceReferenceCount: 4,
        manualRequiredCount: 5,
        reconciliationRequiredCount: 2,
        calculationRequiredCount: 3,
        assessmentRequiredCount: 1,
        profitLossMigrationPolicyRequired: true,
        worksheetBalanced: false,
        readyToPost: false,
        openingBalancePostingEnabled: false,
        automaticSourcePostingEnabled: false,
      ),
      openingBalanceLines: const <OpeningBalanceCutoverLine>[
        OpeningBalanceCutoverLine(
          accountCode: '1020',
          systemKey: 'cash_collector_custody',
          accountName: 'Cash - Collector Custody',
          accountType: 'asset',
          normalBalance: 'debit',
          sourceReferenceAmount: 200,
          sourceBasis: 'collection_custody_reference',
          readinessStatus: 'reconciliation_required',
          guidance: 'Reconcile to physical collector cash.',
        ),
        OpeningBalanceCutoverLine(
          accountCode: '1100',
          systemKey: 'loans_receivable_regular',
          accountName: 'Loans Receivable - Regular',
          accountType: 'asset',
          normalBalance: 'debit',
          sourceReferenceAmount: 19550,
          sourceBasis: 'regular_operational_reference',
          readinessStatus: 'calculation_required',
          guidance: 'Derive the PFRS carrying amount before posting.',
        ),
      ],
    );
  }

  @override
  Future<AccountingFiscalPeriod> createFiscalPeriod(
    UserSession session, {
    required String deviceId,
    required String label,
    required DateTime startDate,
    required DateTime endDate,
  }) async {
    this.deviceId = deviceId;
    createdLabel = label;
    createdStartDate = startDate;
    createdEndDate = endDate;
    return AccountingFiscalPeriod(
      periodId: 'created-period',
      label: label,
      startDate: startDate,
      endDate: endDate,
      status: 'open',
      journalCount: 0,
      draftJournalCount: 0,
      postedJournalCount: 0,
    );
  }

  @override
  Future<AccountingFiscalPeriod> changeFiscalPeriodStatus(
    UserSession session, {
    required String deviceId,
    required String periodId,
    required String status,
    bool confirmClose = false,
  }) async {
    this.deviceId = deviceId;
    lastStatus = status;
    lastConfirmClose = confirmClose;
    _status = status;
    return AccountingFiscalPeriod(
      periodId: periodId,
      label: 'August 2026',
      startDate: DateTime(2026, 8, 1),
      endDate: DateTime(2026, 8, 31),
      status: status,
      journalCount: 2,
      draftJournalCount: 0,
      postedJournalCount: 2,
      closedByName: status == 'closed' ? 'Management' : null,
    );
  }
}
