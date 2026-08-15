import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/notifications/activity_notification.dart';
import 'package:gilbic_mobile/src/core/notifications/activity_notification_repository.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification_repository.dart';
import 'package:gilbic_mobile/src/features/notifications/notification_center_page.dart';

void main() {
  testWidgets('Android client sees only recipient-scoped activity updates',
      (tester) async {
    final activity = _ActivityRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: NotificationCenterPage(
          session: _clientSession,
          deviceIdentityProvider: _identity('android'),
          activityRepository: activity,
        ),
      ),
    );

    expect(find.byKey(const Key('notification-center-page')), findsOneWidget);
    expect(find.byKey(const Key('open-activity-notifications')), findsOneWidget);
    expect(find.byKey(const Key('open-remittance-notifications')), findsNothing);

    await tester.tap(find.byKey(const Key('open-activity-notifications')));
    await tester.pumpAndSettle();

    expect(find.text('Payment posted'), findsOneWidget);
    expect(find.textContaining('Receipt R-1001'), findsOneWidget);
    expect(activity.lastDeviceId, 'android-installation');
  });

  testWidgets('iOS remittance viewer stays view-only without receive permission',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(800, 1400));
    addTearDown(() async => tester.binding.setSurfaceSize(null));

    final remittance = _RemittanceRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: NotificationCenterPage(
          session: _employeeViewerSession,
          deviceIdentityProvider: _identity('ios'),
          activityRepository: _ActivityRepository(),
          remittanceRepository: remittance,
        ),
      ),
    );

    expect(find.byKey(const Key('open-activity-notifications')), findsOneWidget);
    expect(find.byKey(const Key('open-remittance-notifications')), findsOneWidget);
    expect(
      find.textContaining('do not allow custody acceptance'),
      findsOneWidget,
    );

    await tester.tap(find.byKey(const Key('open-remittance-notifications')));
    await tester.pumpAndSettle();
    expect(remittance.lastDeviceId, 'ios-installation');

    await tester.tap(find.byKey(const Key('notification-remittance-note-1')));
    await tester.pumpAndSettle();

    expect(
      find.textContaining('View only — your current server permissions'),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('open-accept-remittance-remittance-note-1')),
      findsNothing,
    );
    expect(remittance.acceptCount, 0);
  });
}

const _clientSession = UserSession(
  userId: 'client-1',
  username: 'client.one',
  displayName: 'Client One',
  role: AppRole.client,
  rawRole: 'Client',
  accessToken: 'client-token',
  permissions: <String>['loan.self.view'],
);

const _employeeViewerSession = UserSession(
  userId: 'employee-1',
  username: 'employee.one',
  displayName: 'Employee One',
  role: AppRole.employee,
  rawRole: 'Employee',
  accessToken: 'employee-token',
  permissions: <String>['employee.portal.view', 'remittance.view'],
);

DeviceIdentityProvider _identity(String platform) {
  final store = MemoryDeviceIdentityStore()..value = '$platform-installation';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => platform,
    appVersionResolver: () async => '1.0.0',
  );
}

class _ActivityRepository implements ActivityNotificationRepository {
  String? lastDeviceId;

  @override
  Future<List<ActivityNotification>> load(
    UserSession session, {
    required String deviceId,
  }) async {
    lastDeviceId = deviceId;
    return <ActivityNotification>[
      ActivityNotification(
        id: 'activity-1',
        type: 'payment_posted',
        title: 'Payment posted',
        message: 'Receipt R-1001 was posted to your account.',
        senderName: 'SPINA',
        metadata: const <String, dynamic>{
          'receipt_number': 'R-1001',
          'amount': '200.00',
        },
        isRead: false,
        createdAt: DateTime.utc(2026, 8, 15, 8),
      ),
    ];
  }

  @override
  Future<ActivityNotification> markRead(
    UserSession session, {
    required String deviceId,
    required String notificationId,
  }) async {
    return ActivityNotification(
      id: 'activity-1',
      type: 'payment_posted',
      title: 'Payment posted',
      message: 'Receipt R-1001 was posted to your account.',
      senderName: 'SPINA',
      metadata: const <String, dynamic>{
        'receipt_number': 'R-1001',
        'amount': '200.00',
      },
      isRead: true,
      createdAt: DateTime.utc(2026, 8, 15, 8),
      readAt: DateTime.utc(2026, 8, 15, 8, 1),
    );
  }
}

class _RemittanceRepository implements RemittanceNotificationRepository {
  String? lastDeviceId;
  int acceptCount = 0;

  RemittanceNotification get _pending => RemittanceNotification(
        notificationId: 'remittance-note-1',
        remittanceId: 'remittance-1',
        remittanceNumber: 'REM-1',
        title: 'Remittance awaiting acceptance',
        message: 'Collector One submitted cash for custody review.',
        status: 'pending',
        collectorName: 'Collector One',
        totalAmount: 600,
        clientCount: 3,
        transactionCount: 4,
        collectionDate: DateTime(2026, 8, 15),
        createdAt: DateTime.utc(2026, 8, 15, 8),
        custodyMessage: 'Accept only after physical cash is received.',
      );

  @override
  Future<List<RemittanceNotification>> loadNotifications(
    UserSession session, {
    required String deviceId,
  }) async {
    lastDeviceId = deviceId;
    return <RemittanceNotification>[_pending];
  }

  @override
  Future<RemittanceNotification> markRead(
    UserSession session, {
    required String deviceId,
    required String notificationId,
  }) async {
    return RemittanceNotification(
      notificationId: _pending.notificationId,
      remittanceId: _pending.remittanceId,
      remittanceNumber: _pending.remittanceNumber,
      title: _pending.title,
      message: _pending.message,
      status: _pending.status,
      collectorName: _pending.collectorName,
      totalAmount: _pending.totalAmount,
      clientCount: _pending.clientCount,
      transactionCount: _pending.transactionCount,
      collectionDate: _pending.collectionDate,
      createdAt: _pending.createdAt,
      readAt: DateTime.utc(2026, 8, 15, 8, 1),
      custodyMessage: _pending.custodyMessage,
    );
  }

  @override
  Future<RemittanceAcceptanceResult> acceptRemittance(
    UserSession session, {
    required String deviceId,
    required String notificationId,
  }) async {
    acceptCount += 1;
    throw StateError('A view-only session must never call acceptRemittance.');
  }
}
