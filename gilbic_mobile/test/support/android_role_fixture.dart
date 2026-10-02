import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

Future<void> pumpAndroidRoleFixture(
  WidgetTester tester, {
  required Widget home,
  required Size size,
  required TextScaler textScaler,
  bool disableAnimations = false,
  EdgeInsets viewInsets = EdgeInsets.zero,
}) async {
  await tester.binding.setSurfaceSize(size);
  addTearDown(() => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(
    MaterialApp(
      theme: SpinaTheme.light.copyWith(platform: TargetPlatform.android),
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context).copyWith(
          size: size,
          devicePixelRatio: 1,
          textScaler: textScaler,
          disableAnimations: disableAnimations,
          viewInsets: viewInsets,
        ),
        child: child!,
      ),
      home: RepaintBoundary(
        key: const Key('android-role-capture'),
        child: home,
      ),
    ),
  );
}
