import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/account/account_repository.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/notifications/activity_notification.dart';
import 'package:gilbic_mobile/src/core/notifications/activity_notification_repository.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification_repository.dart';
import 'package:gilbic_mobile/src/features/account/account_settings_page.dart';
import 'package:gilbic_mobile/src/features/notifications/activity_notifications_page.dart';
import 'package:gilbic_mobile/src/features/notifications/remittance_notifications_page.dart';
import 'package:gilbic_mobile/src/features/notifications/notification_center_page.dart';
import 'support/android_role_fixture.dart';
import 'support/android_workflow_capture.dart';

const stale =
    'Showing the last successful information. It has not been refreshed.';
const privateA = 'Private record A';
const privateB = 'Private record B';
UserSession session(String id) => UserSession(
  userId: id,
  username: id,
  displayName: id,
  role: AppRole.employee,
  rawRole: 'Employee',
  accessToken: 'token-$id',
  permissions: const ['remittance.view', 'remittance.receive'],
);
SpinaApiException failure(int status) =>
    SpinaApiException('untrusted internal detail', statusCode: status);
String recoveryAction(int status) => status == 401
    ? 'Sign in again'
    : status == 426
    ? 'Return to sign-in'
    : 'Access unavailable';

class Control {
  int reads = 0, writes = 0, signOuts = 0;
  Future<void> Function(UserSession)? read;
  Future<void> Function()? write;
  bool empty = false;
  Future<void> load(UserSession session) async {
    reads++;
    await read?.call(session);
  }

  Future<void> mark() async {
    writes++;
    await write?.call();
  }
}

AccountOverview overview(UserSession session) => AccountOverview(
  profile: AccountProfile(
    id: session.userId,
    username: session.username,
    fullName: session.userId == 'A' ? privateA : privateB,
    role: 'Employee',
    status: 'active',
  ),
  devices: const [],
);
ActivityNotification activity(UserSession session, {bool read = false}) =>
    ActivityNotification(
      id: 'activity-${session.userId}',
      type: 'payment_posted',
      title: session.userId == 'A' ? privateA : privateB,
      message: 'Synthetic saved receipt',
      senderName: 'SPINA',
      metadata: const {'receipt_number': 'SYNTHETIC-1'},
      isRead: read,
      createdAt: DateTime.utc(2026, 10, 3),
    );
RemittanceNotification remittance(UserSession session, {bool read = false}) =>
    RemittanceNotification(
      notificationId: 'notification-${session.userId}',
      remittanceId: 'remittance-${session.userId}',
      remittanceNumber: 'SYNTHETIC-1',
      title: session.userId == 'A' ? privateA : privateB,
      message: 'Synthetic handover',
      status: 'pending',
      collectorName: 'Synthetic Collector',
      totalAmount: 100,
      clientCount: 1,
      transactionCount: 1,
      collectionDate: DateTime(2026, 10, 3),
      createdAt: DateTime.utc(2026, 10, 3),
      custodyMessage: 'Review before custody',
      readAt: read ? DateTime.utc(2026, 10, 3) : null,
    );

class Accounts implements AccountRepository {
  Accounts(this.control);
  final Control control;
  @override
  Future<AccountOverview> fetch(UserSession session) async {
    await control.load(session);
    return overview(session);
  }

  @override
  Future<AccountDevice> revokeDevice(UserSession session, String deviceId) =>
      throw StateError('No device write authorized');
  @override
  Future<void> changePassword(UserSession session, String password) =>
      throw StateError('No password write authorized');
}

class Activity implements ActivityNotificationRepository {
  Activity(this.control);
  final Control control;
  @override
  Future<List<ActivityNotification>> load(
    UserSession session, {
    required String deviceId,
  }) async {
    await control.load(session);
    return control.empty ? [] : [activity(session)];
  }

  @override
  Future<ActivityNotification> markRead(
    UserSession session, {
    required String deviceId,
    required String notificationId,
  }) async {
    expect(notificationId, 'activity-${session.userId}');
    await control.mark();
    return activity(session, read: true);
  }
}

class Remittances implements RemittanceNotificationRepository {
  Remittances(this.control);
  final Control control;
  @override
  Future<List<RemittanceNotification>> loadNotifications(
    UserSession session, {
    required String deviceId,
  }) async {
    await control.load(session);
    return control.empty ? [] : [remittance(session)];
  }

  @override
  Future<RemittanceNotification> markRead(
    UserSession session, {
    required String deviceId,
    required String notificationId,
  }) async {
    expect(notificationId, 'notification-${session.userId}');
    await control.mark();
    return remittance(session, read: true);
  }

