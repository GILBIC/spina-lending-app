import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/management/general_journal.dart';

void main() {
  test(
    'Posted ledger aggregates can exceed the individual journal line limit',
    () {
      final balance = AccountingTrialBalance.fromPayload({
        'total_debits': '19999999999999999.98',
        'total_credits': '19999999999999999.98',
        'balanced': true,
        'lines': <Object>[],
      });
      expect(balance.totalDebits, '19999999999999999.98');
      expect(balance.totalCredits, '19999999999999999.98');
    },
  );
  test('Journal serialization preserves every cent up to the server limit', () {
    const line = JournalLineDraft(
      accountCode: '1010',
      debit: '9999999999999999.99',
      credit: '0',
    );
    expect(line.toPayload()['debit'], '9999999999999999.99');
    expect(line.toPayload()['credit'], '0.00');
    expect(
      journalCents('9999999999999999.99'),
      BigInt.parse('999999999999999999'),
    );
    expect(
      journalAmountFromCents(journalCents('0.10') + journalCents('0.20')),
      '0.30',
    );
  });
  for (final value in [
    '1.234',
    '-1',
    'NaN',
    'Infinity',
    '1e3',
    '1,000',
    '10000000000000000.00',
    'invalid',
  ]) {
    test(
      'Invalid journal amount $value never becomes a rounded or zero write',
      () {
        expect(
          () => JournalLineDraft(accountCode: '1010', debit: value).toPayload(),
          throwsFormatException,
        );
      },
    );
  }
  test('Server journal amounts remain exact when loaded for editing', () {
    final line = AccountingJournalLine.fromPayload({
      'line_number': 1,
      'account_code': '1010',
      'account_name': 'Cash',
      'description': '',
      'debit': '9007199254740991.99',
      'credit': '0.00',
    });
    expect(line.debit, '9007199254740991.99');
    expect(
      JournalLineDraft(
        accountCode: line.accountCode,
        debit: line.debit,
        credit: line.credit,
      ).toPayload()['debit'],
      '9007199254740991.99',
    );
    expect(
      () => AccountingJournalLine.fromPayload({
        'debit': 'not money',
        'credit': '0.00',
      }),
      throwsFormatException,
    );
  });
}
