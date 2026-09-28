import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/payments/request_money.dart';

void main() {
  test(
    'request money preserves cents and supports existing separator input',
    () {
      expect(requestMoney('9999999999999999.99'), '9999999999999999.99');
      expect(requestMoney('001,234.5'), '1234.50');
      expect(requestMoney(100.01), '100.01');
      expect(
        requestMoneyCents('1000000000000000.01'),
        BigInt.parse('100000000000000001'),
      );
    },
  );

  test('invalid and lossy money never becomes a rounded request', () {
    for (final amount in <Object?>[
      '',
      '1e3',
      '1.001',
      '-1',
      '10000000000000000',
      null,
      true,
      double.nan,
      double.infinity,
      1000000000000000.0,
    ]) {
      expect(
        () => requestMoney(amount),
        throwsFormatException,
        reason: '$amount',
      );
      expect(tryRequestMoney(amount), isNull);
      expect(requestMoneyCents(amount), isNull);
    }
  });
}
