import 'dart:math';
import 'package:gilbic_mobile/src/core/management/accounting_readiness_repository.dart';
import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';

const collectorControlRoles = <String, (String, String)>{
  '1060': ('debit', 'Returns awaiting confirmation'),
  '2210': ('credit', 'Unidentified excess owed'),
  '2220': ('credit', 'Collector credit owed'),
};

Map<String, dynamic> validateCollectorControlSchedule(
  Map<String, dynamic> value, {
  required String bookId,
}) {
  final book = AccountingBookIdentity.fromPayload(
    accountingObject(value['book']),
  );
  accountingCheck(
    book.configured &&
        book.bookId == bookId &&
        accountingDate(value['as_of']) &&
        value['business_timezone'] == 'Asia/Manila' &&
        value['balance_basis'] == 'debit_minus_credit' &&
        value['comprehensive_source_coverage'] == false &&
        value['controls_reconciled'] is bool,
  );
  for (final key in [
    'movement_count',
    'unproven_movement_count',
    'correction_count',
    'limit',
    'offset',
  ]) {
    accountingCheck(value[key] is int && (value[key] as int) >= 0);
  }
  final limit = value['limit'] as int,
      offset = value['offset'] as int,
      count = value['movement_count'] as int;
  accountingCheck(
    limit >= 1 &&
        limit <= 500 &&
        (value['unproven_movement_count'] as int) <= count,
  );
  BigInt cents(Object? amount) =>
      BigInt.parse((amount as String).replaceAll('.', ''));
  final controls = accountingRows(value['controls']);
  accountingCheck(
    controls.length == 3 &&
        controls.map((row) => row['account_code']).toSet().length == 3,
  );
  for (final row in controls) {
    accountingCheck(
      collectorControlRoles.containsKey(row['account_code']) &&
          collectorControlRoles[row['account_code']]!.$1 ==
              row['normal_balance'] &&
          row['unregistered_line_count'] is int &&
          (row['unregistered_line_count'] as int) >= 0,
    );
    for (final key in [
      'source_balance',
      'ledger_balance',
      'difference',
      'source_amount',
      'ledger_amount',
    ]) {
      TreasuryMoney(row[key], signed: true);
    }
    final direction = row['normal_balance'] == 'debit'
        ? BigInt.one
        : -BigInt.one;
    accountingCheck(
      cents(row['source_amount']) == direction * cents(row['source_balance']) &&
          cents(row['ledger_amount']) ==
              direction * cents(row['ledger_balance']) &&
          cents(row['difference']) ==
              cents(row['ledger_balance']) - cents(row['source_balance']),
    );
  }
  final movements = accountingRows(value['movements']);
  accountingCheck(movements.length == min(limit, max(0, count - offset)));
  for (final row in movements) {
    accountingCheck(
      collectorControlRoles.containsKey(row['account_code']) &&
          accountingDate(row['effective_date']) &&
          (row['effective_date'] as String).compareTo(
                value['as_of'] as String,
              ) <=
              0 &&
          [
            'collector_case',
            'collector_resolution',
            'collector_credit',
            'collector_return_debit',
            'collector_entry',
          ].contains(row['source_type']) &&
          treasuryUuid(row['source_id']) &&
          row['exact_posted'] is bool,
    );
    TreasuryMoney(row['signed_amount'], signed: true);
  }
  final capacity = accountingObject(value['current_capacity']);
  accountingCheck(
    capacity['observed_at'] is String &&
        RegExp(r'(Z|\+00:00)$').hasMatch(capacity['observed_at'] as String) &&
        DateTime.tryParse(capacity['observed_at'] as String) != null,
  );
  for (final key in [
    'unidentified_amount',
    'outstanding_amount',
    'reserved_amount',
    'available_amount',
  ]) {
    TreasuryMoney(capacity[key]);
  }
  accountingCheck(
    cents(capacity['outstanding_amount']) -
            cents(capacity['reserved_amount']) ==
        cents(capacity['available_amount']),
  );
  if (value['controls_reconciled'] == true) {
    accountingCheck(
      value['unproven_movement_count'] == 0 &&
          value['correction_count'] == 0 &&
          controls.every(
            (row) =>
                row['difference'] == '0.00' &&
                row['unregistered_line_count'] == 0,
          ) &&
          movements.every((row) => row['exact_posted'] == true),
    );
  }
  return accountingObject(
    immutableTreasury({
      for (final key in [
        'as_of',
        'business_timezone',
        'balance_basis',
        'movement_count',
        'unproven_movement_count',
        'correction_count',
        'limit',
        'offset',
        'controls_reconciled',
        'comprehensive_source_coverage',
      ])
        key: value[key],
      'book': {
        for (final key in ['status', 'book_id', 'kind', 'entity_label'])
          key: accountingObject(value['book'])[key],
      },
      'current_capacity': {
        for (final key in [
          'observed_at',
          'unidentified_amount',
          'outstanding_amount',
          'reserved_amount',
          'available_amount',
        ])
          key: capacity[key],
      },
      'controls': [
        for (final row in controls)
          {
            for (final key in [
              'account_code',
              'normal_balance',
              'source_balance',
              'ledger_balance',
              'difference',
              'source_amount',
              'ledger_amount',
              'unregistered_line_count',
            ])
              key: row[key],
          },
      ],
      'movements': [
        for (final row in movements)
          {
            for (final key in [
              'account_code',
              'effective_date',
              'signed_amount',
              'source_type',
              'source_id',
              'exact_posted',
            ])
              key: row[key],
          },
      ],
    }),
  );
}
