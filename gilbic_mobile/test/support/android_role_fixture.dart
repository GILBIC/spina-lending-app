import 'dart:io';
import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

Future<void>? _loadedFonts;
Future<void> _loadAndroidFonts() => _loadedFonts ??= () async {
  final configuration =
      jsonDecode(await File('.dart_tool/package_config.json').readAsString())
          as Map<String, dynamic>;
  final root = configuration['flutterRoot'] as String?;
  if (root == null) throw StateError('Flutter SDK path unavailable');
  final directory = Uri.parse(
    '$root/',
  ).resolve('bin/cache/artifacts/material_fonts/');
  final roboto = FontLoader('Roboto');
  for (final weight in ['regular', 'medium', 'bold', 'black', 'light']) {
    roboto.addFont(
      File.fromUri(
        directory.resolve('roboto-$weight.ttf'),
      ).readAsBytes().then(ByteData.sublistView),
    );
  }
  await roboto.load();
  final icons = FontLoader('MaterialIcons');
  icons.addFont(
    File.fromUri(
      directory.resolve('materialicons-regular.otf'),
    ).readAsBytes().then(ByteData.sublistView),
  );
  await icons.load();
}();

Future<void> pumpAndroidRoleFixture(
  WidgetTester tester, {
  required Widget home,
  required Size size,
  required TextScaler textScaler,
  bool disableAnimations = false,
  EdgeInsets viewInsets = EdgeInsets.zero,
}) async {
  await tester.runAsync(_loadAndroidFonts);
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
