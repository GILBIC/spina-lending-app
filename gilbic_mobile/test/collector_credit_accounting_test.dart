import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/management/collector_accounting_evidence.dart';
import 'management_collector_accounting_page_test.dart'
    show collectorLine, collectorSource;
import 'management_protected_accounting_page_test.dart' show id;

const split = <String, dynamic>{
  'gross_obligation': '100.00',
  'authorized_credit_amount': '4.00',
  'physical_cash_required': '96.00',
  'physical_amount': '98.00',
  'excess_amount': '2.00',
};
Map<String, dynamic> source([String kind = 'credit_application']) => {
  ...collectorSource(kind),
  'amount': kind == 'settlement' ? '98.00' : '4.00',
  'fee': '0.00',
  'custody_split': {...split},
  'lines': kind == 'settlement'
      ? [
          collectorLine(1, '1010', '98.00', '0.00'),
          collectorLine(2, '1020', '0.00', '96.00'),
          collectorLine(3, '2210', '0.00', '2.00'),
        ]
      : [
          collectorLine(1, '2220', '4.00', '0.00'),
          collectorLine(2, '1020', '0.00', '4.00'),
        ],
};
Map<String, dynamic> validate(Map<String, dynamic> value) =>
    validateCollectorAccounting(
      value,
      bookId: id(1),
      accountId: id(3),
      sourceId: id(5),
      sourceKind: value['source_kind'] as String,
    );

void main() {
  test(
    'application contains only payable and custody with exact retained split',
    () {
      expect(validate(source())['custody_split'], split);
      for (final changed in [
        <String, dynamic>{'authorized_credit_amount': '5.00'},
        {'gross_obligation': '99.00'},
        {'physical_amount': '96.00'},
      ]) {
        expect(
          () => validate({
            ...source(),
            'custody_split': {...split, ...changed},
          }),
          throwsA(anything),
        );
      }
      expect(
        () => validate({...source(), 'custody_split': null}),
        throwsA(anything),
      );
      expect(
        () => validate({
          ...source(),
          'lines': [
            collectorLine(1, '2220', '4.00', '0.00'),
            collectorLine(2, '1010', '0.00', '4.00'),
          ],
        }),
        throwsA(anything),
      );
    },
  );
  test('cash leg keeps actual cash distinct from credit consumption', () {
    expect(validate(source('settlement'))['custody_split'], split);
    expect(
      () => validate({
        ...source('settlement'),
        'lines': [
          collectorLine(1, '1010', '98.00', '0.00'),
          collectorLine(2, '1020', '0.00', '97.00'),
          collectorLine(3, '2210', '0.00', '1.00'),
        ],
      }),
      throwsA(anything),
    );
  });
  test('full credit plus excess cash omits a zero custody line', () {
    final value = {
      ...source('settlement'),
      'amount': '2.00',
      'custody_split': {
        'gross_obligation': '100.00',
        'authorized_credit_amount': '100.00',
        'physical_cash_required': '0.00',
        'physical_amount': '2.00',
        'excess_amount': '2.00',
      },
      'lines': [
        collectorLine(1, '1010', '2.00', '0.00'),
        collectorLine(2, '2210', '0.00', '2.00'),
      ],
    };
    expect(validate(value)['amount'], '2.00');
    expect(
      () => validate({...value, 'custody_split': null}),
      throwsA(anything),
    );
  });
}
