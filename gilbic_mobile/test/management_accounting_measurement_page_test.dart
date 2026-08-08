import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/opening_balance_workbook.dart';
import 'package:gilbic_mobile/src/core/management/opening_balance_workbook_repository.dart';
import 'package:gilbic_mobile/src/features/management/management_accounting_measurement_page.dart';

void main() {
  testWidgets('Management sees measured EIR cutover references without posting', (
    tester,
  ) async {
    final repository = _FakeMeasurementRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementAccountingMeasurementPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Loan Measurement'), findsOneWidget);
    expect(find.byKey(const Key('accounting-measurement-summary')), findsOneWidget);
    expect(find.text('7 / 7'), findsOneWidget);
    expect(find.text('₱19,723.77'), findsWidgets);
    expect(find.text('₱9,000.00'), findsWidgets);
    expect(find.text('₱619.36'), findsWidgets);
    expect(find.text('₱29,343.11'), findsOneWidget);
    expect(find.text('No'), findsWidgets);

    await tester.scrollUntilVisible(
      find.text('Workbook measurement references'),
      250,
    );
    expect(
      find.byKey(const Key('accounting-measurement-workbook-references')),
      findsOneWidget,
    );

    await tester.scrollUntilVisible(
      find.byKey(const Key('loan-measurement-TEST-REG-20260802')),
      250,
    );
    expect(find.text('TEST-REG-20260802'), findsOneWidget);
    expect(repository.deviceId, 'management-device');
  });
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

class _FakeMeasurementRepository implements OpeningBalanceWorkbookRepository {
  String? deviceId;

  OpeningBalanceWorkbookData _data() => OpeningBalanceWorkbookData(
        managementEnabled: true,
        notice: 'Workbook remains non-posting.',
        summary: OpeningBalanceWorkbookSummary(
          workbookId: 'workbook-1',
          cutoverDate: DateTime(2026, 8, 8),
          status: 'draft',
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
          readyForReview: false,
          readyToPost: false,
          openingBalancePostingEnabled: false,
          automaticSourcePostingEnabled: false,
        ),
        lines: const <OpeningBalanceWorkbookLine>[
          OpeningBalanceWorkbookLine(
            workbookId: 'workbook-1',
            accountCode: '1100',
            systemKey: 'loans_receivable_regular',
            accountName: 'Loans Receivable - Regular',
            accountType: 'asset',
            normalBalance: 'debit',
            sourceReferenceAmount: 19550,
            sourceBasis: 'regular_operational_reference',
            requirementType: 'calculation_required',
            guidance: 'Calculate EIR carrying amount.',
            proposedDebit: null,
            proposedCredit: null,
            verificationStatus: 'pending',
            evidenceNote: null,
            measurementReferenceAmount: 19723.77,
            measurementStatus: 'measured',
            measurementNote: 'Regular loan component.',
          ),
          OpeningBalanceWorkbookLine(
            workbookId: 'workbook-1',
            accountCode: '1110',
            systemKey: 'loans_receivable_7x7',
            accountName: 'Loans Receivable - 7x7',
            accountType: 'asset',
            normalBalance: 'debit',
            sourceReferenceAmount: 9000,
            sourceBasis: '7x7_principal_reference',
            requirementType: 'calculation_required',
            guidance: 'Calculate EIR carrying amount.',
            proposedDebit: null,
            proposedCredit: null,
            verificationStatus: 'pending',
            evidenceNote: null,
            measurementReferenceAmount: 9000,
            measurementStatus: 'measured',
            measurementNote: '7x7 loan component.',
          ),
          OpeningBalanceWorkbookLine(
            workbookId: 'workbook-1',
            accountCode: '1120',
            systemKey: 'accrued_interest_receivable',
            accountName: 'Accrued Interest Receivable',
            accountType: 'asset',
            normalBalance: 'debit',
            sourceReferenceAmount: null,
            sourceBasis: 'accounting_schedule_required',
            requirementType: 'calculation_required',
            guidance: 'Use measured EIR interest component.',
            proposedDebit: null,
            proposedCredit: null,
            verificationStatus: 'pending',
            evidenceNote: null,
            measurementReferenceAmount: 619.36,
            measurementStatus: 'measured',
            measurementNote: 'Accrued EIR component.',
          ),
        ],
        measurement: AccountingMeasurementData(
          notice: 'Stage 5D measurements are references only and do not post.',
          summary: const AccountingMeasurementSummary(
            activeLoanCount: 7,
            measuredLoanCount: 7,
            reviewRequiredCount: 0,
            actualCashReceived: 450,
            effectiveInterestIncome: 793.11,
            regularLoanComponent: 19723.77,
            sevenBySevenLoanComponent: 9000,
            accruedInterestComponent: 619.36,
            grossCarryingAmount: 29343.11,
            measurementStatus: 'measured',
            measurementPolicyVersion: 'eir_cutover_v1',
            eclIncluded: false,
            readyToPost: false,
          ),
          loans: <LoanAccountingMeasurement>[
            LoanAccountingMeasurement(
              loanId: 'loan-1',
              loanNumber: 'TEST-REG-20260802',
              clientName: 'TEST CLIENT REGULAR',
              calculationMode: 'fixed_daily',
              policyVersion: 'regular_fixed_20_v1',
              dateReleased: DateTime(2026, 8, 1),
              dueDate: DateTime(2026, 11, 29),
              cutoverDate: DateTime(2026, 8, 8),
              daysElapsed: 7,
              principal: 5000,
              operationalBalance: 4900,
              dailyEir: 0.003114181946,
              dailyEirPercent: 0.31141819,
              contractualCashDue: 350,
              actualCashReceived: 100,
              effectiveInterestIncome: 108.77,
              loanComponent: 4965.57,
              accruedInterestComponent: 43.20,
              grossCarryingAmount: 5008.77,
              contractualUnpaidInterest: null,
              measurementStatus: 'measured',
              measurementNote: 'Regular EIR cutover measurement.',
            ),
          ],
        ),
      );

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