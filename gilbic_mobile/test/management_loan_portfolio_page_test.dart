import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_loan.dart';
import 'package:gilbic_mobile/src/core/management/management_loan_repository.dart';
import 'package:gilbic_mobile/src/features/management/management_loan_portfolio_page.dart';

void main() {
  testWidgets('Management sees read-only portfolio and can search', (tester) async {
    final repository = _FakeManagementLoanRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementLoanPortfolioPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Loan Management'), findsOneWidget);
    expect(find.text('Active loans'), findsOneWidget);
    expect(find.text('Outstanding'), findsOneWidget);
    expect(find.text('Approved renewals'), findsOneWidget);

    await tester.enterText(
      find.byKey(const Key('management-loan-search')),
      'TEST-REG-001',
    );
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();

    expect(repository.query, 'TEST-REG-001');
    expect(repository.status, 'active');
    expect(repository.deviceId, 'management-device');

    await tester.scrollUntilVisible(
      find.byKey(const Key('management-loan-loan-1')),
      500,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();

    expect(find.text('TEST CLIENT REGULAR'), findsOneWidget);
    expect(
      find.text('Renewal approved and awaiting SPINA office processing.'),
      findsOneWidget,
    );
    expect(find.text('Official remaining balance'), findsOneWidget);
    expect(find.text('₱4,900.00'), findsWidgets);
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

class _FakeManagementLoanRepository implements ManagementLoanRepository {
  String? deviceId;
  String? query;
  String? status;

  @override
  Future<ManagementLoanPortfolio> loadPortfolio(
    UserSession session, {
    required String deviceId,
    required String query,
    required String status,
  }) async {
    this.deviceId = deviceId;
    this.query = query;
    this.status = status;
    return ManagementLoanPortfolio(
      summary: const ManagementLoanSummary(
        activeLoanCount: 2,
        activeClientCount: 1,
        activePrincipalTotal: 8000,
        activeRemainingTotal: 7900,
        overdueActiveCount: 0,
        activeSevenBySevenCount: 1,
        approvedRenewalCount: 1,
      ),
      notice: 'Loan Management is view-only in mobile.',
      loans: <ManagementLoanItem>[
        ManagementLoanItem(
          loanId: 'loan-1',
          loanNumber: 'TEST-REG-20260802',
          clientId: 'client-1',
          clientCode: 'TEST-REG-001',
          clientName: 'TEST CLIENT REGULAR',
          clientArea: 'GILBIC TEST AREA',
          clientStatus: 'active',
          loanTypeCode: 'REG',
          loanTypeName: 'Regular',
          calculationMode: 'fixed_daily',
          principal: 5000,
          dailyAmount: 50,
          interestRate: 20,
          remainingBalance: 4900,
          paidAmount: 100,
          paidPercent: 2,
          dateReleased: DateTime(2026, 8, 1),
          dueDate: DateTime(2026, 11, 29),
          loanStatus: 'active',
          lastPaymentDate: DateTime(2026, 8, 6),
          advanceUntil: DateTime(2026, 8, 5),
          passCount: 0,
          paymentCount: 2,
          stateVersion: 3,
          renewalRequestStatus: 'approved',
          isOverdue: false,
        ),
      ],
    );
  }
}
