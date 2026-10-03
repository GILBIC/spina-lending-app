import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collector_field_home_page.dart';
import 'package:gilbic_mobile/src/features/notifications/notification_center_page.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/client_fixture.dart';
import 'support/android_role_fixture.dart';
import 'support/role_homes.dart';

void main() {
  for (final configuration in [(412.0, 915.0, 1.0), (320.0, 640.0, 2.0)]) {
    testWidgets(
      'Management grouped Notifications opens safely ${configuration.$1}/${configuration.$3}',
      (tester) async {
        await pumpAndroidRoleFixture(
          tester,
          home: roleHome(AppRole.management),
          size: Size(configuration.$1, configuration.$2),
          textScaler: TextScaler.linear(configuration.$3),
        );
        await tester.pumpAndSettle();
        final launcher = find.byKey(const Key('management-notifications'));
        await tester.scrollUntilVisible(
          launcher,
          300,
          scrollable: find.byType(Scrollable).last,
        );
        await Scrollable.ensureVisible(tester.element(launcher), alignment: .6);
        await tester.pumpAndSettle();
        final output = Platform.environment['SPINA_ANDROID_A4_CAPTURE_DIR'];
        if (output != null) {
          final boundary = tester.renderObject<RenderRepaintBoundary>(
            find.byKey(const Key('android-role-capture')),
          );
          await tester.runAsync(() async {
            final picture = await boundary.toImage(pixelRatio: 1);
            final bytes = await picture.toByteData(
              format: ui.ImageByteFormat.png,
            );
            picture.dispose();
            await Directory(output).create(recursive: true);
            await File(
              '$output/management-secondary-${configuration.$1.toInt()}-scale-${configuration.$3}.png',
            ).writeAsBytes(bytes!.buffer.asUint8List());
          });
        }
        await tester.tap(launcher);
        await tester.pumpAndSettle();
        expect(find.byType(NotificationCenterPage), findsOneWidget);
        await tester.scrollUntilVisible(
          find.byKey(const Key('open-remittance-notifications')),
          250,
          scrollable: find.byType(Scrollable).last,
        );
        expect(
          find.byKey(const Key('open-remittance-notifications')),
          findsOneWidget,
        );
        await tester.binding.handlePopRoute();
        await tester.pumpAndSettle();
        expect(launcher, findsOneWidget);
        expect(find.byTooltip('Sign out'), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );
  }
  for (final role in [AppRole.management, AppRole.employee]) {
    testWidgets('${role.name} canonical secondary labels', (tester) async {
      await pumpAndroidRoleFixture(
        tester,
        home: roleHome(role),
        size: const Size(412, 915),
        textScaler: TextScaler.linear(1),
      );
      await tester.pumpAndSettle();
      final scroll = find.byType(Scrollable).last;
      await tester.scrollUntilVisible(
        find.text('Profile & security'),
        400,
        scrollable: scroll,
      );
      expect(find.text('Profile & security'), findsOneWidget);
      expect(find.text('Offline & sync'), findsOneWidget);
      expect(find.text('Notifications'), findsOneWidget);
    });
  }
  for (final role in [AppRole.employee, AppRole.client]) {
    testWidgets('${role.name} account menu keeps all four secondary labels', (
      tester,
    ) async {
      await pumpAndroidRoleFixture(
        tester,
        home: roleHome(role),
        size: const Size(412, 915),
        textScaler: TextScaler.linear(1),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Account & tools'));
      await tester.pumpAndSettle();
      for (final label in [
        'Profile & security',
        'Notifications',
        'Offline & sync',
        'Sign out',
      ]) {
        expect(find.text(label), findsWidgets);
      }
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
    });
  }
  testWidgets('view-only Remit is disabled with an explanation', (
    tester,
  ) async {
    await pumpAndroidRoleFixture(
      tester,
      home: _collector(_session(['route.view', 'remittance.view'])),
      size: const Size(412, 915),
      textScaler: TextScaler.linear(1),
    );
    await tester.pumpAndSettle();
    final remit = tester.widget<NavigationDestination>(
      find.widgetWithText(NavigationDestination, 'Remit'),
    );
    expect(remit.enabled, isFalse);
    expect(find.textContaining('Remit unavailable:'), findsOneWidget);
  });
  for (final tool in [
    ('treasury', 'treasury.view'),
    ('residence-visit', 'client_onboarding.visit.record'),
    ('employee-operations', 'employee.portal.view'),
    ('remittance-requests', 'remittance.view'),
    ('assigned-remittance', 'remittance.create'),
    ('other-area', 'collection.create'),
    ('renewals', 'renewal.recommend.assigned'),
  ]) {
    testWidgets('opened More revalidates ${tool.$1} before any request', (
      tester,
    ) async {
      final requests = <String>[];
      await http.runWithClient(
        () async {
          var session = _session(['route.view', tool.$2]);
          late StateSetter update;
          await pumpAndroidRoleFixture(
            tester,
            home: StatefulBuilder(
              builder: (_, setState) {
                update = setState;
                return _collector(session);
              },
            ),
            size: const Size(412, 915),
            textScaler: TextScaler.linear(1),
          );
          await tester.pumpAndSettle();
          await tester.tap(find.byKey(const Key('collector-more-tab')));
          await tester.pumpAndSettle();
          final tile = find.byKey(Key('collector-more-${tool.$1}'));
          expect(tile, findsOneWidget);
          await Scrollable.ensureVisible(tester.element(tile));
          await tester.pumpAndSettle();
          update(() => session = _session(['route.view']));
          await tester.pumpAndSettle();
          final before = requests.length;
          await tester.tap(tile);
          await tester.pump();
          await tester.pump(const Duration(milliseconds: 500));
          expect(find.byType(CollectorFieldHomePage), findsOneWidget);
          expect(requests.skip(before), isEmpty);
          expect(
            find.textContaining('Your current SPINA access'),
            findsOneWidget,
          );
        },
        () => MockClient((request) async {
          requests.add('${request.method} ${request.url.path}');
          return http.Response('{}', 500);
        }),
      );
    });
  }
  testWidgets(
    'Collector More hides unauthorized tools and keeps shared labels',
    (tester) async {
      await pumpAndroidRoleFixture(
        tester,
        home: roleHome(AppRole.collector),
        size: const Size(412, 915),
        textScaler: TextScaler.linear(1),
      );
      await tester.pumpAndSettle();
      expect(find.byType(CollectorFieldHomePage), findsOneWidget);
      final remit = tester.widget<NavigationDestination>(
        find.widgetWithText(NavigationDestination, 'Remit'),
      );
      expect(remit.enabled, isFalse);
      expect(
        find.text('Remit unavailable: remittance access is not assigned'),
        findsOneWidget,
      );
      await tester.tap(find.byKey(const Key('collector-more-tab')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('collector-more-renewals')), findsNothing);
      expect(find.text('Offline & sync'), findsOneWidget);
      expect(find.text('Profile & security'), findsOneWidget);
      expect(find.text('Notifications'), findsOneWidget);
      final signOut = find.byKey(const Key('collector-more-sign-out'));
      await tester.ensureVisible(signOut);
      await tester.pumpAndSettle();
      expect(find.text('Sign out'), findsOneWidget);
    },
  );
}

UserSession _session(List<String> permissions) => UserSession(
  userId: 'secondary-collector',
  username: 'synthetic',
  displayName: 'Collector',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'synthetic-token',
  permissions: permissions,
);

Widget _collector(UserSession session) => CollectorFieldHomePage(
  session: session,
  onSignOut: () async {},
  collectorRouteLoader: SyntheticRoute(),
  paymentSubmissionRepository: SpinaPaymentSubmissionRepository(),
  deviceIdentityProvider: clientIdentity(),
  collectionDeviceSequence: MemoryCollectionDeviceSequence(),
);
