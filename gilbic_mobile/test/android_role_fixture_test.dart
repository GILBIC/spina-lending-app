import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'dart:ui' as ui;
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';
import 'support/android_role_fixture.dart';

void main() {
  testWidgets(
    'capture includes pushed production review and its confirmation',
    (tester) async {
      final review = ManagementReviewPresentation.validated(
        binding: ManagementMutationBinding.collectionVoid,
        recordLabel: 'Official receipt',
        recordValue: 'SYNTHETIC-42',
        statusLabel: 'Eligible for protected correction',
        facts: const [ManagementReviewFact(label: 'Amount', value: '₱500.00')],
        warnings: const [],
        nextActionLabel: 'Void this collection',
        consequence: 'Permanent audit evidence remains.',
        actionEnabled: true,
      );
      await pumpAndroidRoleFixture(
        tester,
        size: const Size(320, 640),
        textScaler: TextScaler.linear(2),
        home: Scaffold(
          body: Builder(
            builder: (context) => FilledButton(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (context) => Scaffold(
                    body: ListView(
                      children: [
                        ManagementReviewPanel(review: review),
                        FilledButton(
                          onPressed: () =>
                              showManagementReviewConfirmation(context, review),
                          child: const Text('Open confirmation'),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              child: const Text('Open review'),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      Future<List<int>> pixels() async {
        final boundary = tester.renderObject<RenderRepaintBoundary>(
          find.byKey(const Key('android-role-capture')),
        );
        late List<int> bytes;
        await tester.runAsync(() async {
          final picture = await boundary.toImage(pixelRatio: 1);
          bytes = (await picture.toByteData(
            format: ui.ImageByteFormat.rawRgba,
          ))!.buffer.asUint8List().toList();
          picture.dispose();
        });
        return bytes;
      }

      final homePixels = await pixels();
      await tester.tap(find.text('Open review'));
      await tester.pumpAndSettle();
      final panel = find.byType(ManagementReviewPanel);
      expect(MediaQuery.textScalerOf(tester.element(panel)).scale(10), 20);
      expect(
        find.descendant(
          of: find.byKey(const Key('android-role-capture')),
          matching: panel,
        ),
        findsOneWidget,
      );
      expect(await pixels(), isNot(homePixels));
      await tester.scrollUntilVisible(
        find.text('Open confirmation'),
        200,
        scrollable: find.byType(Scrollable).last,
      );
      await tester.pumpAndSettle();
      final routePixels = await pixels();
      await tester.tap(find.text('Open confirmation'));
      await tester.pumpAndSettle();
      expect(
        find.descendant(
          of: find.byKey(const Key('android-role-capture')),
          matching: find.byType(AlertDialog),
        ),
        findsOneWidget,
      );
      expect(
        MediaQuery.textScalerOf(
          tester.element(find.byType(AlertDialog)),
        ).scale(10),
        20,
      );
      expect(await pixels(), isNot(routePixels));
      expect(tester.takeException(), isNull);
    },
  );
  for (final scale in [1.0, 1.3, 2.0]) {
    testWidgets('production Android fixture exposes scale $scale', (
      tester,
    ) async {
      await pumpAndroidRoleFixture(
        tester,
        size: const Size(320, 640),
        textScaler: TextScaler.linear(scale),
        home: Scaffold(
          body: Builder(
            builder: (context) {
              expect(Theme.of(context).platform, TargetPlatform.android);
              expect(
                Theme.of(context).colorScheme.primary,
                SpinaTheme.light.colorScheme.primary,
              );
              expect(MediaQuery.sizeOf(context), const Size(320, 640));
              expect(
                MediaQuery.textScalerOf(context).scale(10),
                closeTo(scale * 10, 0.001),
              );
              return const Text('Fixture');
            },
          ),
        ),
      );
      expect(tester.takeException(), isNull);
    });
  }
  testWidgets('fixture reports a deliberate overflowing row', (tester) async {
    await pumpAndroidRoleFixture(
      tester,
      size: const Size(320, 640),
      textScaler: TextScaler.linear(2),
      home: const Scaffold(
        body: Row(
          children: [SizedBox(width: 1000, child: Text('Overflow probe'))],
        ),
      ),
    );
    expect(tester.takeException(), isA<FlutterError>());
  });
}
