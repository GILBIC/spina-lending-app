import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/financial_accounting.dart';
import 'package:gilbic_mobile/src/core/management/financial_accounting_repository.dart';
import 'package:gilbic_mobile/src/features/management/management_financial_accounting_page.dart';

void main() {
  testWidgets('Management sees read-only accounting controls and loan policies', (
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
    expect(find.text('Not started'), findsOneWidget);
    expect(find.text('Unavailable'), findsOneWidget);

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
  String? deviceId;

  @override
  Future<FinancialAccountingOverview> loadOverview(
    UserSession session, {
    required String deviceId,
  }) async {
    this.deviceId = deviceId;
    return const FinancialAccountingOverview(
      notice: 'Financial Accounting is currently a read-only control center.',
      journalStatus: 'not_started',
      trialBalanceStatus: 'unavailable',
      summary: FinancialAccountingSummary(
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
      policies: <LoanAccountingPolicy>[
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
}
