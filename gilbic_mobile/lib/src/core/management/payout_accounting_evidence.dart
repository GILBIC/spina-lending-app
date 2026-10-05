import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';

Map<String, dynamic> validatePayoutAccounting(
  Map<String, dynamic> value, {
  required String bookId,
  required String accountId,
  required String payoutId,
  required String stage,
}) {
  accountingCheck(
    ['debit', 'completion'].contains(stage) &&
        value['book_id'] == bookId &&
        value['payout_id'] == payoutId &&
        value['stage'] == stage &&
        value['treasury_account_id'] == accountId &&
        [
          value['event_id'],
          value['loan_id'],
          value['client_id'],
          value['fiscal_period_id'],
        ].every(treasuryUuid) &&
        (stage == 'completion'
            ? treasuryUuid(value['disbursement_event_id'])
            : value['disbursement_event_id'] == null) &&
        accountingDate(value['posting_date']) &&
        accountingDigest(value['source_digest']),
  );
  TreasuryMoney(value['amount'], positive: true);
  TreasuryMoney(value['fee']);
  accountingCheck(stage == 'debit' || value['fee'] == '0.00');
  final lines = accountingRows(value['lines']);
  accountingCheck(lines.length == (value['fee'] == '0.00' ? 2 : 3));
  BigInt cents(Object? value) =>
      BigInt.parse((value as String).replaceAll('.', ''));
  for (final line in lines) {
    accountingCheck(
      line['line_number'] is int &&
          (line['line_number'] as int) > 0 &&
          ['1030', '1050', '1100', '5240'].contains(line['account_code']) &&
          accountingObject(line['account_snapshot'])['name'] is String,
    );
    TreasuryMoney(line['debit']);
    TreasuryMoney(line['credit']);
  }
  accountingCheck(
    lines.map((line) => line['line_number']).toSet().length == lines.length,
  );
  final transit = lines
      .where((line) => line['account_code'] == '1050')
      .toList();
  final counter = lines
      .where(
        (line) => line['account_code'] == (stage == 'debit' ? '1030' : '1100'),
      )
      .toList();
  final fees = lines.where((line) => line['account_code'] == '5240').toList();
  accountingCheck(
    transit.length == 1 &&
        counter.length == 1 &&
        fees.length == (value['fee'] == '0.00' ? 0 : 1),
  );
  accountingCheck(
    transit.single[stage == 'debit' ? 'debit' : 'credit'] == value['amount'] &&
        transit.single[stage == 'debit' ? 'credit' : 'debit'] == '0.00' &&
        cents(counter.single[stage == 'debit' ? 'credit' : 'debit']) ==
            cents(value['amount']) + cents(value['fee']) &&
        counter.single[stage == 'debit' ? 'debit' : 'credit'] == '0.00',
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
        'payout_id',
        'stage',
        'event_id',
        'loan_id',
        'client_id',
        'disbursement_event_id',
        'treasury_account_id',
        'fiscal_period_id',
        'posting_date',
        'amount',
        'fee',
        'source_digest',
      ])
        key: value[key],
      'lines': [
        for (final line in lines)
          {
            for (final key in [
              'line_number',
              'account_code',
              'debit',
              'credit',
            ])
              key: line[key],
            'name': accountingObject(line['account_snapshot'])['name'],
          },
      ],
    }),
  );
}
