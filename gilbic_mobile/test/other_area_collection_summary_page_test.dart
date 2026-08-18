import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/remittance/cross_remittance.dart';
import 'package:gilbic_mobile/src/core/remittance/cross_remittance_repository.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance.dart';
import 'package:gilbic_mobile/src/features/collector/other_area_collection_summary_page.dart';

void main() {
  testWidgets('shows all three other-area remittance and custody states',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(900, 1800));
    addTearDown(() async => tester.binding.setSurfaceSize(null));

    final repository = _Repository();
    await tester.pumpWidget(
      MaterialApp(
        home: OtherAreaCollectionSummaryPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(repository.loadCount, 1);
    expect(find.text('My Other-Area Collections'), findsOneWidget);
    expect(find.text('Not yet remitted: 1'), findsOneWidget);
    expect(find.text('Awaiting acceptance: 1'), findsOneWidget);
    expect(find.text('Accepted: 1'), findsOneWidget);
    expect(find.text('Collector Two'), findsWidgets);
    expect(find.textContaining('CARDONA › LOOC'), findsOneWidget);
    expect(find.text('GBC-1 • Regular • 2026-08-18'), findsOneWidget);
    expect(find.text('Cash remains under your custody.'), findsOneWidget);
    expect(
      find.text('Cash remains under your custody until Collector Two accepts.'),
      findsOneWidget,
    );
    expect(
      find.text('Cash custody transferred to Management One.'),
      findsOneWidget,
    );
    expect(find.textContaining('Recorded: 2026-08-18 09:00'), findsWidgets);
  });

  testWidgets('status filter isolates awaiting acceptance records',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(900, 1800));
    addTearDown(() async => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        home: OtherAreaCollectionSummaryPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: _Repository(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('other-area-summary-status-filter')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Awaiting acceptance').last);
    await tester.pumpAndSettle();

    expect(find.text('GBC-2 • Regular • 2026-08-18'), findsOneWidget);
    expect(find.text('GBC-1 • Regular • 2026-08-18'), findsNothing);
    expect(find.text('GBC-3 • Regular • 2026-08-18'), findsNothing);
  });
}

const UserSession _session = UserSession(
  userId: 'collector-one',
  username: 'collector.one',
  displayName: 'Collector One',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'collector-token',
  permissions: <String>['remittance.view'],
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
  int loadCount = 0;

  @override
  Future<List<CrossCollectionStatus>> loadCollectionHistory(
    UserSession session, {
    required String deviceId,
    DateTime? collectionDate,
  }) async {
    loadCount += 1;
    expect(deviceId, 'collector-device');
    return <CrossCollectionStatus>[
      _status(
        id: 'tx-1',
        receipt: 'GBC-1',
        custody: CrossCollectionCustodyStatus.notRemitted,
      ),
      _status(
        id: 'tx-2',
        receipt: 'GBC-2',
        custody: CrossCollectionCustodyStatus.awaitingAcceptance,
        remittanceNumber: 'REM-2',
        recipient: 'Collector Two',
        submittedAt: DateTime.parse('2026-08-18T01:10:00Z'),
      ),
      _status(
        id: 'tx-3',
        receipt: 'GBC-3',
        custody: CrossCollectionCustodyStatus.accepted,
        remittanceNumber: 'REM-3',
        recipient: 'Management One',
        submittedAt: DateTime.parse('2026-08-18T01:15:00Z'),
        receivedAt: DateTime.parse('2026-08-18T01:20:00Z'),
      ),
    ];
  }

  @override
  Future<List<CrossRemittanceTarget>> loadTargets(
    UserSession session, {
    required String deviceId,
    required DateTime collectionDate,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<RemittanceSummary> loadPreview(
    UserSession session, {
    required String deviceId,
    required String recipientUserId,
    required DateTime collectionDate,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<RemittanceRecord> submit(
    UserSession session, {
    required String deviceId,
    required String recipientUserId,
    required DateTime collectionDate,
    String note = '',
  }) {
    throw UnimplementedError();
  }
}

CrossCollectionStatus _status({
  required String id,
  required String receipt,
  required CrossCollectionCustodyStatus custody,
  String remittanceNumber = '',
  String recipient = '',
  DateTime? submittedAt,
  DateTime? receivedAt,
}) {
  return CrossCollectionStatus(
    transactionId: id,
    receiptNumber: receipt,
    clientId: 'client-$id',
    clientName: 'Client $id',
    loanId: 'loan-$id',
    loanType: 'Regular',
    area: 'CARDONA › LOOC',
    assignedCollectorUserId: 'collector-two',
    assignedCollectorName: 'Collector Two',
    collectionDate: DateTime(2026, 8, 18),
    entryType: 'payment',
    amount: 50,
    acceptedAt: DateTime.parse('2026-08-18T01:00:00Z'),
    isLocked: custody != CrossCollectionCustodyStatus.notRemitted,
    remittanceId: remittanceNumber.isEmpty ? null : 'rem-$id',
    remittanceNumber: remittanceNumber,
    custodyStatus: custody,
    remittanceRecipientUserId: recipient.isEmpty ? null : 'recipient-$id',
    remittanceRecipientName: recipient,
    submittedAt: submittedAt,
    receivedAt: receivedAt,
  );
}
