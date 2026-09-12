import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/loans/client_schedule.dart';
import 'package:gilbic_mobile/src/core/loans/client_schedule_repository.dart';
import 'package:gilbic_mobile/src/features/client/client_schedule_page.dart';

void main() {
  testWidgets('Client schedule page renders authoritative server values only',
      (tester) async {
    final repository = _FakeClientScheduleRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ClientSchedulePage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          loanId: 'regular-loan',
          loanNumber: 'TEST-REG-20260802',
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Payment schedule'), findsOneWidget);
    expect(find.textContaining('Authoritative SPINA schedule'), findsOneWidget);
    expect(find.text('Regular'), findsOneWidget);
    expect(find.text('₱200.00'), findsWidgets);
    expect(find.text('₱150.00'), findsOneWidget);
    expect(find.text('Due Today'), findsOneWidget);
    expect(find.text('Oct 10, 2026'), findsOneWidget);
    expect(find.text('Oct 12, 2026'), findsOneWidget);
    expect(find.text('Management-approved extension'), findsOneWidget);
    expect(repository.loanId, 'regular-loan');
    expect(repository.deviceId, 'client-device');
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

class _FakeClientScheduleRepository implements ClientScheduleRepository {
  String? loanId;
  String? deviceId;

  @override
  Future<ClientLoanSchedule> loadSchedule(
    UserSession session, {
    required String deviceId,
    required String loanId,
  }) async {
    this.loanId = loanId;
    this.deviceId = deviceId;
    return ClientLoanSchedule(
      loanId: loanId,
      loanNumber: 'TEST-REG-20260802',
      loanType: 'Regular',
      calculationMode: 'fixed_total',
      isSevenBySeven: false,
      paymentFrequency: 'daily',
      readOnly: true,
      pastDueAmount: 200,
      pastDueCount: 1,
      scheduleExtensionSlots: 2,
      contractualMaturity: DateTime(2026, 10, 10),
      operationalMaturity: DateTime(2026, 10, 12),
      maturityStatus: 'extended',
      rows: <ClientScheduleRow>[
        ClientScheduleRow(
          paymentDate: DateTime(2026, 9, 12),
          amount: 200,
          status: 'Due Today',
          remainingAmount: 150,
          note: 'Management-approved extension',
        ),
      ],
    );
  }
}
