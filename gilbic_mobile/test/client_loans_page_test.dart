import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan_repository.dart';
import 'package:gilbic_mobile/src/core/loans/client_schedule.dart';
import 'package:gilbic_mobile/src/core/loans/client_schedule_repository.dart';
import 'package:gilbic_mobile/src/features/client/client_loans_page.dart';

void main() {
  testWidgets('linked client can view regular and 7x7 loan balances',
      (tester) async {
    final repository = _FakeClientLoanRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ClientLoansPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('My Loans'), findsOneWidget);
    expect(find.text('TEST CLIENT REGULAR'), findsOneWidget);
    expect(find.text('TEST-REG-001 • TEST AREA'), findsOneWidget);
    expect(find.text('Active loans'), findsOneWidget);
    expect(find.text('Regular'), findsOneWidget);
    expect(find.textContaining('Remaining: ₱4,950.00'), findsOneWidget);
    expect(find.text('Official remaining balance'), findsWidgets);
    expect(find.text('₱4,950.00'), findsWidgets);
    expect(find.byType(LinearProgressIndicator), findsNothing);
    expect(find.textContaining('% paid'), findsNothing);

    await tester.scrollUntilVisible(
      find.byKey(const Key('client-loan-seven-by-seven-loan')),
      400,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();

    expect(find.text('7x7'), findsOneWidget);
    expect(
      find.textContaining('7x7 mobile collection remains disabled'),
      findsOneWidget,
    );
    expect(repository.deviceId, 'client-device');
    expect(repository.userId, 'client-1');
  });

  testWidgets('My Loans opens the authoritative server schedule for a loan',
      (tester) async {
    final loans = _FakeClientLoanRepository();
    final schedules = _FakeClientScheduleRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ClientLoansPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: loans,
          scheduleRepository: schedules,
        ),
      ),
    );
    await tester.pumpAndSettle();

    final button = find.byKey(const Key('client-loan-schedule-regular-loan'));
    await tester.ensureVisible(button);
    await tester.pumpAndSettle();
    await tester.tap(button);
    await tester.pumpAndSettle();

    expect(find.text('Payment schedule'), findsOneWidget);
    expect(find.text('Authoritative SPINA schedule'), findsOneWidget);
    expect(schedules.loanId, 'regular-loan');
    expect(schedules.deviceId, 'client-device');
  });
}

const UserSession _session = UserSession(
  userId: 'client-1',
  username: 'testregular1',
  displayName: 'TEST CLIENT REGULAR',
  role: AppRole.client,
  rawRole: 'Client',
  accessToken: 'client-token',
  permissions: <String>[],
);

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'client-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

class _FakeClientLoanRepository implements ClientLoanRepository {
  String? deviceId;
  String? userId;

  @override
  Future<ClientLoanPortfolio> loadPortfolio(
    UserSession session, {
    required String deviceId,
  }) async {
    this.deviceId = deviceId;
    userId = session.userId;
    return ClientLoanPortfolio(
      clientId: 'client-record-1',
      clientCode: 'TEST-REG-001',
      clientName: 'TEST CLIENT REGULAR',
      area: 'TEST AREA',
      clientStatus: 'active',
      loans: <ClientLoan>[
        ClientLoan(
          loanId: 'regular-loan',
          loanNumber: 'TEST-REG-20260802',
          loanTypeCode: 'regular_mobile_test',
          loanTypeName: 'Regular',
          principal: 5000,
          dailyAmount: 50,
          interestRate: 20,
          dateReleased: DateTime(2026, 8, 1),
          dueDate: DateTime(2026, 11, 29),
          status: 'active',
          remainingBalance: 4950,
          paidAmount: 50,
          passCount: 0,
          lastPaymentDate: DateTime(2026, 8, 2),
          advanceUntil: DateTime(2026, 8, 5),
          stateVersion: 3,
          paymentCount: 1,
        ),
        ClientLoan(
          loanId: 'seven-by-seven-loan',
          loanNumber: 'TEST-REG-7X7-20260802',
          loanTypeCode: 'seven_by_seven_mobile_test',
          loanTypeName: '7x7',
          principal: 3000,
          dailyAmount: 21,
          status: 'active',
          remainingBalance: 3000,
          paidAmount: 0,
          passCount: 0,
          stateVersion: 0,
          paymentCount: 0,
        ),
      ],
    );
  }
}

class _FakeClientScheduleRepository implements ClientScheduleRepository {
  String? deviceId;
  String? loanId;

  @override
  Future<ClientLoanSchedule> loadSchedule(
    UserSession session, {
    required String deviceId,
    required String loanId,
  }) async {
    this.deviceId = deviceId;
    this.loanId = loanId;
    return ClientLoanSchedule(
      loanId: loanId,
      loanNumber: 'TEST-REG-20260802',
      loanType: 'Regular',
      calculationMode: 'fixed_total',
      isSevenBySeven: false,
      paymentFrequency: 'daily',
      readOnly: true,
      pastDueAmount: '0.00',
      pastDueCount: 0,
      scheduleExtensionSlots: 0,
      contractualMaturity: DateTime(2026, 11, 29),
      operationalMaturity: DateTime(2026, 11, 29),
      maturityStatus: 'current',
      rows: const <ClientScheduleRow>[],
    );
  }
}
