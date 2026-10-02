import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan_repository.dart';
import 'package:gilbic_mobile/src/core/loans/client_schedule.dart';
import 'package:gilbic_mobile/src/core/loans/client_schedule_repository.dart';

UserSession clientSession() => UserSession(
  userId: 'client-1',
  username: 'ana.client',
  displayName: 'Ana',
  role: AppRole.client,
  rawRole: 'Client',
  accessToken: 'client-token',
  permissions: <String>['loan.self.view'],
);

DeviceIdentityProvider clientIdentity() {
  final store = MemoryDeviceIdentityStore()..value = 'client-home-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

ClientLoanPortfolio clientPortfolio() => ClientLoanPortfolio(
  clientId: 'client-record-1',
  clientCode: 'CLIENT-001',
  clientName: 'Ana Client',
  area: 'Area 1',
  clientStatus: 'active',
  loans: <ClientLoan>[
    regularLoan(),
    const ClientLoan(
      loanId: 'seven-by-seven-loan',
      loanNumber: '7X7-001',
      loanTypeCode: 'seven_by_seven',
      loanTypeName: '7x7',
      principal: '3000.00',
      dailyAmount: '21.00',
      status: 'active',
      remainingBalance: '3000.00',
      paidAmount: '0.00',
      passCount: 0,
      stateVersion: 0,
      paymentCount: 0,
    ),
  ],
);

ClientLoan regularLoan({
  String status = 'active',
  String remainingBalance = '4950.00',
}) {
  return ClientLoan(
    loanId: 'regular-loan',
    loanNumber: 'REG-001',
    loanTypeCode: 'regular',
    loanTypeName: 'Regular',
    principal: '5000.00',
    dailyAmount: '50.00',
    dateReleased: DateTime(2026, 8, 1),
    dueDate: DateTime(2026, 11, 29),
    status: status,
    remainingBalance: remainingBalance,
    paidAmount: '50.00',
    passCount: 0,
    lastPaymentDate: DateTime(2026, 8, 2),
    stateVersion: 3,
    paymentCount: 1,
  );
}

class FakeClientLoanRepository implements ClientLoanRepository {
  FakeClientLoanRepository(this.portfolio) : failure = null;

  FakeClientLoanRepository.failure(this.failure) : portfolio = null;

  final ClientLoanPortfolio? portfolio;
  final Object? failure;
  String? deviceId;
  String? userId;

  @override
  Future<ClientLoanPortfolio> loadPortfolio(
    UserSession session, {
    required String deviceId,
  }) async {
    this.deviceId = deviceId;
    userId = session.userId;
    if (failure != null) throw failure!;
    return portfolio!;
  }
}

class FakeClientScheduleRepository implements ClientScheduleRepository {
  FakeClientScheduleRepository({
    this.penaltyStatus = 'not_applicable',
    this.payoff = '0.00',
    this.reviewReason = '',
  });
  final String penaltyStatus;
  final String payoff;
  final String reviewReason;
  @override
  Future<ClientLoanSchedule> loadSchedule(
    UserSession session, {
    required String deviceId,
    required String loanId,
  }) async {
    return ClientLoanSchedule(
      loanId: loanId,
      loanNumber: '7X7-001',
      loanType: '7x7',
      calculationMode: 'seven_by_seven',
      isSevenBySeven: true,
      paymentFrequency: 'daily',
      readOnly: true,
      pastDueAmount: '0.00',
      pastDueCount: 0,
      scheduleExtensionSlots: 0,
      maturityStatus: 'scheduled',
      penaltyStatus: penaltyStatus,
      projectedPenalty: '0.00',
      assessedPenaltyBalance: '0.00',
      penaltyBase: '0.00',
      remainingCostHeadroom: '0.00',
      exactPayoffTotal: payoff,
      managementReviewRequiredReason: reviewReason,
      rows: const <ClientScheduleRow>[],
    );
  }
}
