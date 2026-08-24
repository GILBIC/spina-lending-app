import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/features/auth/login_page.dart';
import 'package:gilbic_mobile/src/features/design/spina_design_preview_page.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

void main() {
  test('SPINA theme keeps the approved pink and white visual anchors', () {
    final theme = SpinaTheme.light;

    expect(theme.colorScheme.primary, SpinaTheme.brandPink);
    expect(theme.colorScheme.surface, Colors.white);
    expect(theme.scaffoldBackgroundColor, SpinaTheme.canvas);
    expect(theme.useMaterial3, isTrue);
  });

  testWidgets('Android CA1 login keeps only the essential sign-in content', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(412, 915));
    try {
      await tester.pumpWidget(
        MaterialApp(
          theme: SpinaTheme.light,
          home: LoginPage(
            onSignIn: (username, password) async => null,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('SPINA'), findsOneWidget);
      expect(find.text('Welcome back'), findsOneWidget);
      expect(find.byKey(const Key('username-field')), findsOneWidget);
      expect(find.byKey(const Key('password-field')), findsOneWidget);
      expect(find.byKey(const Key('sign-in-button')), findsOneWidget);
      expect(find.text('Clear access. Confident control.'), findsNothing);
      expect(
        find.text('Sign in to continue to your SPINA account.'),
        findsNothing,
      );
      expect(
        find.text('Your role and access are protected by SPINA.'),
        findsNothing,
      );
      expect(find.byKey(const Key('open-ca1-design-preview')), findsNothing);
      expect(find.text('Review-only preview for the Android CA1 design pass.'), findsNothing);
    } finally {
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.binding.setSurfaceSize(null);
    }
  });

  testWidgets('CA1 preview demonstrates explicit confirmation language', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(412, 915));
    try {
      await tester.pumpWidget(
        MaterialApp(
          theme: SpinaTheme.light,
          home: const SpinaDesignPreviewPage(),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Review confirmation'));
      await tester.pumpAndSettle();

      expect(find.text('Confirm before continuing'), findsOneWidget);
      expect(
        find.textContaining('Financial actions will always explain'),
        findsOneWidget,
      );
      expect(find.text('I understand'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);
    } finally {
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.binding.setSurfaceSize(null);
    }
  });
}
