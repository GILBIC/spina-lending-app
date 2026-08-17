const Duration _spinaBusinessUtcOffset = Duration(hours: 8);

/// Converts an instant to SPINA's Philippine business wall-clock time.
///
/// This value is intended for display only. Persisted and transmitted
/// timestamps must remain UTC.
DateTime spinaBusinessWallClock(DateTime value) {
  return value.toUtc().add(_spinaBusinessUtcOffset);
}

String formatSpinaBusinessDateTime(DateTime? value) {
  if (value == null) {
    return 'Unknown time';
  }

  final businessTime = spinaBusinessWallClock(value);
  return '${businessTime.year.toString().padLeft(4, '0')}-'
      '${businessTime.month.toString().padLeft(2, '0')}-'
      '${businessTime.day.toString().padLeft(2, '0')} '
      '${businessTime.hour.toString().padLeft(2, '0')}:'
      '${businessTime.minute.toString().padLeft(2, '0')}';
}
