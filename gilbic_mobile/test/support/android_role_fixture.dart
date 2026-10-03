import 'package:flutter/foundation.dart';
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
  final originalPlatform = debugDefaultTargetPlatformOverride;
  late ThemeData androidTheme;
  try {
    // Build the production theme under Android so its font families, as well
    // as platform behavior, are Android's. Changing platform afterwards does
    // not rebuild Windows text styles and would retain unavailable Segoe UI.
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    final production = SpinaTheme.light;
    // The Android engine defaults an omitted family to Roboto. The widget
    // engine defaults it to Ahem instead, even after fonts are registered.
    // Bind only that omitted family; retain production colors/sizes/weights.
    androidTheme = production.copyWith(
      appBarTheme: production.appBarTheme.copyWith(
        titleTextStyle: production.appBarTheme.titleTextStyle?.copyWith(
          fontFamily: 'Roboto',
        ),
        toolbarTextStyle: production.appBarTheme.toolbarTextStyle?.copyWith(
          fontFamily: 'Roboto',
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: _androidFontFallback(production.filledButtonTheme.style),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: _androidFontFallback(production.outlinedButtonTheme.style),
      ),
      textButtonTheme: TextButtonThemeData(
        style: _androidFontFallback(production.textButtonTheme.style),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: _androidFontFallback(production.elevatedButtonTheme.style),
      ),
      chipTheme: production.chipTheme.copyWith(
        labelStyle: _androidTextFontFallback(production.chipTheme.labelStyle),
        secondaryLabelStyle: _androidTextFontFallback(
          production.chipTheme.secondaryLabelStyle,
        ),
      ),
      snackBarTheme: production.snackBarTheme.copyWith(
        contentTextStyle: _androidTextFontFallback(
          production.snackBarTheme.contentTextStyle,
        ),
      ),
    );
  } finally {
    debugDefaultTargetPlatformOverride = originalPlatform;
  }
  await tester.pumpWidget(
    MaterialApp(
      theme: androidTheme,
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context).copyWith(
          size: size,
          devicePixelRatio: 1,
          textScaler: textScaler,
          disableAnimations: disableAnimations,
          viewInsets: viewInsets,
        ),
        child: RepaintBoundary(
          key: const Key('android-role-capture'),
          child: child!,
        ),
      ),
      home: home,
    ),
  );
}

ButtonStyle? _androidFontFallback(ButtonStyle? style) => style?.copyWith(
  textStyle: WidgetStateProperty.resolveWith(
    (states) =>
        style.textStyle?.resolve(states)?.copyWith(fontFamily: 'Roboto'),
  ),
);

TextStyle? _androidTextFontFallback(TextStyle? style) =>
    style?.copyWith(fontFamily: style.fontFamily ?? 'Roboto');
