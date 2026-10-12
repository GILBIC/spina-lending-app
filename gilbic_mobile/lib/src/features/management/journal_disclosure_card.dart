import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/management/journal_disclosure_evidence.dart';
import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';

class JournalDisclosureCard extends StatelessWidget {
  const JournalDisclosureCard({required this.disclosures, super.key});
  final Map<String, dynamic> disclosures;
  @override
  Widget build(BuildContext context) {
    late final Map<String, dynamic> data;
    try {
      data = validateJournalDisclosures(disclosures);
    } on Object {
      return const Text(
        'Disclosure evidence is incomplete. Refresh before relying on these figures.',
      );
    }
    final coverage = accountingObject(data['coverage']);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Cash and noncash disclosure review',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
            Text(journalDisclosureStatusLabels[data['status']]!),
            Text(
              '${coverage['reviewed_count']} reviewed · ${coverage['excluded_count']} protected opening/closing entries · ${coverage['blocked_count']} need review · ${coverage['journal_count']} posted journals',
            ),
            for (final row in accountingRows(data['blockers']))
              Text(
                '${row['entry_number']} · ${(row['reason'] as String).replaceAll('_', ' ')}',
              ),
            const Text(
              'Reviewed noncash components',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
            if (accountingRows(data['noncash_components']).isEmpty)
              const Text('No reviewed noncash components returned.'),
            for (final row in accountingRows(data['noncash_components']))
              Text(
                '${row['entry_number']} · ${journalDisclosureLabels[row['classification']]} · PHP ${row['amount']}${row['reversal_of_entry_id'] == null ? '' : ' · Reversal of an earlier journal'}',
              ),
            const Text(
              'Financing liabilities',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
            if (accountingRows(data['financing_liabilities']).isEmpty)
              const Text(
                'No financing accounts selected in the retained policy.',
              ),
            for (final row in accountingRows(
              data['financing_liabilities'],
            )) ...[
              Text(
                '${row['account_code']} · ${row['account_name']}',
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
              for (final field in [
                ('Opening', 'opening_balance'),
                ('Cash changes', 'cash_changes'),
                ('Noncash changes', 'noncash_changes'),
                ('Opening adjustments', 'opening_adjustments'),
                ('Closing', 'closing_balance'),
                ('Difference', 'difference'),
              ])
                Text(
                  '${field.$1}: ${row[field.$2] == null ? 'Unavailable' : 'PHP ${row[field.$2]}'}',
                ),
            ],
            const Text(
              'Coverage is limited to posted journals and selected financing liabilities. Gross noncash components are shown separately; no overall noncash total is inferred.',
            ),
          ],
        ),
      ),
    );
  }
}
