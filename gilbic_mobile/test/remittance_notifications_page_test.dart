import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification_repository.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance_repository.dart';
import 'package:gilbic_mobile/src/features/notifications/remittance_notifications_page.dart';

void main() {
  testWidgets('recipient opens full payment list and acknowledges review before acceptance',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(800, 1600));
    addTearDown(() async => tester.binding.setSurfaceSize(null));

    final notifications = _NotificationRepository();
    final remittances = _HistoryRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: RemittanceNotificationsPage(
          session: _recipientSession,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: notifications,
          remittanceRepository: remittances,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Remittance requests (1)'), findsOneWidget);
    expect(find.byTooltip('Refresh remittance requests'), findsOneWidget);
    expect(find.textContaining('Collector One'), findsOneWidget);
    expect(find.textContaining('₱600.00'), findsOneWidget);
    expect(find.textContaining('Action required'), findsOneWidget);

    await tester.tap(find.byKey(const Key('notification-notification-1')));
    await tester.pumpAndSettle();
    expect(notifications.markReadCount, 1);
    expect(find.textContaining('Review every payment'), findsOneWidget);

    final reviewButton = find.byKey(
      const Key('review-remittance-notification-notification-1'),
    );
    await tester.ensureVisible(reviewButton);
    await tester.tap(reviewButton);
    await tester.pumpAndSettle();

    expect(find.text('Review Remittance'), findsOneWidget);
    expect(find.text('Full payment list'), findsOneWidget);
    expect(find.text('Client A'), findsOneWidget);
    expect(find.text('Client B'), findsOneWidget);

    final acceptButton = find.byKey(
      const Key('receive-remittance-remittance-1'),
    );
    expect(
      tester.widget<FilledButton>(acceptButton).onPressed,
      isNull,
    );

    await tester.tap(
      find.byKey(const Key('review-remittance-remittance-1')),
    );
    await tester.pumpAndSettle();
    expect(
      tester.widget<FilledButton>(acceptButton).onPressed,
      isNotNull,
    );

    await tester.tap(acceptButton);
    await tester.pumpAndSettle();
    expect(find.text('Confirm cash received?'), findsOneWidget);
    expect(find.textContaining('reviewed all 2 payment records'), findsOneWidget);

    await tester.tap(
      find.byKey(const Key('confirm-remittance-remittance-1')),
    );
    await tester.pumpAndSettle();

    expect(remittances.confirmCount, 1);
    expect(find.textContaining('Accepted'), findsWidgets);
    expect(find.textContaining('permanent and read-only'), findsOneWidget);
  });
}

const UserSession _recipientSession = UserSession(
  userId: 'office-one',
  username: 'office.one',
  displayName: 'Office Staff',
  role: AppRole.employee,
  rawRole: 'Employee',
  accessToken: 'office-token',
  permissions: <String>['remittance.view', 'remittance.receive'],
);

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'android-release-candidate';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0-rc',
  );
}

RemittanceNotification _pending({DateTime? readAt}) {
  return RemittanceNotification(
    notificationId: 'notification-1',
    remittanceId: 'remittance-1',
    remittanceNumber: 'REM-RC-1',
    title: 'Remittance awaiting acceptance',
    message: 'Collector One submitted route cash for acceptance.',
    status: 'pending',
    collectorName: 'Collector One',
    totalAmount: 600,
    clientCount: 2,
    transactionCount: 2,
    collectionDate: DateTime(2026, 8, 15),
    createdAt: DateTime.utc(2026, 8, 15, 1),
    readAt: readAt,
    custodyMessage:
        'Review every payment, then confirm only after physical cash is received.',
  );
}

RemittanceRecord _record({String status = 'submitted'}) {
  return RemittanceRecord(
    remittanceId: 'remittance-1',
    remittanceNumber: 'REM-RC-1',
    collectorUserId: 'collector-one',
    collectorName: 'Collector One',
    recipientUserId: 'office-one',
    recipientName: 'Office Staff',
    status: status,
    summary: RemittanceSummary(
      collectionDate: DateTime(2026, 8, 15),
      collectorName: 'Collector One',
      transactionCount: 2,
      paymentCount: 2,
      unableToPayCount: 0,
      coveredPaymentCount: 2,
      clientCount: 2,
      totalAmount: 600,
      items: <RemittanceItem>[
        RemittanceItem(
          transactionId: 'tx-1',
          clientName: 'Client A',
          loanType: 'Regular',
          entryType: 'payment',
          amount: 250,
          receiptNumber: 'GBC-1',
          coveredDates: <DateTime>[DateTime(2026, 8, 15)],
          note: '',
        ),
        RemittanceItem(
          transactionId: 'tx-2',
          clientName: 'Client B',
          loanType: 'Regular',
          entryType: 'advance',
          amount: 350,
          receiptNumber: 'GBC-2',
          coveredDates: <DateTime>[
            DateTime(2026, 8, 15),
            DateTime(2026, 8, 16),
          ],
          note: '',
        ),
      ],
    ),
    note: 'Other-area handover',
    submittedAt: DateTime.utc(2026, 8, 15, 1),
    receivedAt: status == 'received' ? DateTime.utc(2026, 8, 15, 2) : null,
    reviewedAt: status == 'received' ? DateTime.utc(2026, 8, 15, 2) : null,
    reviewedByUserId: status == 'received' ? 'office-one' : '',
  );
}

class _NotificationRepository implements RemittanceNotificationRepository {
  int markReadCount = 0;

  @override
  Future<List<RemittanceNotification>> loadNotifications(
    UserSession session, {
    required String deviceId,
  }) async {
    return <RemittanceNotification>[_pending()];
  }

  @override
  Future<RemittanceNotification> markRead(
    UserSession session, {
    required String deviceId,
    required String notificationId,
  }) async {
    markReadCount += 1;
    return _pending(readAt: DateTime.utc(2026, 8, 15, 1, 30));
  }

  @override
  Future<RemittanceAcceptanceResult> acceptRemittance(
    UserSession session, {
    required String deviceId,
    required String notificationId,
  }) {
    throw StateError('Notification page must not accept without full review.');
  }
}

class _HistoryRepository implements RemittanceRepository {
  int confirmCount = 0;
  RemittanceRecord current = _record();

  @override
  Future<List<RemittanceRecord>> loadHistory(
    UserSession session, {
    required String deviceId,
  }) async => <RemittanceRecord>[current];

  @override
  Future<RemittanceRecord> confirmReceived(
    UserSession session, {
    required String deviceId,
    required String remittanceId,
  }) async {
    confirmCount += 1;
    current = _record(status: 'received');
    return current;
  }

  @override
  Future<List<RemittanceRecipient>> loadRecipients(
    UserSession session, {
    required String deviceId,
  }) {
    throw StateError('Unexpected recipient load.');
  }

  @override
  Future<RemittanceSummary> loadPreview(
    UserSession session, {
    required String deviceId,
    required DateTime collectionDate,
  }) {
    throw StateError('Unexpected preview load.');
  }

  @override
  Future<RemittanceRecord> submit(
    UserSession session, {
    required String deviceId,
    required String recipientUserId,
    required DateTime collectionDate,
    String note = '',
  }) {
    throw StateError('Unexpected submit.');
  }
}
