import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/app.dart';
import 'package:gilbic_mobile/src/core/auth/session_store.dart';

import 'support/app_platform_dependencies.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets(
    'default app composition avoids SQLCipher on Windows',
    (tester) async {
      debugDefaultTargetPlatformOverride = TargetPlatform.windows;
      try {
        await tester.pumpWidget(
          GilbicApp(
            deviceIdentityProvider: testAppDeviceIdentity(),
            imageRecoveryController: testAppImageRecovery(),
            sessionStore: MemorySessionStore(),
          ),
        );
        await tester.pumpAndSettle();

        expect(find.text('Sign in'), findsOneWidget);
      } finally {
        debugDefaultTargetPlatformOverride = null;
      }
    },
  );
}
