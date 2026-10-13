import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/management/financial_statements.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

void main() {
  test(
    'financial statement amounts retain every cent beyond double precision',
    () {
      expect(
        FinancialStatementLine.fromPayload({
          'account_code': '1010',
          'account_name': 'Cash',
          'amount': '90071992547409.93',
        }).amount,
        '90071992547409.93',
      );
      expect(
        FinancialStatementLine.fromPayload({
          'account_code': '1190',
          'account_name': 'Allowance',
          'amount': '-0.01',
        }).amount,
        '-0.01',
      );
    },
  );
  test('financial statement amounts reject inexact or nonfinite payloads', () {
    for (final value in [
      1.23,
      double.nan,
      'NaN',
      'Infinity',
      '1e2',
      '0.001',
      '1.2',
    ]) {
      expect(
        () => FinancialStatementLine.fromPayload({
          'account_code': '1010',
          'account_name': 'Cash',
          'amount': value,
        }),
        throwsA(isA<SpinaApiException>()),
      );
    }
  });
}
