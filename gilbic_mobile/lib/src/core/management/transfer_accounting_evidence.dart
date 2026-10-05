import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';

Map<String, dynamic> validateTransferAccounting(
  Map<String, dynamic> value, {
  required String bookId,
  required String sourceAccountId,
  required String destinationAccountId,
  required String transferId,
  required String leg,
}) {
  accountingCheck(
    ['source', 'destination'].contains(leg) &&
        sourceAccountId != destinationAccountId &&
        value['book_id'] == bookId &&
        value['transfer_id'] == transferId &&
        value['leg'] == leg &&
        value['source_account_id'] == sourceAccountId &&
        value['destination_account_id'] == destinationAccountId &&
        value['treasury_account_id'] ==
            (leg == 'source' ? sourceAccountId : destinationAccountId) &&
        treasuryUuid(value['event_id']) &&
        treasuryUuid(value['fiscal_period_id']) &&
        accountingDate(value['posting_date']) &&
        accountingDigest(value['source_digest']),
  );
  TreasuryMoney(value['amount'], positive: true);
  TreasuryMoney(value['fee']);
  accountingCheck(leg == 'source' || value['fee'] == '0.00');
  final lines = accountingRows(value['lines']);
  accountingCheck(lines.length == (value['fee'] == '0.00' ? 2 : 3));
  BigInt cents(Object? amount) =>
      BigInt.parse((amount as String).replaceAll('.', ''));
  for (final row in lines) {
    accountingCheck(
      row['line_number'] is int &&
          (row['line_number'] as int) > 0 &&
          ['1010', '1030', '1040', '5240'].contains(row['account_code']) &&
          accountingObject(row['account_snapshot'])['name'] is String,
    );
    TreasuryMoney(row['debit']);
    TreasuryMoney(row['credit']);
  }
  accountingCheck(
    lines.map((row) => row['line_number']).toSet().length == lines.length,
  );
  final transit = lines.where((row) => row['account_code'] == '1040').toList(),
      cash = lines
          .where((row) => ['1010', '1030'].contains(row['account_code']))
          .toList(),
      fees = lines.where((row) => row['account_code'] == '5240').toList();
  accountingCheck(
    transit.length == 1 &&
        cash.length == 1 &&
        fees.length == (value['fee'] == '0.00' ? 0 : 1),
  );
  accountingCheck(
    transit.single[leg == 'source' ? 'debit' : 'credit'] == value['amount'] &&
        transit.single[leg == 'source' ? 'credit' : 'debit'] == '0.00' &&
        cents(cash.single[leg == 'source' ? 'credit' : 'debit']) ==
            cents(value['amount']) + cents(value['fee']) &&
        cash.single[leg == 'source' ? 'debit' : 'credit'] == '0.00',
  );
  if (fees.isNotEmpty) {
    accountingCheck(
      fees.single['debit'] == value['fee'] && fees.single['credit'] == '0.00',
    );
  }
  return accountingObject(
    immutableTreasury({
      for (final key in [
        'book_id',
        'transfer_id',
        'leg',
        'event_id',
        'source_account_id',
        'destination_account_id',
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
