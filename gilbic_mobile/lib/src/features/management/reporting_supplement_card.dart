import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/features/management/journal_disclosure_card.dart';
import 'package:gilbic_mobile/src/core/management/reporting_evidence.dart';
import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';

class ReportingSupplementCard extends StatelessWidget {
  const ReportingSupplementCard({
    this.supplement,
    this.includeComparative = true,
    super.key,
  });
  final Map<String, dynamic>? supplement;
  final bool includeComparative;
  String money(Object? value) => value == null ? 'Unavailable' : 'PHP $value';
  Widget fact(String label, Object? value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 3),
    child: Text('$label: $value'),
  );
  Widget section(String title, List<Widget> children) => Card(
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
          ...children,
        ],
      ),
    ),
  );

  @override
  Widget build(BuildContext context) {
    if (supplement == null) {
      return const Text(
        'Additional report evidence is unavailable. No complete reporting conclusion can be drawn.',
      );
    }
    late final Map<String, dynamic> data;
    try {
      data = validateReportingSupplement(supplement!);
    } on Object {
      return const Text(
        'Additional report evidence is incomplete. Refresh before relying on these reports.',
      );
    }
    final equity = accountingObject(data['changes_in_equity']),
        cash = accountingObject(data['cash_flows']),
        notes = accountingObject(data['notes']);
    final categories = accountingObject(cash['categories']);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        section('Statement of Changes in Equity', [
          fact('Opening equity', money(equity['opening_equity'])),
          fact('Profit or loss', money(equity['profit_or_loss'])),
          for (final row in accountingRows(equity['other_equity_movements']))
            fact(
              '${row['account_code']} · ${row['account_name']}',
              money(row['amount']),
            ),
          fact('Closing equity', money(equity['closing_equity'])),
          fact(
            'Reconciliation difference',
            money(equity['reconciliation_difference']),
          ),
          Text(
            equity['reconciled'] == true
                ? 'Reconciled for the posted ledger'
                : 'Equity reconciliation needs review',
          ),
          const Text(
            'Formal retained-earnings transfers are excluded to avoid counting profit twice.',
          ),
        ]),
        section('Statement of Cash Flows', [
          Text(cashFlowStatusLabels[cash['status']]!),
          fact(
            'Cash accounts',
            cash['policy'] == null
                ? 'Unavailable'
                : (accountingObject(cash['policy'])['cash_account_codes']
                          as List)
                      .join(', '),
          ),
          fact('Opening cash', money(cash['opening_cash'])),
          fact(
            'Opening balance adjustments',
            money(cash['opening_balance_adjustments']),
          ),
          fact('Closing cash', money(cash['closing_cash'])),
          fact('Net cash flow', money(cash['net_cash_flow'])),
          for (final category in ['operating', 'investing', 'financing'])
            if (categories[category] != null) ...[
              Text('${category[0].toUpperCase()}${category.substring(1)}'),
              for (final field in ['receipts', 'payments', 'net'])
                fact(
                  '${field[0].toUpperCase()}${field.substring(1)}',
                  money(accountingObject(categories[category])[field]),
                ),
            ],
          fact(
            'Reconciliation difference',
            money(cash['reconciliation_difference']),
          ),
          fact('Unclassified cash lines', cash['unclassified_line_count']),
          Text(
            cash['reconciled'] == true
                ? 'Reconciled for the posted ledger.'
                : 'Cash flow evidence needs review.',
          ),
          const Text(
            'Review cash definitions and line classifications in Reporting evidence. Internal transfers must offset within one journal or match both protected cash legs of one owned transfer in this period. Fees remain separate.',
          ),
        ]),
        section('Retained reporting notes', [
          Text(
            '${notes['framework_label'] ?? 'Reporting framework has not been supplied.'}',
          ),
          if (accountingRows(notes['items']).isEmpty)
            const Text('No retained reporting notes are available.'),
          for (final row in accountingRows(notes['items']))
            ExpansionTile(
              title: Text(row['title'] as String),
              children: [
                Text(row['text'] as String),
                fact('Evidence reference', row['evidence_reference']),
                fact('Evidence fingerprint', row['evidence_digest']),
              ],
            ),
        ]),
        if (data['journal_disclosures'] != null)
          JournalDisclosureCard(
            disclosures: accountingObject(data['journal_disclosures']),
          )
        else
          section('Journals with no cash movement', [
            const Text(
              'This inventory excludes mixed journals containing both cash and noncash activity. Further noncash disclosure may be required.',
            ),
            if (accountingRows(data['noncash_activity']).isEmpty)
              Text(
                cash['policy'] == null ||
                        cash['status'] == 'cash_definition_changed'
                    ? 'Noncash activity is unavailable until the cash definition is retained.'
                    : 'No noncash activity returned for this period.',
              ),
            for (final row in accountingRows(data['noncash_activity']))
              fact(
                '${row['entry_number'] ?? row['journal_entry_id']} · ${row['posting_date']} · Gross debit',
                money(row['gross_debit']),
              ),
          ]),
        if (includeComparative && data['comparative'] != null)
          _comparative(accountingObject(data['comparative']))
        else if (includeComparative)
          const Text('No comparative period returned.'),
        const Text(
          'These reports cover the posted ledger only. Retained notes and classifications do not certify statutory compliance or complete source recognition.',
        ),
      ],
    );
  }

  Widget _comparative(Map<String, dynamic> pack) {
    final period = accountingObject(pack['period']),
        profit = accountingObject(pack['profit_or_loss']),
        position = accountingObject(pack['financial_position']);
    return ExpansionTile(
      title: Text('Comparative period · ${period['label']}'),
      children: [
        section('Prior-period Profit or Loss', [
          for (final key in ['income_lines', 'expense_lines'])
            for (final row in accountingRows(profit[key]))
              fact(
                '${row['account_code']} · ${row['account_name']}',
                money(row['amount']),
              ),
          fact('Total income', money(profit['total_income'])),
          fact('Total expenses', money(profit['total_expenses'])),
          fact('Net income', money(profit['net_income'])),
        ]),
        section('Prior-period Financial Position', [
          for (final key in ['asset_lines', 'liability_lines', 'equity_lines'])
            for (final row in accountingRows(position[key]))
              fact(
                '${row['account_code']} · ${row['account_name']}',
                money(row['amount']),
              ),
          fact('Total assets', money(position['total_assets'])),
          fact('Total liabilities', money(position['total_liabilities'])),
          fact('Recorded equity', money(position['recorded_equity'])),
          fact(
            'Unclosed earnings',
            money(position['unclosed_earnings_to_date']),
          ),
          fact('Total equity', money(position['total_equity'])),
          fact(
            'Liabilities + equity',
            money(position['total_liabilities_and_equity']),
          ),
        ]),
        ReportingSupplementCard(
          supplement: pack['reporting_supplement'] == null
              ? null
              : accountingObject(pack['reporting_supplement']),
          includeComparative: false,
        ),
      ],
    );
  }
}
