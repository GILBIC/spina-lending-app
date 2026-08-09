import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/financial_accounting.dart';
import 'package:gilbic_mobile/src/core/management/financial_statements.dart';
import 'package:gilbic_mobile/src/core/management/financial_statements_repository.dart';
import 'package:gilbic_mobile/src/features/management/management_financial_statements_page.dart';

void main() {
  testWidgets('Management sees posted-ledger financial statements', (tester) async {
    final repository = _FakeStatementsRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementFinancialStatementsPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          periods: _periods,
          statementsRepository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(repository.deviceId, 'management-device');
    expect(repository.periodId, 'period-aug-2026');
    expect(find.text('Financial Statements'), findsOneWidget);
    expect(find.text('August 2026 • Open'), findsOneWidget);
    expect(find.text('Statement of Profit or Loss'), findsOneWidget);
    expect(find.text('4000 Interest Income - Regular'), findsOneWidget);
    expect(find.text('₱1,500.00'), findsWidgets);
    expect(find.text('Net income'), findsOneWidget);
    expect(find.text('₱1,000.00'), findsWidgets);

    final position = find.byKey(const Key('financial-position-statement'));
    await tester.scrollUntilVisible(
      position,
      450,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();

    expect(find.text('Statement of Financial Position'), findsOneWidget);
    expect(find.text('Balanced'), findsOneWidget);
    expect(find.text('1190 Allowance for Expected Credit Loss'), findsOneWidget);
    expect(find.text('(₱200.00)'), findsOneWidget);
    expect(find.text('Total assets'), findsOneWidget);
    expect(find.text('Liabilities + equity'), findsOneWidget);
    expect(find.text('₱6,800.00'), findsWidgets);
  });

  testWidgets('Management can change the statement period', (tester) async {
    final repository = _FakeStatementsRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementFinancialStatementsPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          periods: _periods,
          statementsRepository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('financial-statements-period')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('July 2026 • Closed').last);
    await tester.pumpAndSettle();

    expect(repository.periodId, 'period-jul-2026');
  });
}

const UserSession _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>['accounting.view'],
);

final List<AccountingFiscalPeriod> _periods = <AccountingFiscalPeriod>[
  AccountingFiscalPeriod(
    periodId: 'period-aug-2026',
    label: 'August 2026',
    startDate: DateTime(2026, 8, 1),
    endDate: DateTime(2026, 8, 31),
    status: 'open',
    journalCount: 3,
    draftJournalCount: 0,
    postedJournalCount: 3,
  ),
  AccountingFiscalPeriod(
    periodId: 'period-jul-2026',
    label: 'July 2026',
    startDate: DateTime(2026, 7, 1),
    endDate: DateTime(2026, 7, 31),
    status: 'closed',
    journalCount: 2,
    draftJournalCount: 0,
    postedJournalCount: 2,
  ),
];

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'management-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

class _FakeStatementsRepository implements FinancialStatementsRepository {
  String? deviceId;
  String? periodId;

  @override
  Future<AccountingFinancialStatements> loadStatements(
    UserSession session, {
    required String deviceId,
    String? periodId,
  }) async {
    this.deviceId = deviceId;
    this.periodId = periodId;
    final isJuly = periodId == 'period-jul-2026';
    final period = isJuly
        ? FinancialStatementPeriod(
            periodId: 'period-jul-2026',
            label: 'July 2026',
            startDate: _julyStart,
            endDate: _julyEnd,
            status: 'closed',
          )
        : FinancialStatementPeriod(
            periodId: 'period-aug-2026',
            label: 'August 2026',
            startDate: _augustStart,
            endDate: _augustEnd,
            status: 'open',
          );
    return AccountingFinancialStatements(
      period: period,
      profitOrLoss: const ProfitOrLossStatement(
        incomeLines: <FinancialStatementLine>[
          FinancialStatementLine(
            accountCode: '4000',
            accountName: 'Interest Income - Regular',
            amount: 1500,
          ),
        ],
        expenseLines: <FinancialStatementLine>[
          FinancialStatementLine(
            accountCode: '5100',
            accountName: 'Salaries and Wages Expense',
            amount: 500,
          ),
        ],
        totalIncome: 1500,
        totalExpenses: 500,
        netIncome: 1000,
      ),
      financialPosition: FinancialPositionStatement(
        asOfDate: isJuly ? _julyEnd : _augustEnd,
        assetLines: const <FinancialStatementLine>[
          FinancialStatementLine(
            accountCode: '1010',
            accountName: 'Cash - Office',
            amount: 2000,
          ),
          FinancialStatementLine(
            accountCode: '1100',
            accountName: 'Loans Receivable - Regular',
            amount: 5000,
          ),
          FinancialStatementLine(
            accountCode: '1190',
            accountName: 'Allowance for Expected Credit Loss',
            amount: -200,
          ),
        ],
        liabilityLines: const <FinancialStatementLine>[
          FinancialStatementLine(
            accountCode: '2000',
            accountName: 'Accounts Payable',
            amount: 1000,
          ),
        ],
        equityLines: const <FinancialStatementLine>[
          FinancialStatementLine(
            accountCode: '3000',
            accountName: 'Capital',
            amount: 4000,
          ),
          FinancialStatementLine(
            accountCode: '3100',
            accountName: 'Retained Earnings',
            amount: 800,
          ),
        ],
        totalAssets: 6800,
        totalLiabilities: 1000,
        recordedEquity: 4800,
        unclosedEarningsToDate: 1000,
        totalEquity: 5800,
        totalLiabilitiesAndEquity: 6800,
        balanced: true,
      ),
      source: 'posted_general_ledger_only',
      notice: 'Posted General Ledger entries only.',
    );
  }
}

final DateTime _augustStart = DateTime(2026, 8, 1);
final DateTime _augustEnd = DateTime(2026, 8, 31);
final DateTime _julyStart = DateTime(2026, 7, 1);
final DateTime _julyEnd = DateTime(2026, 7, 31);
