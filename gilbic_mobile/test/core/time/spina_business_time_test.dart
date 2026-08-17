import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/time/spina_business_time.dart';

void main() {
  group('SPINA business time', () {
    test('formats a UTC instant as Philippine business time', () {
      final value = DateTime.parse('2026-08-17T01:45:00Z');

      expect(formatSpinaBusinessDateTime(value), '2026-08-17 09:45');
    });

    test('does not double-shift an already +08:00 timestamp', () {
      final value = DateTime.parse('2026-08-17T09:45:00+08:00');

      expect(formatSpinaBusinessDateTime(value), '2026-08-17 09:45');
    });

    test('returns Unknown time for null', () {
      expect(formatSpinaBusinessDateTime(null), 'Unknown time');
    });
  });
}
