import 'package:gilbic_mobile/src/core/time/spina_business_time.dart';

/// Display only. Exact decimal text never passes through floating point.
String formatSpinaMoney(String? value, {bool compact = false}) {
  final match = RegExp(r'^([+-]?)(\d+)(?:\.(\d+))?$').firstMatch(value?.trim() ?? '');
  if (match == null) return 'Unavailable';
  final sign = match.group(1)!;
  final whole = match.group(2)!;
  final rawFraction = match.group(3) ?? '00';
  final fraction = rawFraction.length == 1 ? '${rawFraction}0' : rawFraction;
  final grouped = whole.replaceAllMapped(RegExp(r'\B(?=(\d{3})+(?!\d))'), (_) => ',');
  final decimals = compact && RegExp(r'^0+$').hasMatch(fraction) ? '' : '.$fraction';
  return '$sign₱$grouped$decimals';
}

/// Calendar fields are validated and preserved without timezone conversion.
String formatSpinaCalendarDate(String? value) {
  if (value == null || value.trim().isEmpty) return 'Not recorded';
  final text = value.trim();
  if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(text)) return 'Unavailable';
  final parsed = DateTime.tryParse(text);
  if (parsed == null || '${parsed.year.toString().padLeft(4, '0')}-${parsed.month.toString().padLeft(2, '0')}-${parsed.day.toString().padLeft(2, '0')}' != text) return 'Unavailable';
  return text;
}

String formatSpinaInstant(DateTime? value) => value == null
    ? 'Not recorded' : formatSpinaBusinessDateTime(value);
