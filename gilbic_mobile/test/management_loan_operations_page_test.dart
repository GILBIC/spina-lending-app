import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_operations.dart';
import 'package:gilbic_mobile/src/core/management/management_operations_repository.dart';
import 'package:gilbic_mobile/src/features/management/management_loan_operations_page.dart';

void main() {
  testWidgets('Management sees read-only collection operations and filters', (
    tester,
  ) async {
    final repository = _FakeOperationsRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementLoanOperationsPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Loan Operations'), findsOneWidget);
    expect(find.text('Latest collections'), findsOneWidget);
    expect(find.text('Unremitted cash'), findsOneWidget);
    expect(find.text('Corrections / voids'), findsOneWidget);

    final search = find.byKey(const Key('management-operations-search'));
    await tester.scrollUntilVisible(
      search,
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    await tester.enterText(search, 'GBC-20260806-00000010');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();

    expect(repository.query, 'GBC-20260806-00000010');
    expect(repository.status, 'all');
    expect(repository.deviceId, 'management-device');

    final entryFinder = find.byKey(const Key('management-operation-tx-1'));
    await tester.scrollUntilVisible(
      entryFinder,
      500,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    expect(find.text('TEST CLIENT REGULAR'), findsOneWidget);
    expect(find.text('Received'), findsOneWidget);

    await tester.tap(entryFinder);
    await tester.pumpAndSettle();
    expect(find.text('GBC-20260806-00000010'), findsWidgets);
    expect(find.text('₱4,900.00'), findsOneWidget);
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

class _FakeOperationsRepository implements ManagementOperationsRepository {
  String? deviceId;
  String? query;
  String? status;

  @override
  Future<ManagementOperationsOverview> loadOverview(
    UserSession session, {
    required String deviceId,
    required String query,
    required String status,
  }) async {
    this.deviceId = deviceId;
    this.query = query;
    this.status = status;
    return ManagementOperationsOverview(
      notice: 'Loan Operations is a read-only monitoring view.',
      summary: ManagementOperationsSummary(
        latestCollectionDate: DateTime(2026, 8, 6),
        latestDayAmount: 50,
        latestDayPaymentCount: 1,
        latestDayUnableToPayCount: 0,
        unremittedAmount: 0,
        unremittedEntryCount: 0,
        pendingRemittanceAmount: 0,
        pendingRemittanceCount: 0,
        receivedRemittanceAmount: 50,
        receivedRemittanceCount: 1,
        correctionCount: 0,
        voidCount: 1,
      ),
      entries: <ManagementOperationEntry>[
        ManagementOperationEntry(
          transactionId: 'tx-1',
          receiptNumber: 'GBC-20260806-00000010',
          collectionDate: DateTime(2026, 8, 6),
          acceptedAt: DateTime.utc(2026, 8, 6, 3, 3),
          clientCode: 'TEST-REG-001',
          clientName: 'TEST CLIENT REGULAR',
          loanNumber: 'TEST-REG-20260802',
          loanTypeName: 'Regular',
          collectorName: 'Test Collector',
          entryType: 'payment',
          amount: 50,
          officialBalance: 4900,
          coveredDates: <DateTime>[DateTime(2026, 8, 6)],
          editVersion: 0,
          status: 'received',
          remittanceNumber: 'REM-20260805-00000004',
        ),
      ],
      audits: <ManagementOperationAudit>[
        ManagementOperationAudit(
          eventId: 'audit-1',
          eventType: 'void',
          happenedAt: DateTime.utc(2026, 8, 5, 9, 1),
          transactionId: 'tx-void',
          receiptNumber: 'GBC-20260805-00000008',
          clientName: 'TEST CLIENT REGULAR',
          loanNumber: 'TEST-REG-20260802',
          actorName: 'Management',
          reason: 'Payment posted to the wrong borrower',
        ),
      ],
    );
  }
}
