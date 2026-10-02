import 'dart:io';
import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';
import 'android_fixture_fonts.dart';

Future<void>? _loadedFonts;
Future<void> _loadAndroidFonts() => _loadedFonts ??= () async {
  final configuration =
      jsonDecode(await File('.dart_tool/package_config.json').readAsString())
          as Map<String, dynamic>;
  final files = androidFixtureFontFiles(configuration);
  // Finish file reads before registering futures with FontLoader. A failed
  // artifact read must not leave another unhandled font future behind.
  final bytes = files.map((file) => file.readAsBytesSync()).toList();
  final roboto = FontLoader('Roboto');
  for (final data in bytes.take(5)) {
    roboto.addFont(Future.value(ByteData.sublistView(data)));
  }
  await roboto.load();
  final icons = FontLoader('MaterialIcons');
  icons.addFont(Future.value(ByteData.sublistView(bytes.last)));
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
  Object? fontError;
  StackTrace? fontStack;
  await tester.runAsync(() async {
    try {
      await _loadAndroidFonts().timeout(const Duration(seconds: 30));
    } catch (error, stack) {
      _loadedFonts = null;
      fontError = error;
      fontStack = stack;
    }
  });
  if (fontError != null) {
    Error.throwWithStackTrace(fontError!, fontStack!);
  }
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
