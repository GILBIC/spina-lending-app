import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance.dart';

void main() {
  test(
    'zero cash settled history retains exact credit without claiming cash receipt',
    () {
      final data = <String, dynamic>{
        'remittance_id': 'synthetic-remittance',
        'remittance_number': 'SYNTHETIC',
        'status': 'received',
        'total_amount': '100.00',
        'settlement_split': {
          'gross_obligation': '100.00',
          'authorized_credit_amount': '100.00',
          'physical_cash_required': '0.00',
          'physical_amount': '0.00',
          'excess_amount': '0.00',
        },
      };
      final record = RemittanceRecord.fromPayload(data)!;
      expect(
        record.settlementSplit!.description,
        contains('Actual cash received: PHP 0.00'),
      );
      expect(record.settlementSplit!.credit, '100.00');
      for (final key in [
        'gross_obligation',
        'physical_amount',
        'excess_amount',
      ]) {
        expect(
          () => RemittanceRecord.fromPayload({
            ...data,
            'settlement_split': {
              ...data['settlement_split'] as Map,
              key: '99.00',
            },
          }),
          throwsFormatException,
        );
      }
      expect(
        () => RemittanceRecord.fromPayload({...data, 'total_amount': '101.00'}),
        throwsFormatException,
      );
      expect(
        RemittanceRecord.fromPayload({
          ...data,
          'settlement_split': null,
        })!.settlementSplit,
        isNull,
      );
    },
  );
}
