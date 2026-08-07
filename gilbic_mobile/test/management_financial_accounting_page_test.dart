import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/financial_accounting.dart';
import 'package:gilbic_mobile/src/core/management/financial_accounting_repository.dart';
import 'package:gilbic_mobile/src/features/management/management_financial_accounting_page.dart';

void main() {
  testWidgets('Management sees accounting foundation, periods, and loan policies', (
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
    expect(find.textContaining('Open'), findsWidgets);
    expect(find.textContaining('Foundation ready'), findsOneWidget);
    expect(find.text('Unavailable'), findsOneWidget);

    final periods = find.byKey(const Key('financial-accounting-fiscal-periods'));
    await tester.scrollUntilVisible(
      periods,
      350,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    expect(find.text('Fiscal Periods'), findsOneWidget);
    expect(find.text('August 2026'), findsOneWidget);
    expect(find.text('2026-08-01 – 2026-08-31'), findsOneWidget);
    expect(find.text('Send to review'), findsOneWidget);
    expect(find.byKey(const Key('create-accounting-period')), findsOneWidget);

    final chart = find.byKey(const Key('financial-accounting-chart-of-accounts'));
    await tester.scrollUntilVisible(
      chart,
      400,
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
      500,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    expect(find.text('7x7'), findsOneWidget);
    expect(find.text('₱7.00 / ₱1,000'), findsOneWidget);
    expect(find.text('Disabled'), findsOneWidget);
    expect(
      find.textContaining('Cash release = new principal'),
      findsOneWidget,
    );
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
      400,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    await tester.tap(reviewButton);
    await tester.pumpAndSettle();

    expect(repository.lastStatus, 'review');
    expect(find.text('Review'), findsWidgets);
    expect(find.text('Close period'), findsOneWidget);
    expect(find.text('Reopen'), findsOneWidget);
  });

  testWidgets('Closing a review period requires visible confirmation', (
    tester,
  ) async {
    final repository = _FakeAccountingRepository(initialStatus: 'review');

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

    final closeButton = find.byKey(const Key('period-close-period-aug-2026'));
    await tester.scrollUntilVisible(
      closeButton,
      400,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    await tester.tap(closeButton);
    await tester.pumpAndSettle();

    expect(find.text('Close accounting period?'), findsOneWidget);
    expect(find.byKey(const Key('confirm-close-accounting-period')), findsOneWidget);
    expect(repository.lastStatus, isNull);

    await tester.tap(find.byKey(const Key('confirm-close-accounting-period')));
    await tester.pumpAndSettle();

    expect(repository.lastStatus, 'closed');
    expect(repository.lastConfirmClose, isTrue);
    expect(find.text('Closed'), findsWidgets);
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

class _FakeAccountingRepository implements FinancialAccountingRepository {
  _FakeAccountingRepository({String initialStatus = 'open'})
      : _status = initialStatus;

  String? deviceId;
  String? lastStatus;
  bool? lastConfirmClose;
  String _status;

  @override
  Future<FinancialAccountingOverview> loadOverview(
    UserSession session, {
    required String deviceId,
  }) async {
    this.deviceId = deviceId;
    return FinancialAccountingOverview(
      notice:
          'Financial Accounting now has protected fiscal-period controls.',
      foundationStatus: 'ready',
      fiscalPeriodStatus: _status == 'open' ? 'open' : 'configured',
      periodManagementEnabled: true,
      journalStatus: 'foundation_ready',
      trialBalanceStatus: 'unavailable',
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
        journalEntryCount: 0,
        draftJournalCount: 0,
        postedJournalCount: 0,
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
          journalCount: 0,
          draftJournalCount: 0,
          postedJournalCount: 0,
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
              'Track principal receivable and accrued interest separately.',
          renewalRule:
              'Cash release = new principal minus old principal outstanding minus accrued unpaid interest.',
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
      journalCount: 0,
      draftJournalCount: 0,
      postedJournalCount: 0,
      closedByName: status == 'closed' ? 'Management' : null,
    );
  }
}
