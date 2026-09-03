import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/time/spina_business_time.dart';

void main() {
  test('SPINA business date uses Philippine UTC+8 rollover', () {
    expect(
      formatSpinaBusinessDate(DateTime.parse('2026-08-17T16:30:00Z')),
      '2026-08-18',
    );
  });

  test('SPINA business date does not double-shift an explicit +08 instant', () {
    expect(
      formatSpinaBusinessDate(DateTime.parse('2026-08-18T00:30:00+08:00')),
      '2026-08-18',
    );
  });
}
