import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/remittance/cross_remittance.dart';
import 'package:gilbic_mobile/src/core/remittance/cross_remittance_repository.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance.dart';
import 'package:gilbic_mobile/src/features/collector/cross_collector_remittance_page.dart';

void main() {
  testWidgets('keeps Management distinct from assigned Collector for dual-role user',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(900, 1800));
    addTearDown(() async => tester.binding.setSurfaceSize(null));

    final repository = _Repository();
    await tester.pumpWidget(
      MaterialApp(
        home: CrossCollectorRemittancePage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
          collectionDate: DateTime(2026, 8, 19),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Other-Area Remittance'), findsOneWidget);
    expect(repository.previewCapacity,
        CrossRemittanceRecipientCapacity.assignedCollector);

    await tester.tap(find.byKey(const Key('cross-remittance-recipient')));
    await tester.pumpAndSettle();
    await tester.tap(find.textContaining('Dual Role • Management').last);
    await tester.pumpAndSettle();

    expect(repository.previewRecipientId, 'dual-role-user');
    expect(
      repository.previewCapacity,
      CrossRemittanceRecipientCapacity.management,
    );
    expect(find.text('Cash to Management: ₱100.00'), findsOneWidget);

    await tester.tap(find.byKey(const Key('submit-cross-remittance')));
    await tester.pumpAndSettle();
    expect(find.text('Send to Management?'), findsOneWidget);
    await tester.tap(find.byKey(const Key('confirm-cross-remittance')));
    await tester.pumpAndSettle();

    expect(repository.submitRecipientId, 'dual-role-user');
    expect(
      repository.submitCapacity,
      CrossRemittanceRecipientCapacity.management,
    );
    expect(find.text('Management notified'), findsOneWidget);
    expect(find.text('Management: Dual Role'), findsOneWidget);
  });
}

const UserSession _session = UserSession(
  userId: 'collector-one',
  username: 'collector.one',
  displayName: 'Collector One',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'collector-token',
  permissions: <String>['remittance.create'],
);

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'collector-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0-rc',
  );
}

class _Repository implements CrossRemittanceRepository {
  String? previewRecipientId;
  CrossRemittanceRecipientCapacity? previewCapacity;
  String? submitRecipientId;
  CrossRemittanceRecipientCapacity? submitCapacity;

  @override
  Future<List<CrossCollectionStatus>> loadCollectionHistory(
    UserSession session, {
    required String deviceId,
    DateTime? collectionDate,
  }) async {
    return const <CrossCollectionStatus>[];
  }

  @override
  Future<List<CrossRemittanceTarget>> loadTargets(
    UserSession session, {
    required String deviceId,
    required DateTime collectionDate,
  }) async {
    expect(deviceId, 'collector-device');
    return const <CrossRemittanceTarget>[
      CrossRemittanceTarget(
        recipientUserId: 'dual-role-user',
        recipientName: 'Dual Role',
        recipientCapacity: CrossRemittanceRecipientCapacity.assignedCollector,
        roleName: 'Assigned Collector',
        transactionCount: 1,
        clientCount: 1,
        totalAmount: 100,
      ),
      CrossRemittanceTarget(
        recipientUserId: 'dual-role-user',
        recipientName: 'Dual Role',
        recipientCapacity: CrossRemittanceRecipientCapacity.management,
        roleName: 'Management',
        transactionCount: 1,
        clientCount: 1,
        totalAmount: 100,
      ),
    ];
  }

  @override
  Future<RemittanceSummary> loadPreview(
    UserSession session, {
    required String deviceId,
    required String recipientUserId,
    CrossRemittanceRecipientCapacity recipientCapacity =
        CrossRemittanceRecipientCapacity.assignedCollector,
    required DateTime collectionDate,
  }) async {
    previewRecipientId = recipientUserId;
    previewCapacity = recipientCapacity;
    return _summary();
  }

  @override
  Future<RemittanceRecord> submit(
    UserSession session, {
    required String deviceId,
    required String recipientUserId,
    CrossRemittanceRecipientCapacity recipientCapacity =
        CrossRemittanceRecipientCapacity.assignedCollector,
    required DateTime collectionDate,
    String note = '',
  }) async {
    submitRecipientId = recipientUserId;
    submitCapacity = recipientCapacity;
    final summary = _summary();
    return RemittanceRecord(
      remittanceId: 'rem-one',
      remittanceNumber: 'REM-20260819-00000001',
      collectorUserId: 'collector-one',
      collectorName: 'Collector One',
      recipientUserId: recipientUserId,
      recipientName: 'Dual Role',
      status: 'submitted',
      summary: summary,
      note: note,
      submittedAt: DateTime.parse('2026-08-19T04:00:00Z'),
      receivedAt: null,
    );
  }
}

RemittanceSummary _summary() {
  return RemittanceSummary(
    collectionDate: DateTime(2026, 8, 19),
    collectorName: 'Collector One',
    transactionCount: 1,
    paymentCount: 1,
    unableToPayCount: 0,
    coveredPaymentCount: 1,
    clientCount: 1,
    totalAmount: 100,
    items: <RemittanceItem>[
      RemittanceItem(
        transactionId: 'tx-one',
        clientName: 'Client One',
        loanType: 'Regular',
        entryType: 'payment',
        amount: 100,
        receiptNumber: 'GBC-20260819-00000001',
        coveredDates: <DateTime>[DateTime(2026, 8, 19)],
        note: '',
      ),
    ],
  );
}
