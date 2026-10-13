import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';

const collectorAccountingStages = <String, (String, String)>{
  'settlement': (
    'Accepted cash count',
    'Transfers the actual accepted count from existing Collector custody cash and records unidentified excess. Loan principal and interest are not recognized again.',
  ),
  'recognition': (
    'Recognized Collector credit',
    'Moves identified excess into Collector credit payable. This step does not move cash.',
  ),
  'credit_application': (
    'Credit used for remittance',
    'Reduces Collector credit payable and settles the approved custody obligation on the acceptance date. Actual cash received has a separate accounting review.',
  ),
  'return_debit': (
    'Actual return debit',
    'Records actual cash paid and its separately evidenced fee. The principal awaits the Collector’s received confirmation.',
  ),
  'return_confirmation': (
    'Received return confirmation',
    'Reduces credit payable and clears the return awaiting confirmation. This step does not move cash again.',
  ),
  'return_reversal': (
    'Actual incoming return reversal',
    'Records only principal actually received back and restores that amount of Collector credit. The earlier fee remains unchanged.',
  ),
};

Map<String, dynamic> validateCollectorAccounting(
  Map<String, dynamic> value, {
  required String bookId,
  required String accountId,
  required String sourceId,
  required String sourceKind,
}) {
  accountingCheck(
    collectorAccountingStages.containsKey(sourceKind) &&
        [
          bookId,
          accountId,
          sourceId,
          value['fiscal_period_id'],
        ].every(treasuryUuid) &&
        value['book_id'] == bookId &&
        value['treasury_account_id'] == accountId &&
        value['source_id'] == sourceId &&
        value['source_kind'] == sourceKind &&
        accountingDate(value['posting_date']) &&
        accountingDigest(value['source_digest']),
  );
  TreasuryMoney(value['amount'], positive: true);
  TreasuryMoney(value['fee']);
  BigInt cents(Object? amount) =>
      BigInt.parse((amount as String).replaceAll('.', ''));
  final lines = accountingRows(value['lines']);
  accountingCheck(lines.length >= 2 && lines.length <= 3);
  for (final row in lines) {
    final name = accountingObject(row['account_snapshot'])['name'];
    accountingCheck(
      row['line_number'] is int &&
          (row['line_number'] as int) > 0 &&
          [
            '1010',
            '1030',
            '1020',
            '1060',
            '2210',
            '2220',
            '5240',
          ].contains(row['account_code']) &&
          name is String &&
          name.trim().isNotEmpty,
    );
    TreasuryMoney(row['debit']);
    TreasuryMoney(row['credit']);
    accountingCheck((row['debit'] == '0.00') != (row['credit'] == '0.00'));
  }
  accountingCheck(
    lines.map((row) => row['line_number']).toSet().length == lines.length &&
        lines.map((row) => row['account_code']).toSet().length ==
            lines.length &&
        lines.fold<BigInt>(
              BigInt.zero,
              (sum, row) => sum + cents(row['debit']) - cents(row['credit']),
            ) ==
            BigInt.zero,
  );
  void exact(String code, String side, BigInt amount) {
    final matches = lines.where((row) => row['account_code'] == code).toList();
    accountingCheck(matches.length == 1);
    accountingCheck(
      cents(matches.single[side]) == amount &&
          matches.single[side == 'debit' ? 'credit' : 'debit'] == '0.00',
    );
  }

  final amount = cents(value['amount']), fee = cents(value['fee']);
  Map<String, dynamic>? split;
  if (value['custody_split'] != null) {
    accountingCheck(['settlement', 'credit_application'].contains(sourceKind));
    final raw = accountingObject(value['custody_split']);
    const keys = [
      'gross_obligation',
      'authorized_credit_amount',
      'physical_cash_required',
      'physical_amount',
      'excess_amount',
    ];
    for (final key in keys) {
      TreasuryMoney(raw[key]);
    }
    split = {for (final key in keys) key: raw[key]};
    accountingCheck(
      cents(split['authorized_credit_amount']) > BigInt.zero &&
          cents(split['gross_obligation']) ==
              cents(split['authorized_credit_amount']) +
                  cents(split['physical_cash_required']) &&
          cents(split['physical_amount']) ==
              cents(split['physical_cash_required']) +
                  cents(split['excess_amount']),
    );
  }
  final cash = lines
      .where((row) => ['1010', '1030'].contains(row['account_code']))
      .toList();
  if (sourceKind != 'return_debit') accountingCheck(fee == BigInt.zero);
  if (sourceKind == 'settlement') {
    accountingCheck(cash.length == 1);
    exact(cash.single['account_code'] as String, 'debit', amount);
    final custody = lines
        .where((row) => row['account_code'] == '1020')
        .toList();
    if (split != null) {
      final principal = cents(split['physical_cash_required']),
          excess = cents(split['excess_amount']);
      accountingCheck(
        cents(split['physical_amount']) == amount &&
            lines.length ==
                1 +
                    (principal > BigInt.zero ? 1 : 0) +
                    (excess > BigInt.zero ? 1 : 0),
      );
      if (principal > BigInt.zero) {
        exact('1020', 'credit', principal);
      } else {
        accountingCheck(custody.isEmpty);
      }
      if (excess > BigInt.zero) exact('2210', 'credit', excess);
    } else {
      accountingCheck(
        custody.length == 1 &&
            custody.single['debit'] == '0.00' &&
            cents(custody.single['credit']) > BigInt.zero &&
            cents(custody.single['credit']) <= amount,
      );
      final excess = amount - cents(custody.single['credit']);
      accountingCheck(lines.length == (excess == BigInt.zero ? 2 : 3));
      if (excess > BigInt.zero) exact('2210', 'credit', excess);
    }
  } else if (sourceKind == 'credit_application') {
    accountingCheck(
      split != null &&
          cents(split['authorized_credit_amount']) == amount &&
          cash.isEmpty &&
          lines.length == 2,
    );
    exact('2220', 'debit', amount);
    exact('1020', 'credit', amount);
  } else if (sourceKind == 'recognition' ||
      sourceKind == 'return_confirmation') {
    accountingCheck(lines.length == 2 && cash.isEmpty);
    exact(sourceKind == 'recognition' ? '2210' : '2220', 'debit', amount);
    exact(sourceKind == 'recognition' ? '2220' : '1060', 'credit', amount);
  } else {
    accountingCheck(
      cash.length == 1 && lines.length == (fee == BigInt.zero ? 2 : 3),
    );
    exact(
      cash.single['account_code'] as String,
      sourceKind == 'return_debit' ? 'credit' : 'debit',
      amount + fee,
    );
    exact(
      sourceKind == 'return_debit' ? '1060' : '2220',
      sourceKind == 'return_debit' ? 'debit' : 'credit',
      amount,
    );
    if (fee > BigInt.zero) exact('5240', 'debit', fee);
  }
  return accountingObject(
    immutableTreasury({
      if (split != null) 'custody_split': split,
      for (final key in [
        'book_id',
        'source_kind',
        'source_id',
        'treasury_account_id',
        'fiscal_period_id',
        'posting_date',
        'amount',
        'fee',
        'source_digest',
      ])
        key: value[key],
      'lines': [
        for (final row in lines)
          {
            for (final key in [
              'line_number',
              'account_code',
              'debit',
              'credit',
            ])
              key: row[key],
            'name': accountingObject(row['account_snapshot'])['name'],
          },
      ],
    }),
  );
}
