import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/collection_void.dart';
import 'package:gilbic_mobile/src/core/management/collection_void_repository.dart';
import 'package:gilbic_mobile/src/features/management/management_collection_void_page.dart';

void main() {
  testWidgets('Management can review and void an unlocked wrong payment',
      (tester) async {
    final repository = _FakeCollectionVoidRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementCollectionVoidPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Void Incorrect Payment'), findsOneWidget);
    expect(
      find.text('Management-only audited correction'),
      findsOneWidget,
    );

    await tester.enterText(
      find.byKey(const Key('management-void-receipt')),
      'GBC-20260805-00000008',
    );
    await tester.tap(find.byKey(const Key('management-void-search')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('management-void-candidate')), findsOneWidget);
    expect(find.text('TEST CLIENT REGULAR'), findsOneWidget);
    expect(find.text('Amount: ₱50.00'), findsOneWidget);
    expect(find.text('Balance before entry: ₱4950.00'), findsOneWidget);
    expect(find.text('Balance after entry: ₱4900.00'), findsOneWidget);

    await tester.scrollUntilVisible(
      find.byKey(const Key('management-void-reason')),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.enterText(
      find.byKey(const Key('management-void-reason')),
      'Payment posted to the wrong borrower',
    );
    await tester.scrollUntilVisible(
      find.byKey(const Key('submit-management-collection-void')),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(
      find.byKey(const Key('submit-management-collection-void')),
    );
    await tester.pumpAndSettle();

    expect(find.text('Void this collection?'), findsOneWidget);
    expect(find.textContaining('The original record'), findsOneWidget);

    await tester.tap(
      find.byKey(const Key('confirm-management-collection-void')),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('management-void-success')), findsOneWidget);
    expect(find.text('Collection voided'), findsOneWidget);
    expect(find.text('Restored balance: ₱4950.00'), findsOneWidget);
    expect(repository.receiptNumber, 'GBC-20260805-00000008');
    expect(repository.transactionId, 'transaction-8');
    expect(repository.reason, 'Payment posted to the wrong borrower');
    expect(repository.deviceId, 'management-device');
  });
}

const UserSession _session = UserSession(
  userId: 'management-1',
  username: 'management.one',
  displayName: 'Management One',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>['collection.void.unremitted'],
);

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'management-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

class _FakeCollectionVoidRepository
    implements ManagementCollectionVoidRepository {
  String? receiptNumber;
  String? transactionId;
  String? reason;
  String? deviceId;

  @override
  Future<ManagementCollectionVoidCandidate> findByReceipt(
    UserSession session, {
    required String deviceId,
    required String receiptNumber,
  }) async {
    this.deviceId = deviceId;
    this.receiptNumber = receiptNumber;
    return ManagementCollectionVoidCandidate(
      transactionId: 'transaction-8',
      receiptNumber: receiptNumber,
      clientCode: 'TEST-REG-001',
      clientName: 'TEST CLIENT REGULAR',
      loanType: 'Regular',
      collectorName: 'Test Collector',
      collectionDate: DateTime(2026, 8, 5),
      entryType: 'advance',
      amount: 50,
      coveredDates: const <String>['2026-08-06'],
      previousBalance: 4950,
      officialBalance: 4900,
    );
  }

  @override
  Future<ManagementCollectionVoidResult> voidCollection(
    UserSession session, {
    required String deviceId,
    required String transactionId,
    required String reason,
  }) async {
    this.deviceId = deviceId;
    this.transactionId = transactionId;
    this.reason = reason;
    return ManagementCollectionVoidResult(
      transactionId: transactionId,
      receiptNumber: receiptNumber!,
      clientName: 'TEST CLIENT REGULAR',
      restoredBalance: 4950,
      stateVersion: 3,
      reason: reason,
      voidedAt: DateTime.utc(2026, 8, 5, 7, 40),
    );
  }
}
