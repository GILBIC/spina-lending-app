import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';
import 'support/android_role_fixture.dart';

void main() {
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
