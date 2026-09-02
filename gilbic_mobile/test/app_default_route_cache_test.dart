import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/app.dart';
import 'package:gilbic_mobile/src/core/auth/session_store.dart';

void main() {
  testWidgets('default Windows composition reaches sign in without SQLCipher', (
    tester,
  ) async {
    final previousPlatform = debugDefaultTargetPlatformOverride;
    debugDefaultTargetPlatformOverride = TargetPlatform.windows;
    addTearDown(() {
      debugDefaultTargetPlatformOverride = previousPlatform;
    });

    await tester.pumpWidget(
      GilbicApp(sessionStore: MemorySessionStore()),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('sign-in-button')), findsOneWidget);
  });
}
