import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/features/collector/collector_field_home_page.dart';
import 'support/android_role_fixture.dart';
import 'support/role_homes.dart';

void main() {
  for (final role in [AppRole.management, AppRole.employee]) {
    testWidgets('${role.name} canonical secondary labels', (tester) async {
      await pumpAndroidRoleFixture(tester, home: roleHome(role), size: const Size(412, 915), textScaler: TextScaler.linear(1));
      await tester.pumpAndSettle();
      final scroll = find.byType(Scrollable).last;
      await tester.scrollUntilVisible(find.text('Profile & security'), 400, scrollable: scroll);
      expect(find.text('Profile & security'), findsOneWidget);
      expect(find.text('Offline & sync'), findsOneWidget);
    });
  }
  testWidgets('Collector More hides unauthorized tools and keeps shared labels', (tester) async {
    await pumpAndroidRoleFixture(tester, home: roleHome(AppRole.collector), size: const Size(412, 915), textScaler: TextScaler.linear(1));
    await tester.pumpAndSettle();
    expect(find.byType(CollectorFieldHomePage), findsOneWidget);
    await tester.tap(find.byKey(const Key('collector-more-tab')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('collector-more-renewals')), findsNothing);
    expect(find.text('Offline & sync'), findsOneWidget);
    expect(find.text('Profile & security'), findsOneWidget);
    expect(find.text('Notifications'), findsOneWidget);
  });
}
