import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/management/protected_accounting_evidence.dart';
import 'management_protected_accounting_page_test.dart'
    show id, source, regularApplicationSource;

Map<String, dynamic> validate(Map<String, dynamic> value) =>
    validateApplicationAccounting(
      value,
      bookId: id(1),
      accountId: id(3),
      applicationId: id(4),
    );

void main() {
  for (final product in ['fixed_daily', 'seven_by_seven']) {
    Map<String, dynamic> review() =>
        product == 'fixed_daily' ? regularApplicationSource() : source;
    Map<String, dynamic> principalOnly() {
      final value = review();
      final lines = value['lines'] as List;
      lines.removeRange(2, lines.length);
      lines[1]['credit'] = '100.00';
      return value;
    }

    test(
      '$product retains exact public policy and excludes private evidence',
      () {
        final value = review();
        final result = validate(value);
        expect(result['product_model'], product);
        expect(
          result['accounting_policy_version'],
          value['accounting_policy_version'],
        );
        expect(jsonEncode(result), isNot(contains('DO NOT DISPLAY')));
        expect(result.containsKey('origin'), isFalse);
        expect(validate(principalOnly())['amount'], '100.00');
      },
    );
    test('$product refuses accounts belonging to the other product', () {
      final value = review();
      final lines = value['lines'] as List;
      lines[1]['account_code'] = product == 'fixed_daily' ? '1110' : '1100';
      lines[2]['account_code'] = product == 'fixed_daily' ? '4010' : '4000';
      expect(() => validate(value), throwsFormatException);
    });
    test('$product rejects missing or crossed policy pairs', () {
      for (final key in ['product_model', 'accounting_policy_version']) {
        final value = review()..remove(key);
        expect(() => validate(value), throwsFormatException, reason: key);
      }
      final legacy = review()
        ..remove('product_model')
        ..remove('accounting_policy_version');
      expect(() => validate(legacy), throwsFormatException);
      final crossed = review()
        ..['accounting_policy_version'] = product == 'fixed_daily'
            ? 'treasury_seven_by_seven_application_v1'
            : 'treasury_regular_original_first_cash_v1';
      expect(() => validate(crossed), throwsFormatException);
    });
    test('$product rejects balanced two-sided lines', () {
      final value = review();
      final row = (value['lines'] as List)[1];
      row['debit'] = '1.00';
      row['credit'] = '91.00';
      expect(() => validate(value), throwsFormatException);
    });
    test('$product rejects zero-effect lines and duplicate line numbers', () {
      final zero = principalOnly();
      (zero['lines'] as List).add({
        'line_number': 4,
        'account_code': '1120',
        'debit': '0.00',
        'credit': '0.00',
        'account_snapshot': {'name': 'Interest receivable'},
      });
      expect(() => validate(zero), throwsFormatException);
      final duplicate = review();
      (duplicate['lines'] as List)[1]['line_number'] = 1;
      expect(() => validate(duplicate), throwsFormatException);
    });
    test('$product rejects additional liability legs even when balanced', () {
      final value = review();
      (value['lines'] as List)[3]['account_code'] = '2200';
      expect(() => validate(value), throwsFormatException);
    });
    test('$product requires unique account and direction coordinates', () {
      final value = principalOnly();
      final lines = value['lines'] as List;
      lines[1]['credit'] = '90.00';
      lines.add({
        ...Map<String, dynamic>.from(lines[1] as Map),
        'line_number': 3,
        'credit': '10.00',
      });
      expect(() => validate(value), throwsFormatException);
    });
    test('$product rejects balanced but inconsistent EIR coordinates', () {
      final value = review();
      final lines = value['lines'] as List;
      lines[3]['debit'] = '11.00';
      lines[4]['credit'] = '11.00';
      expect(() => validate(value), throwsFormatException);
    });
    test('$product never accepts principal or income debit coordinates', () {
      for (final position in [1, 2]) {
        final value = review();
        final lines = value['lines'] as List;
        final invalidDebitCode = lines[position]['account_code'];
        lines.removeRange(1, lines.length);
        lines.addAll([
          {
            'line_number': 2,
            'account_code': invalidDebitCode,
            'debit': '1.00',
            'credit': '0.00',
            'account_snapshot': {'name': 'Invalid debit coordinate'},
          },
          {
            'line_number': 3,
            'account_code': '1120',
            'debit': '0.00',
            'credit': '101.00',
            'account_snapshot': {'name': 'Interest receivable'},
          },
        ]);
        expect(() => validate(value), throwsFormatException);
      }
    });
  }
  test('unbalanced lines and unknown policy versions stay unavailable', () {
    final imbalance = source;
    (imbalance['lines'] as List)[1]['credit'] = '90.01';
    expect(() => validate(imbalance), throwsFormatException);
    final unknown = source..['accounting_policy_version'] = 'future_policy';
    expect(() => validate(unknown), throwsFormatException);
  });
}
