import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/management/journal_disclosure_evidence.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';

const cashFlowCategories = ['operating', 'investing', 'financing', 'internal'];
const cashFlowStatusLabels = {
  'cash_definition_required': 'Cash definition required',
  'cash_definition_changed': 'Cash definition changed; review a new policy.',
  'classification_required': 'Cash classification required',
  'complete_for_posted_ledger': 'Complete for the posted ledger',
  'cash_reconciliation_required': 'Cash reconciliation required',
};

List<Map<String, dynamic>> validateCashAllocations(
  List<Map<String, dynamic>> rows,
  String expectedAmount,
) {
  TreasuryMoney(expectedAmount, signed: true);
  accountingCheck(rows.isNotEmpty && rows.length <= 20);
  final expected = BigInt.parse(expectedAmount.replaceAll('.', ''));
  accountingCheck(expected != BigInt.zero);
  var sum = BigInt.zero;
  for (final row in rows) {
    accountingCheck(cashFlowCategories.contains(row['category']));
    TreasuryMoney(row['amount'], signed: true);
    final amount = BigInt.parse((row['amount'] as String).replaceAll('.', ''));
    accountingCheck(
      amount * expected > BigInt.zero,
      'Every allocation must have the cash line direction.',
    );
    sum += amount;
  }
  accountingCheck(
    sum == expected,
    'Allocations must equal the exact signed cash line amount.',
  );
  return rows
      .map(
        (row) => <String, dynamic>{
          'category': row['category'],
          'amount': row['amount'],
        },
      )
      .toList();
}

Map<String, dynamic> validateReportingSupplement(Map<String, dynamic> value) {
  if (value['journal_disclosures'] != null) {
    validateJournalDisclosures(accountingObject(value['journal_disclosures']));
  }
  final equity = accountingObject(value['changes_in_equity']),
      cash = accountingObject(value['cash_flows']),
      notes = accountingObject(value['notes']);
  for (final key in [
    'opening_equity',
    'profit_or_loss',
    'closing_equity',
    'reconciliation_difference',
  ]) {
    TreasuryMoney(equity[key], signed: true);
  }
  accountingCheck(equity['reconciled'] is bool);
  for (final row in accountingRows(equity['other_equity_movements'])) {
    accountingCheck(
      row['account_code'] is String && row['account_name'] is String,
    );
    TreasuryMoney(row['amount'], signed: true);
  }
  accountingCheck(
    cashFlowStatusLabels.containsKey(cash['status']) &&
        cash['reconciled'] is bool &&
        cash['unclassified_line_count'] is int &&
        (cash['unclassified_line_count'] as int) >= 0,
  );
  accountingRows(cash['unclassified_lines']);
  accountingObject(cash['categories']);
  for (final key in [
    'opening_cash',
    'closing_cash',
    'net_cash_flow',
    'reconciliation_difference',
  ]) {
    accountingCheck(cash.containsKey(key));
    if (cash[key] != null) TreasuryMoney(cash[key], signed: true);
  }
  if (cash['policy'] == null) {
    accountingCheck(
      cash['status'] == 'cash_definition_required' &&
          cash['reconciled'] == false &&
          [
            'opening_cash',
            'closing_cash',
            'net_cash_flow',
            'reconciliation_difference',
          ].every((key) => cash[key] == null),
    );
  } else {
    final policy = accountingObject(cash['policy']);
    final codes = policy['cash_account_codes'];
    accountingCheck(
      codes is List &&
          codes.isNotEmpty &&
          codes.length <= 3 &&
          codes.every((code) => ['1010', '1020', '1030'].contains(code)) &&
          codes.toSet().length == codes.length,
    );
    accountingCheck(
      treasuryUuid(policy['id']) &&
          treasuryUuid(policy['book_id']) &&
          treasuryUuid(policy['fiscal_period_id']) &&
          policy['version'] is int &&
          (policy['version'] as int) > 0 &&
          policy['cash_definition_valid'] is bool,
    );
    final categories = accountingObject(cash['categories']);
    if (cash['status'] == 'cash_definition_changed') {
      accountingCheck(
        policy['cash_definition_valid'] == false &&
            cash['reconciled'] == false &&
            [
              'opening_cash',
              'closing_cash',
              'net_cash_flow',
              'reconciliation_difference',
              'opening_balance_adjustments',
            ].every((key) => cash[key] == null) &&
            categories.isEmpty,
      );
    } else {
      accountingCheck(policy['cash_definition_valid'] == true);
      TreasuryMoney(cash['opening_balance_adjustments'], signed: true);
      for (final category in ['operating', 'investing', 'financing']) {
        for (final key in ['receipts', 'payments', 'net']) {
          TreasuryMoney(
            accountingObject(categories[category])[key],
            signed: true,
          );
        }
      }
    }
  }
  for (final row in accountingRows(cash['cash_lines'])) {
    accountingCheck(
      treasuryUuid(row['journal_line_id']) &&
          treasuryUuid(row['journal_entry_id']) &&
          ['1010', '1020', '1030'].contains(row['account_code']) &&
          row['source_type'] is String &&
          row['is_opening_adjustment'] is bool &&
          (row['source_type'] != 'opening_balance' ||
              row['is_opening_adjustment'] == true) &&
          row['classification_version'] is int &&
          (row['classification_version'] as int) >= 0 &&
          (row['allocations'] == null || row['allocations'] is List),
    );
    TreasuryMoney(row['amount'], signed: true);
  }
  accountingCheck(
    [
      'reporting_policy_required',
      'retained_management_notes',
    ].contains(notes['status']),
  );
  for (final row in accountingRows(notes['items'])) {
    accountingCheck(
      [
        'title',
        'text',
        'evidence_reference',
        'evidence_digest',
      ].every((key) => row[key] is String && (row[key] as String).isNotEmpty),
    );
  }
  for (final row in accountingRows(value['noncash_activity'])) {
    accountingCheck(
      treasuryUuid(row['journal_entry_id']) &&
          accountingDate(row['posting_date']),
    );
    TreasuryMoney(row['gross_debit']);
  }
  if (value['comparative'] != null) {
    final prior = accountingObject(value['comparative']),
        period = accountingObject(
          accountingObject(value['comparative'])['period'],
        );
    accountingCheck(
      treasuryUuid(period['period_id']) && period['label'] is String,
    );
    for (final config in [
      (
        'profit_or_loss',
        ['income_lines', 'expense_lines'],
        ['total_income', 'total_expenses', 'net_income'],
      ),
      (
        'financial_position',
        ['asset_lines', 'liability_lines', 'equity_lines'],
        [
          'total_assets',
          'total_liabilities',
          'recorded_equity',
          'unclosed_earnings_to_date',
          'total_equity',
          'total_liabilities_and_equity',
        ],
      ),
    ]) {
      final part = accountingObject(prior[config.$1]);
      for (final key in config.$3) {
        TreasuryMoney(part[key], signed: true);
      }
      for (final key in config.$2) {
        for (final row in accountingRows(part[key])) {
          accountingCheck(
            row['account_code'] is String && row['account_name'] is String,
          );
          TreasuryMoney(row['amount'], signed: true);
        }
      }
    }
  }
  return accountingObject(immutableTreasury(value));
}
