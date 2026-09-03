import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

void main() {
  testWidgets('iOS keeps the SPINA identity and centers app bar titles', (
    tester,
  ) async {
    final previousPlatform = debugDefaultTargetPlatformOverride;
    debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
    await tester.binding.setSurfaceSize(const Size(430, 800));
    addTearDown(() async {
      await tester.binding.setSurfaceSize(null);
    });

    try {
      await tester.pumpWidget(
        MaterialApp(
          theme: SpinaTheme.light,
          home: Scaffold(
            appBar: AppBar(title: const Text('SPINA')),
            body: const SizedBox.expand(),
          ),
        ),
      );

      final title = find.text('SPINA');
      final theme = Theme.of(tester.element(title));
      expect(theme.platform, TargetPlatform.iOS);
      expect(theme.colorScheme.primary, SpinaTheme.brandPink);
      expect(tester.getCenter(title).dx, closeTo(215, 1));
    } finally {
      debugDefaultTargetPlatformOverride = previousPlatform;
    }
  });
}
