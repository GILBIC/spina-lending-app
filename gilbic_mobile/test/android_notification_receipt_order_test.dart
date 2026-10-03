import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/notifications/activity_notification.dart';
import 'package:gilbic_mobile/src/core/notifications/activity_notification_repository.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification_repository.dart';
import 'package:gilbic_mobile/src/features/notifications/activity_notifications_page.dart';
import 'package:gilbic_mobile/src/features/notifications/remittance_notifications_page.dart';
import 'android_shared_read_recovery_test.dart' as fixtures;
import 'support/android_role_fixture.dart';
import 'support/client_fixture.dart' show clientIdentity;

const oldTitle = 'Earlier synthetic snapshot';
const newTitle = 'Newer authoritative synthetic snapshot';

ActivityNotification activity(bool newer, {bool read = false}) =>
    ActivityNotification(
      id: 'same-activity',
      type: 'payment_posted',
      title: newer ? newTitle : oldTitle,
      message: 'Synthetic only',
      senderName: 'SPINA',
      metadata: {'amount': newer ? '200.00' : '100.00'},
      isRead: read,
      createdAt: DateTime.utc(2026, 10, 3),
    );

RemittanceNotification remittance(bool newer, {bool read = false}) =>
    RemittanceNotification(
      notificationId: 'same-remittance-notification',
      remittanceId: 'same-remittance',
      remittanceNumber: 'SYNTHETIC-ONLY',
      title: newer ? newTitle : oldTitle,
      message: 'Synthetic only',
      status: newer ? 'accepted' : 'pending',
      collectorName: 'Synthetic Collector',
      totalAmount: newer ? 200 : 100,
      clientCount: 1,
      transactionCount: 1,
      collectionDate: DateTime(2026, 10, 3),
      createdAt: DateTime.utc(2026, 10, 3),
      custodyMessage: 'Synthetic test facts',
      readAt: read ? DateTime.utc(2026, 10, 3) : null,
    );

class ActivityRepo implements ActivityNotificationRepository {
  int reads = 0, writes = 0;
  final pending = Completer<ActivityNotification>();
  @override
  Future<List<ActivityNotification>> load(
    UserSession session, {
    required String deviceId,
  }) async => [activity(reads++ > 0)];
  @override
  Future<ActivityNotification> markRead(
    UserSession session, {
    required String deviceId,
    required String notificationId,
  }) {
    expect(notificationId, 'same-activity');
    writes++;
    return pending.future;
  }
}

class RemittanceRepo implements RemittanceNotificationRepository {
  int reads = 0, writes = 0;
  final pending = Completer<RemittanceNotification>();
  @override
  Future<List<RemittanceNotification>> loadNotifications(
    UserSession session, {
    required String deviceId,
  }) async => [remittance(reads++ > 0)];
  @override
  Future<RemittanceNotification> markRead(
    UserSession session, {
    required String deviceId,
    required String notificationId,
  }) {
    expect(notificationId, 'same-remittance-notification');
    writes++;
    return pending.future;
  }

  @override
  Future<RemittanceAcceptanceResult> acceptRemittance(
    UserSession session, {
    required String deviceId,
    required String notificationId,
  }) => throw StateError('No custody command authorized');
}

void main() {
  for (final isActivity in [true, false]) {
    for (final status in [null, 401, 403]) {
      testWidgets(
        '${isActivity ? 'Activity' : 'Remittance'} late receipt $status respects newer same-ID GET facts and current denial',
        (tester) async {
          final a = ActivityRepo();
          final r = RemittanceRepo();
          final session = fixtures.session('synthetic-review');
          final identity = clientIdentity();
          await pumpAndroidRoleFixture(
            tester,
            size: const Size(800, 1600),
            textScaler: TextScaler.linear(1),
            home: isActivity
                ? ActivityNotificationsPage(
                    session: session,
                    deviceIdentityProvider: identity,
                    repository: a,
                    onSignOut: () async {},
                  )
                : RemittanceNotificationsPage(
                    session: session,
                    deviceIdentityProvider: identity,
                    repository: r,
                    onSignOut: () async {},
                  ),
          );
          await tester.pumpAndSettle();
          expect(find.text(oldTitle), findsOneWidget);
          await tester.tap(find.text(oldTitle));
          await tester.pump();
          expect(isActivity ? a.writes : r.writes, 1);
          await tester
              .widget<RefreshIndicator>(find.byType(RefreshIndicator))
              .onRefresh();
          await tester.pump();
          expect(find.text(newTitle), findsOneWidget);
          expect(find.text(oldTitle), findsNothing);
          expect(isActivity ? a.reads : r.reads, 2);
          if (status != null) {
            if (isActivity) {
              a.pending.completeError(fixtures.failure(status));
            } else {
              r.pending.completeError(fixtures.failure(status));
            }
          } else if (isActivity) {
            a.pending.complete(activity(false, read: true));
          } else {
            r.pending.complete(remittance(false, read: true));
          }
          await tester.pumpAndSettle();
          expect(
            find.text(newTitle),
            status == null ? findsOneWidget : findsNothing,
            reason:
                'Preserve newer facts after success, but clear current-scope denied data.',
          );
          if (status != null) {
            expect(
              find.text(status == 401 ? 'Sign in again' : 'Access unavailable'),
              findsWidgets,
            );
          }
          expect(find.text(oldTitle), findsNothing);
          expect(isActivity ? a.writes : r.writes, 1);
          expect(isActivity ? a.reads : r.reads, 2);
          expect(tester.takeException(), isNull);
        },
      );
    }
  }
}