  @override
  Future<RemittanceAcceptanceResult> acceptRemittance(
    UserSession session, {
    required String deviceId,
    required String notificationId,
  }) => throw StateError('No custody write authorized');
}

enum Surface { account, activity, remittance }

class Harness {
  Harness(this.surface) {
    account = Accounts(control);
    activityRepository = Activity(control);
    remittanceRepository = Remittances(control);
  }
  final Surface surface;
  final control = Control();
  final currentSession = ValueNotifier(session('A'));
  DeviceIdentityProvider identity = DeviceIdentityProvider(
    store: MemoryDeviceIdentityStore()..value = 'test-device',
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
  late final Accounts account;
  late final Activity activityRepository;
  late final Remittances remittanceRepository;
  Widget page(UserSession value) => switch (surface) {
    Surface.account => AccountSettingsPage(
      session: value,
      deviceIdentityProvider: identity,
      repository: account,
      onSignOut: () async {
        control.signOuts++;
      },
    ),
    Surface.activity => ActivityNotificationsPage(
      session: value,
      deviceIdentityProvider: identity,
      repository: activityRepository,
      onSignOut: () async {
        control.signOuts++;
      },
    ),
    Surface.remittance => RemittanceNotificationsPage(
      session: value,
      deviceIdentityProvider: identity,
      repository: remittanceRepository,
      onSignOut: () async {
        control.signOuts++;
      },
    ),
  };
  Future<void> pump(
    WidgetTester tester, {
    Size size = const Size(800, 1600),
    double scale = 1,
  }) async {
    addTearDown(currentSession.dispose);
    await pumpAndroidRoleFixture(
      tester,
      size: size,
      textScaler: TextScaler.linear(scale),
      home: ValueListenableBuilder(
        valueListenable: currentSession,
        builder: (_, value, _) => page(value),
      ),
    );
    await tester.pump();
    await tester.pump();
  }

  Future<void> Function() refresh(WidgetTester tester) =>
      tester.widget<RefreshIndicator>(find.byType(RefreshIndicator)).onRefresh;
}

void main() {
  for (final surface in Surface.values) {
    testWidgets('A8 $surface narrow error recovered empty and denied', (
      tester,
    ) async {
      final h = Harness(surface);
      h.control.read = (_) async => throw failure(503);
      await h.pump(tester, size: const Size(320, 640), scale: 2);
      await tester.pumpAndSettle();
      final semantics = tester.ensureSemantics();
      expect(find.text('Retry'), findsOneWidget);
      await captureAndroidWorkflowScroll(tester, 'shared-$surface-unavailable');
      await checkAndroidWorkflowSemantics(tester);
      h.control.read = null;
      await tester.tap(find.text('Retry'));
      await tester.pumpAndSettle();
      if (surface == Surface.remittance) {
        expect(
          tester
              .renderObject<RenderBox>(find.text(privateA))
              .constraints
              .maxWidth,
          greaterThanOrEqualTo(208),
          reason: 'Large-text notification identity has readable width',
        );
      }
      await captureAndroidWorkflowScroll(tester, 'shared-$surface-recovered');
      expect(h.control.reads, 2);
      h.control.empty = true;
      await h.refresh(tester)();
      await tester.pumpAndSettle();
      await captureAndroidWorkflowScroll(
        tester,
        'shared-$surface-authoritative-empty',
      );
      h.control.read = (_) async => throw failure(403);
      await h.refresh(tester)();
      await tester.pumpAndSettle();
      expect(find.text(privateA), findsNothing);
      expect(find.text('Access unavailable'), findsWidgets);
      await captureAndroidWorkflowScroll(tester, 'shared-$surface-denied');
      await checkAndroidWorkflowSemantics(tester);
      expect(h.control.writes, 0);
      semantics.dispose();
    });
  }
  for (final surface in Surface.values) {
    for (final status in [401, 403, 426]) {
      testWidgets(
        '$surface denied refresh $status clears affected records and does not repeat the GET',
        (tester) async {
          final h = Harness(surface);
          await h.pump(tester);
          await tester.pumpAndSettle();
          expect(find.text(privateA), findsOneWidget);
          final refresh = h.refresh(tester);
          h.control.read = (_) async => throw failure(status);
          await refresh();
          await tester.pumpAndSettle();
          expect(find.text(privateA), findsNothing);
          expect(find.text('untrusted internal detail'), findsNothing);
          expect(find.text(recoveryAction(status)), findsWidgets);
          expect(h.control.signOuts, 0);
          expect(find.text('Try again'), findsNothing);
          expect(find.text('Retry'), findsNothing);
          await refresh();
          await tester.pumpAndSettle();
          expect(h.control.reads, 2);
          expect(h.control.writes, 0);
          if (status == 401 || status == 426) {
            await tester.tap(find.text(recoveryAction(status)));
            await tester.pumpAndSettle();
            expect(h.control.signOuts, 1);
            expect(h.control.reads, 2);
          }
        },
      );
    }
    testWidgets(
      '$surface initial failure has scoped retry and never claims empty',
      (tester) async {
        final h = Harness(surface);
        h.control.read = (_) async => throw failure(503);
        await h.pump(tester);
        await tester.pumpAndSettle();
        expect(
          find.textContaining('No remittance notifications'),
          findsNothing,
        );
        expect(find.textContaining('No payment updates'), findsNothing);
        expect(find.text('untrusted internal detail'), findsNothing);
        expect(find.text('Retry'), findsOneWidget);
        h.control.read = null;
        await tester.tap(find.text('Retry'));
        await tester.pumpAndSettle();
        expect(find.text(privateA), findsOneWidget);
        expect(h.control.reads, 2);
        expect(h.control.writes, 0);
      },
    );
    testWidgets(
      '$surface transient refresh retains and labels last successful records',
      (tester) async {
        final h = Harness(surface);
        await h.pump(tester);
        await tester.pumpAndSettle();
        h.control.read = (_) async => throw failure(503);
        await h.refresh(tester)();
        await tester.pumpAndSettle();
        expect(find.text(privateA), findsOneWidget);
        expect(find.text(stale), findsOneWidget);
        expect(find.text('untrusted internal detail'), findsNothing);
        h.control.read = null;
        await tester.tap(find.text('Retry'));
        await tester.pumpAndSettle();
        expect(find.text(privateA), findsOneWidget);
        expect(find.text(stale), findsNothing);
        expect(h.control.reads, 3);
        expect(h.control.writes, 0);
      },
    );
    testWidgets('$surface deduplicates captured refresh callbacks', (
      tester,
    ) async {
      final h = Harness(surface);
      await h.pump(tester);
      await tester.pumpAndSettle();
      final pending = Completer<void>();
      h.control.read = (_) => pending.future;
      final refresh = h.refresh(tester);
      final first = refresh();
      final second = refresh();
      await tester.pump();
      expect(h.control.reads, 2);
      pending.complete();
      await Future.wait([first, second]);
      await tester.pumpAndSettle();
      expect(find.text(privateA), findsOneWidget);
      expect(h.control.writes, 0);
    });
    testWidgets('$surface ignores old read after actor replacement', (
      tester,
    ) async {
      final h = Harness(surface);
      final old = Completer<void>();
      h.control.read = (value) =>
          value.userId == 'A' ? old.future : Future.value();
      await h.pump(tester);
      h.currentSession.value = session('B');
      await tester.pump();
      await tester.pump();
      expect(find.text(privateB), findsOneWidget);
      old.complete();
      await tester.pumpAndSettle();
      expect(find.text(privateA), findsNothing);
      expect(find.text(privateB), findsOneWidget);
      expect(h.control.reads, 2);
      expect(h.control.writes, 0);
    });
    testWidgets(
      '$surface late completion after disposal cannot reveal private records',
      (tester) async {
        final h = Harness(surface);
        final old = Completer<void>();
        h.control.read = (_) => old.future;
        await h.pump(tester);
        await tester.pumpWidget(const SizedBox());
        old.complete();
        await tester.pumpAndSettle();
        expect(find.text(privateA), findsNothing);
        expect(tester.takeException(), isNull);
      },
    );
    testWidgets(
      '$surface normal token rotation preserves a pending same-scope read',
      (tester) async {
        final h = Harness(surface);
        final pending = Completer<void>();
        h.control.read = (_) => pending.future;
        await h.pump(tester);
        final owner = h.currentSession.value;
        owner.applyRefresh(
          UserSession(
            userId: 'A',
            username: 'A',
            displayName: 'A',
            role: AppRole.employee,
            rawRole: 'Employee',
            accessToken: 'rotated-A',
            permissions: owner.permissions,
          ),
        );
        addTearDown(owner.clearRefreshOverride);
        pending.complete();
        await tester.pumpAndSettle();
        expect(find.text(privateA), findsOneWidget);
        expect(h.control.reads, 1);
        expect(owner.accessToken, 'rotated-A');
        expect(h.control.writes, 0);
      },
    );
  }
  for (final surface in [Surface.activity, Surface.remittance]) {
    for (final status in [401, 403, 426]) {
      testWidgets(
        '$surface read-receipt denial $status clears records and stale row callback',
        (tester) async {
          final h = Harness(surface);
          await h.pump(tester);
          await tester.pumpAndSettle();
          h.control.write = () async => throw failure(status);
          final expanded = surface == Surface.remittance
              ? tester
                    .widget<ExpansionTile>(
                      find.byKey(const Key('notification-notification-A')),
                    )
                    .onExpansionChanged
              : null;
          final VoidCallback oldTap = surface == Surface.activity
              ? tester
                    .widget<InkWell>(
                      find.byKey(const Key('activity-notification-activity-A')),
                    )
                    .onTap!
              : () => expanded!(true);
          oldTap();
          await tester.pumpAndSettle();
          expect(find.text(privateA), findsNothing);
          expect(find.text(recoveryAction(status)), findsWidgets);
          expect(h.control.signOuts, 0);
          expect(h.control.writes, 1);
          oldTap();
          await tester.pumpAndSettle();
          expect(h.control.writes, 1);
        },
      );
    }
    testWidgets(
      '$surface denial invalidates an already pending successful read',
      (tester) async {
        final h = Harness(surface);
        await h.pump(tester);
        await tester.pumpAndSettle();
        final old = Completer<void>();
        h.control.read = (_) => old.future;
        final read = h.refresh(tester)();
        await tester.pump();
        h.control.write = () async => throw failure(403);
        await tester.tap(find.text(privateA));
        await tester.pump();
        await tester.pump();
        old.complete();
        await read;
        await tester.pumpAndSettle();
        expect(find.text(privateA), findsNothing);
        expect(find.text('Access unavailable'), findsWidgets);
        expect(h.control.writes, 1);
        expect(h.control.reads, 2);
      },
    );
    testWidgets(
      '$surface successful empty read is distinguished from unavailable',
      (tester) async {
        final h = Harness(surface);
        h.control.empty = true;
        await h.pump(tester);
        await tester.pumpAndSettle();
        expect(
          find.text(
            surface == Surface.activity
                ? 'No payment updates yet.'
                : 'No remittance notifications yet.',
          ),
          findsOneWidget,
        );
        expect(find.text('Retry'), findsNothing);
        expect(h.control.reads, 1);
      },
    );
    testWidgets(
      '$surface transient receipt failure does not clear or retry records',
      (tester) async {
        final h = Harness(surface);
        await h.pump(tester);
        await tester.pumpAndSettle();
        h.control.write = () async => throw failure(503);
        await tester.tap(find.text(privateA));
        await tester.pumpAndSettle();
        expect(find.text(privateA), findsOneWidget);
        expect(h.control.writes, 1);
        expect(h.control.reads, 1);
        expect(find.text('untrusted internal detail'), findsNothing);
      },
    );
    testWidgets(
      '$surface does not start a repository read after disposed identity lookup',
      (tester) async {
        final h = Harness(surface);
        final identity = DeferredIdentity();
        h.identity = identity;
        await h.pump(tester);
        expect(h.control.reads, 0);
        await tester.pumpWidget(const SizedBox());
        identity.pending.complete(
          const DeviceIdentity(
            installationId: 'old-device',
            platform: 'android',
            appVersion: '1',
          ),
        );
        await tester.pumpAndSettle();
        expect(h.control.reads, 0);
        expect(tester.takeException(), isNull);
      },
    );
    testWidgets('NotificationCenter forwards real recovery to $surface', (
      tester,
    ) async {
      final h = Harness(surface);
      h.control.read = (_) async => throw failure(401);
      await pumpAndroidRoleFixture(
        tester,
        size: const Size(800, 1600),
        textScaler: TextScaler.linear(1),
        home: NotificationCenterPage(
          session: session('A'),
          deviceIdentityProvider: h.identity,
          activityRepository: h.activityRepository,
          remittanceRepository: h.remittanceRepository,
          onSignOut: () async {
            h.control.signOuts++;
          },
        ),
      );
      await tester.tap(
        find.byKey(
          Key(
            surface == Surface.activity
                ? 'open-activity-notifications'
                : 'open-remittance-notifications',
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(h.control.signOuts, 0);
      await tester.tap(find.text('Sign in again'));
      await tester.pumpAndSettle();
      expect(h.control.signOuts, 1);
      expect(h.control.reads, 1);
      expect(h.control.writes, 0);
    });
  }
}

class DeferredIdentity extends DeviceIdentityProvider {
  final pending = Completer<DeviceIdentity>();
  @override
  Future<DeviceIdentity> load() => pending.future;
}
