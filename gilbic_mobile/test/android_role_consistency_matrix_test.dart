import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';
import 'support/android_role_fixture.dart';
import 'support/role_homes.dart';

void main() {
  for (final role in [AppRole.management, AppRole.employee, AppRole.collector, AppRole.client]) {
    for (final size in [const Size(320, 640), const Size(360, 640), const Size(412, 915)]) {
      for (final scale in [1.0, 1.3, 2.0]) {
        testWidgets('${role.name} ${size.width.toInt()}x${size.height.toInt()} scale $scale all content', (tester) async {
          await pumpAndroidRoleFixture(tester, size: size, textScaler: TextScaler.linear(scale), home: roleHome(role));
          await tester.pumpAndSettle();
          final context = tester.element(find.byType(Scaffold).last);
          expect(MediaQuery.textScalerOf(context).scale(10), closeTo(scale * 10, .001));
          expect(Theme.of(context).colorScheme.primary, SpinaTheme.light.colorScheme.primary);
          expect(tester.takeException(), isNull);
          final scrollable = find.byType(Scrollable).last;
          for (var step = 0; step < 18; step++) {
            final state = tester.state<ScrollableState>(scrollable);
            if (state.position.pixels >= state.position.maxScrollExtent) break;
            await tester.drag(scrollable, const Offset(0, -450));
            await tester.pumpAndSettle();
            expect(tester.takeException(), isNull, reason: 'scroll step $step');
          }
        });
      }
    }
  }
}
