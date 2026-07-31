import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/app.dart';

void main() {
  testWidgets('opens the collector dashboard from development login', (tester) async {
    await tester.pumpWidget(const GilbicApp());
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byType(TextField),
      'Test Collector',
    );
    await tester.tap(find.widgetWithText(FilledButton, 'Open dashboard'));
    await tester.pumpAndSettle();

    expect(find.text('Collector Dashboard'), findsOneWidget);
    expect(find.text('Daily Route'), findsOneWidget);
    expect(find.text('Offline Sync'), findsOneWidget);
  });
}
