import 'package:flutter/material.dart';

/// Shared visual language for SPINA mobile.
///
/// The Android CA review establishes this design system first. The same tokens
/// are intentionally platform-neutral so the approved visual language can be
/// carried to iOS, Desktop and Web without copying a phone-only layout.
abstract final class SpinaTheme {
  static const Color brandPink = Color(0xFFD84F8B);
  static const Color brandPinkDark = Color(0xFF8D2858);
  static const Color brandPinkSoft = Color(0xFFFFE7F1);
  static const Color blush = Color(0xFFFFF6FA);
  static const Color canvas = Color(0xFFFFFBFD);
  static const Color ink = Color(0xFF2E242A);
  static const Color inkMuted = Color(0xFF74636C);
  static const Color line = Color(0xFFEAD8E0);
  static const Color success = Color(0xFF2F7D62);
  static const Color warning = Color(0xFFA86518);

  static ThemeData get light {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: brandPink,
      brightness: Brightness.light,
    ).copyWith(
      primary: brandPink,
      onPrimary: Colors.white,
      primaryContainer: brandPinkSoft,
      onPrimaryContainer: brandPinkDark,
      secondary: brandPinkDark,
      onSecondary: Colors.white,
      surface: Colors.white,
      onSurface: ink,
      outline: line,
      outlineVariant: const Color(0xFFF2E5EB),
      error: const Color(0xFFB3261E),
    );

    final base = ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: canvas,
      visualDensity: VisualDensity.standard,
    );

    return base.copyWith(
      textTheme: base.textTheme.copyWith(
        headlineLarge: base.textTheme.headlineLarge?.copyWith(
          color: ink,
          fontWeight: FontWeight.w800,
          letterSpacing: -0.8,
        ),
        headlineMedium: base.textTheme.headlineMedium?.copyWith(
          color: ink,
          fontWeight: FontWeight.w800,
          letterSpacing: -0.5,
        ),
        headlineSmall: base.textTheme.headlineSmall?.copyWith(
          color: ink,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.3,
        ),
        titleLarge: base.textTheme.titleLarge?.copyWith(
          color: ink,
          fontWeight: FontWeight.w700,
        ),
        titleMedium: base.textTheme.titleMedium?.copyWith(
          color: ink,
          fontWeight: FontWeight.w600,
        ),
        bodyLarge: base.textTheme.bodyLarge?.copyWith(
          color: ink,
          height: 1.35,
        ),
        bodyMedium: base.textTheme.bodyMedium?.copyWith(
          color: ink,
          height: 1.35,
        ),
        bodySmall: base.textTheme.bodySmall?.copyWith(
          color: inkMuted,
          height: 1.35,
        ),
        labelLarge: base.textTheme.labelLarge?.copyWith(
          fontWeight: FontWeight.w700,
        ),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent,
        foregroundColor: ink,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        surfaceTintColor: Colors.transparent,
        titleTextStyle: TextStyle(
          color: ink,
          fontSize: 20,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.25,
        ),
      ),
      cardTheme: CardThemeData(
        color: Colors.white,
        elevation: 0,
        shadowColor: Colors.black.withValues(alpha: 0.06),
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: const BorderSide(color: Color(0xFFF0E3E9)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        labelStyle: const TextStyle(color: inkMuted),
        hintStyle: const TextStyle(color: Color(0xFF9B8892)),
        prefixIconColor: brandPinkDark,
        suffixIconColor: inkMuted,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: line),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: line),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: brandPink, width: 1.8),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: Color(0xFFB3261E)),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: Color(0xFFB3261E), width: 1.8),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(52),
          backgroundColor: brandPink,
          foregroundColor: Colors.white,
          disabledBackgroundColor: const Color(0xFFF1D5E1),
          disabledForegroundColor: const Color(0xFF9B7D8A),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 15),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          textStyle: const TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(0, 52),
          foregroundColor: brandPinkDark,
          side: const BorderSide(color: Color(0xFFE5B7CA)),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 15),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          textStyle: const TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: brandPinkDark,
          textStyle: const TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(
          foregroundColor: brandPinkDark,
          minimumSize: const Size(44, 44),
        ),
      ),
      floatingActionButtonTheme: const FloatingActionButtonThemeData(
        backgroundColor: brandPink,
        foregroundColor: Colors.white,
        elevation: 2,
        focusElevation: 2,
        hoverElevation: 3,
        highlightElevation: 3,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(18)),
        ),
      ),
      chipTheme: base.chipTheme.copyWith(
        backgroundColor: blush,
        selectedColor: brandPinkSoft,
        side: const BorderSide(color: line),
        labelStyle: const TextStyle(color: ink, fontWeight: FontWeight.w600),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(999),
        ),
      ),
      dividerTheme: const DividerThemeData(
        color: Color(0xFFF0E3E9),
        thickness: 1,
        space: 1,
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: Colors.white,
        indicatorColor: brandPinkSoft,
        elevation: 0,
        height: 72,
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          final selected = states.contains(WidgetState.selected);
          return TextStyle(
            color: selected ? brandPinkDark : inkMuted,
            fontWeight: selected ? FontWeight.w700 : FontWeight.w600,
            fontSize: 12,
          );
        }),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          final selected = states.contains(WidgetState.selected);
          return IconThemeData(
            color: selected ? brandPinkDark : inkMuted,
          );
        }),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(24),
        ),
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.transparent,
        showDragHandle: true,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: ink,
        contentTextStyle: const TextStyle(color: Colors.white),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
        ),
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: brandPink,
        linearTrackColor: brandPinkSoft,
        circularTrackColor: brandPinkSoft,
      ),
    );
  }
}

abstract final class SpinaSpacing {
  static const double xxs = 4;
  static const double xs = 8;
  static const double sm = 12;
  static const double md = 16;
  static const double lg = 24;
  static const double xl = 32;
  static const double xxl = 40;
}
