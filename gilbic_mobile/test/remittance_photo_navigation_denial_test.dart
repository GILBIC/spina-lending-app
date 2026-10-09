// Read-only review probe: real parent/child routes, synthetic data and HTTP only.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification_repository.dart';
import 'package:gilbic_mobile/src/features/notifications/remittance_notifications_page.dart';
import 'package:gilbic_mobile/src/features/remittance/remittance_photo_viewer_page.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const actor = UserSession(
  userId: 'synthetic-recipient',
  username: 'synthetic',
  displayName: 'Synthetic',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'synthetic-token',
  permissions: ['remittance.view', 'remittance.receive'],
);
const notification = RemittanceNotification(
  notificationId: 'synthetic-notification',
  remittanceId: 'synthetic-remittance',
  remittanceNumber: 'SYNTHETIC-001',
  title: 'Synthetic handover',
  message: 'PRIVATE SYNTHETIC PARENT DETAIL',
  status: 'pending',
  collectorName: 'Synthetic Collector',
  totalAmount: 100,
  clientCount: 1,
  transactionCount: 1,
  collectionDate: null,
  createdAt: null,
  custodyMessage: 'Synthetic cash custody',
  hasHandoverPhoto: true,
  handoverPhotoVersion: 1,
);

class Notifications extends Fake implements RemittanceNotificationRepository {
  int reads = 0;
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
  }) async => notification;
}

void main() {
  for (final status in [403, 401, 426]) {
    testWidgets('photo $status across actual notification navigation', (
      tester,
    ) async {
      final repo = Notifications();
      var photoReads = 0;
      await http.runWithClient(
        () async {
          await tester.pumpWidget(
            MaterialApp(
              home: RemittanceNotificationsPage(
                session: actor,
                repository: repo,
                deviceIdentityProvider: DeviceIdentityProvider(
                  store: MemoryDeviceIdentityStore()
                    ..value = 'synthetic-device',
                  platformResolver: () => 'android',
                  appVersionResolver: () async => 'test',
                ),
              ),
            ),
          );
          await tester.pumpAndSettle();
          final parentState = tester.state(
            find.byType(RemittanceNotificationsPage),
          );
          await tester.tap(find.text('Synthetic handover'));
          await tester.pumpAndSettle();
          expect(find.text('PRIVATE SYNTHETIC PARENT DETAIL'), findsOneWidget);
          final photoButton = find.byKey(
            const Key('view-handover-photo-synthetic-notification'),
          );
          await tester.ensureVisible(photoButton);
          await tester.tap(photoButton);
          await tester.pumpAndSettle();
          expect(
            find.byType(RemittancePhotoViewerPage),
            status == 403 ? findsOneWidget : findsNothing,
          );
          expect(find.textContaining('Sign in again'), findsOneWidget);
          if (status == 403) {
            expect(
              tester
                  .widget<IconButton>(
                    find.byWidgetPredicate(
                      (widget) =>
                          widget is IconButton &&
                          widget.tooltip == 'Reload photo',
                    ),
                  )
                  .onPressed,
              isNull,
            );
          }
          expect(photoReads, 1);
          expect(parentState.mounted, isTrue);
          if (status == 403) {
            await tester.pageBack();
            await tester.pumpAndSettle();
          }
          expect(
            tester.state(find.byType(RemittanceNotificationsPage)),
            same(parentState),
          );
          final retained = find
              .text('PRIVATE SYNTHETIC PARENT DETAIL')
              .evaluate()
              .isNotEmpty;
          final review = find.byKey(
            const Key('review-remittance-notification-synthetic-notification'),
          );
          final actionEnabled =
              review.evaluate().isNotEmpty &&
              tester.widget<FilledButton>(review).onPressed != null;
          // Record the actual state before asserting the desired global boundary.
          if (status == 403) {
            // A photo-specific object denial need not revoke unrelated parent data.
            expect(retained, isTrue);
            expect(actionEnabled, isTrue);
          } else {
            expect(
              retained,
              isFalse,
              reason:
                  'Session expiry/update rejection must revoke affected private parent state across Back.',
            );
            expect(actionEnabled, isFalse);
          }
        },
        () => MockClient((request) async {
          expect(
            request.url.path,
            '/api/mobile/v1/remittances/synthetic-remittance/handover-photo',
          );
          photoReads++;
          return http.Response(
            '{"detail":{"message":"Synthetic denied","code":"synthetic_denied"}}',
            status,
          );
        }),
      );
    });
  }
}
