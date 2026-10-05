import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification_repository.dart';
import 'package:gilbic_mobile/src/features/notifications/remittance_notifications_page.dart';
import 'android_shared_read_recovery_test.dart' show session;
import 'support/android_role_fixture.dart';
import 'support/client_fixture.dart' show clientIdentity;

class _StatusRepository implements RemittanceNotificationRepository {
  _StatusRepository(String status)
    : notification = RemittanceNotification.fromPayload({
        'notification_id': 'status-notification',
        'remittance_id': 'status-remittance',
        'remittance_number': 'SYNTHETIC-STATUS',
        'title': 'Synthetic remittance',
        'message': 'Synthetic status review only',
        'status': status,
        'collector_name': 'Synthetic Collector',
        'total_amount': '100.00',
        'client_count': 1,
        'transaction_count': 1,
        'collection_date': '2026-10-03',
        'created_at': '2026-10-03T00:00:00Z',
      })!;

  final RemittanceNotification notification;
  int reads = 0;
  int writes = 0;

  @override
  Future<List<RemittanceNotification>> loadNotifications(
    UserSession session, {
    required String deviceId,
  }) async {
    reads++;
    return [notification];
  }

  @override
  Future<RemittanceNotification> markRead(
    UserSession session, {
    required String deviceId,
    required String notificationId,
  }) async {
    writes++;
    throw StateError('Rendering a status must not mark a notification read');
  }

  @override
  Future<RemittanceAcceptanceResult> acceptRemittance(
    UserSession session, {
    required String deviceId,
    required String notificationId,
  }) async {
    writes++;
    throw StateError('Rendering a status must not accept custody');
  }
}

void main() {
  for (final (rawStatus, expectedText, expectedIcon) in [
    (
      'pending',
      'Action required — review full handover',
      Icons.notifications_active,
    ),
    ('rejected', 'Rejected — cash stayed with sender', Icons.cancel_outlined),
    ('accepted', 'Accepted — money under your custody', Icons.verified),
    ('future_state', 'Status unavailable', Icons.info_outline),
    ('cancelled', 'Status unavailable', Icons.info_outline),
  ]) {
    testWidgets(
      'Remittance $rawStatus does not infer custody from an unknown status',
      (tester) async {
        final repository = _StatusRepository(rawStatus);
        await pumpAndroidRoleFixture(
          tester,
          size: const Size(412, 915),
          textScaler: TextScaler.linear(1),
          home: RemittanceNotificationsPage(
            session: session('status-review'),
            deviceIdentityProvider: clientIdentity(),
            repository: repository,
            onSignOut: () async {},
          ),
        );
        await tester.pumpAndSettle();
        final row = find.byKey(const Key('notification-status-notification'));
        expect(row, findsOneWidget);
        if (rawStatus != 'accepted') {
          expect(
            find.textContaining('Accepted — money under your custody'),
            findsNothing,
          );
          expect(
            find.descendant(of: row, matching: find.byIcon(Icons.verified)),
            findsNothing,
          );
        }
        expect(find.textContaining(expectedText), findsOneWidget);
        expect(
          find.descendant(of: row, matching: find.byIcon(expectedIcon)),
          findsOneWidget,
        );
        expect(repository.notification.normalizedStatus, rawStatus);
        expect(repository.notification.notificationId, 'status-notification');
        expect(repository.notification.remittanceId, 'status-remittance');
        expect(repository.notification.totalAmount, 100);
        expect(repository.reads, 1);
        expect(repository.writes, 0);
        expect(tester.takeException(), isNull);
      },
    );
  }
}
