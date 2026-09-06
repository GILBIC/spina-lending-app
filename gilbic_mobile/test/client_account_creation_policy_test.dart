import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/app.dart';
import 'package:gilbic_mobile/src/core/auth/session_store.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('signed-out SPINA does not expose Client self-registration', (
    tester,
  ) async {
    await tester.pumpWidget(
      GilbicApp(sessionStore: MemorySessionStore()),
    );
    await tester.pumpAndSettle();

    expect(find.text('Sign in'), findsOneWidget);
    expect(find.text('Create client account'), findsNothing);
    expect(
      find.byKey(const Key('create-client-account-button')),
      findsNothing,
    );
  });
}
