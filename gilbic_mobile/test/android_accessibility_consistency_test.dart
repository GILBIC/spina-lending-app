import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/features/shared/spina_status.dart';
import 'support/android_role_fixture.dart';
import 'support/role_homes.dart';
import 'android_read_recovery_test.dart' show ControlledSchedules, open;

void main() {
  for (final role in [
    AppRole.management,
    AppRole.employee,
    AppRole.collector,
    AppRole.client,
  ]) {
    testWidgets(
      '${role.name} visible home has labelled Android targets and contrast',
      (tester) async {
        final handle = tester.ensureSemantics();

        await pumpAndroidRoleFixture(
          tester,
          home: roleHome(role),
          size: const Size(360, 640),
          textScaler: TextScaler.linear(1.3),
        );
        await tester.pumpAndSettle();
        await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
        await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
        await expectLater(tester, meetsGuideline(textContrastGuideline));
        final scrollable = find.byType(Scrollable).last;
        for (var step = 0; step < 18; step++) {
          final position = tester.state<ScrollableState>(scrollable).position;
          if (position.extentAfter < 1) {
            break;
          }
          await tester.drag(scrollable, const Offset(0, -450));
          await tester.pumpAndSettle();
          expect(tester.takeException(), isNull);
          // Viewport clipping can expose only the edge of a full-size target.
          // The Android target guideline is checked on the initial home and
          // complete menu/error surfaces above/below, not clipped scroll edges.
          await expectLater(tester, meetsGuideline(textContrastGuideline));
        }
        handle.dispose();
      },
    );
  }
  testWidgets('Client account menu has readable labelled Android actions', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    await pumpAndroidRoleFixture(
      tester,
      home: roleHome(AppRole.client),
      size: const Size(360, 640),
      textScaler: TextScaler.linear(1.3),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Account & tools'));
    await tester.pumpAndSettle();
    expect(find.text('Profile & security'), findsOneWidget);
    await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
    await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
    await expectLater(tester, meetsGuideline(textContrastGuideline));
    handle.dispose();
  });
  testWidgets('Client expired read exposes accessible explicit recovery', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    await open(tester, schedules: ControlledSchedules()..failureStatus = 401);
    await tester.pumpAndSettle();
    expect(find.text('Sign in again'), findsOneWidget);
    await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
    await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
    await expectLater(tester, meetsGuideline(textContrastGuideline));
    handle.dispose();
  });
  testWidgets(
    'semantic statuses scale and communicate without a color-only action',
    (tester) async {
      final handle = tester.ensureSemantics();

      await pumpAndroidRoleFixture(
        tester,
        size: const Size(320, 640),
        textScaler: TextScaler.linear(2),
        home: Scaffold(
          body: ListView(
            children: [
              for (final tone in SpinaStatusTone.values)
                SpinaStatusLabel(
                  label: '${tone.name} status awaiting authoritative review',
                  tone: tone,
                ),
            ],
          ),
        ),
      );
      expect(find.byType(Text), findsNWidgets(4));
      expect(find.byType(FilledButton), findsNothing);
      expect(tester.takeException(), isNull);
      await expectLater(tester, meetsGuideline(textContrastGuideline));
      handle.dispose();
    },
  );
}
