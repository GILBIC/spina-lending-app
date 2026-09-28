const Duration _spinaBusinessUtcOffset = Duration(hours: 8);

/// Converts an instant to SPINA's Philippine business wall-clock time.
///
/// This value is intended for display only. Persisted and transmitted
/// timestamps must remain UTC.
DateTime spinaBusinessWallClock(DateTime value) {
  return value.toUtc().add(_spinaBusinessUtcOffset);
}

/// Interprets manually selected calendar fields as Manila time, regardless of
/// the phone's timezone. The result is an instant suitable for API submission.
DateTime spinaBusinessWallClockToUtc(DateTime value) {
  return DateTime.utc(
    value.year,
    value.month,
    value.day,
    value.hour,
    value.minute,
    value.second,
    value.millisecond,
    value.microsecond,
  ).subtract(_spinaBusinessUtcOffset);
}

String formatSpinaBusinessDate(DateTime value) {
  final businessTime = spinaBusinessWallClock(value);
  return '${businessTime.year.toString().padLeft(4, '0')}-'
      '${businessTime.month.toString().padLeft(2, '0')}-'
      '${businessTime.day.toString().padLeft(2, '0')}';
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
