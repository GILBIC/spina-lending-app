import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification_repository.dart';
import 'package:gilbic_mobile/src/features/notifications/remittance_notifications_page.dart';

void main() {
  testWidgets('recipient reviews and accepts remittance only after custody confirmation',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(800, 1400));
    addTearDown(() async => tester.binding.setSurfaceSize(null));

    final repository = _NotificationRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: RemittanceNotificationsPage(
          session: _recipientSession,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Notifications (1)'), findsOneWidget);
    expect(find.textContaining('Collector One'), findsOneWidget);
    expect(find.textContaining('₱600.00'), findsOneWidget);
    expect(find.textContaining('Action required'), findsOneWidget);

    await tester.tap(find.byKey(const Key('notification-notification-1')));
    await tester.pumpAndSettle();
    expect(repository.markReadCount, 1);
    expect(
      find.textContaining('Accept only after physical cash is received'),
      findsOneWidget,
    );

    await tester.tap(
      find.byKey(const Key('open-accept-remittance-notification-1')),
    );
    await tester.pumpAndSettle();
    expect(find.text('Accept Remittance?'), findsOneWidget);
    expect(
      find.textContaining('cash is physically in your possession'),
      findsOneWidget,
    );

    await tester.tap(
      find.byKey(const Key('accept-remittance-notification-1')),
    );
    await tester.pumpAndSettle();

    expect(repository.acceptCount, 1);
    expect(find.text('Remittance Accepted'), findsOneWidget);
    expect(find.textContaining('Money is now under Office Staff custody'), findsOneWidget);
    await tester.tap(find.text('Done'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Accepted — money under your custody'), findsOneWidget);
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
    clientCount: 3,
    transactionCount: 4,
    collectionDate: DateTime(2026, 8, 15),
    createdAt: DateTime.utc(2026, 8, 15, 1),
    readAt: readAt,
    custodyMessage: 'Accept only after physical cash is received.',
  );
}

RemittanceNotification _accepted() {
  return RemittanceNotification(
    notificationId: 'notification-1',
    remittanceId: 'remittance-1',
    remittanceNumber: 'REM-RC-1',
    title: 'Remittance accepted',
    message: 'Office Staff accepted the remittance.',
    status: 'received',
    collectorName: 'Collector One',
    totalAmount: 600,
    clientCount: 3,
    transactionCount: 4,
    collectionDate: DateTime(2026, 8, 15),
    createdAt: DateTime.utc(2026, 8, 15, 1),
    readAt: DateTime.utc(2026, 8, 15, 2),
    acceptedAt: DateTime.utc(2026, 8, 15, 2),
    custodyMessage: 'Money is now under Office Staff custody.',
  );
}

class _NotificationRepository implements RemittanceNotificationRepository {
  int markReadCount = 0;
  int acceptCount = 0;

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
  }) async {
    acceptCount += 1;
    return RemittanceAcceptanceResult(
      notification: _accepted(),
      remittanceId: 'remittance-1',
      remittanceNumber: 'REM-RC-1',
      status: 'received',
      custodyUserId: 'office-one',
      custodyMessage: 'Money is now under Office Staff custody.',
      receivedAt: DateTime.utc(2026, 8, 15, 2),
    );
  }
}