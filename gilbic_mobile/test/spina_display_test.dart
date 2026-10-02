import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan.dart';
import 'package:gilbic_mobile/src/core/formatting/spina_display.dart';

void main() {
  test('compact money keeps nonzero cents and extra supplied precision', () {
    expect(formatSpinaMoney('1200.00', compact: true), '₱1,200');
    expect(formatSpinaMoney('1200.50', compact: true), '₱1,200.50');
    expect(formatSpinaMoney('1.0001', compact: true), '₱1.0001');
    expect(formatSpinaMoney(null), 'Unavailable');
  });
  test('calendar and instant retain distinct meanings', () {
    expect(formatSpinaCalendarDate('2026-10-02'), '2026-10-02');
    expect(formatSpinaCalendarDate('2026-02-31'), 'Unavailable');
    expect(formatSpinaCalendarDate('bad'), 'Unavailable');
    expect(formatSpinaCalendarDate(null), 'Not recorded');
    expect(
      formatSpinaInstant(DateTime.parse('2026-10-01T16:30:00Z')),
      '2026-10-02 00:30',
    );
    expect(formatSpinaInstant(null), 'Not recorded');
  });
  test('invalid authoritative money is unavailable rather than raw text', () {
    expect(formatClientLoanMoney('not money'), 'Unavailable');
  });
  test('exact money retains supplied precision and large adjacent values', () {
    expect(formatClientLoanMoney('12345.60'), '₱12,345.60');
    expect(formatClientLoanMoney('-50.00'), '-₱50.00');
    expect(formatClientLoanMoney('0'), '₱0.00');
    expect(formatClientLoanMoney('1.2345'), '₱1.2345');
    expect(
      formatClientLoanMoney('90071992547409.91'),
      '₱90,071,992,547,409.91',
    );
    expect(
      formatClientLoanMoney('90071992547409.92'),
      '₱90,071,992,547,409.92',
    );
  });
}
