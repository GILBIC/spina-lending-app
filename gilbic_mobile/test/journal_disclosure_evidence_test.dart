import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/management/journal_disclosure_evidence.dart';

Map<String, dynamic> disclosureContract() => Map<String, dynamic>.from(
  jsonDecode(
        File(
          'test/support/journal_disclosures_backend.json',
        ).readAsStringSync(),
      )
      as Map,
);

void main() {
  test(
    'stale reviews remain readable but malformed retained portions are rejected',
    () {
      final value = disclosureContract();
      final journal = value['journals'][0];
      journal['review_status'] = 'source_changed';
      journal['lines'][1]['cash_allocations'] = null;
      value['status'] = 'disclosure_review_required';
      value['coverage']['reviewed_count'] = 0;
      value['coverage']['blocked_count'] = 1;
      value['blockers'] = [
        {
          'journal_entry_id': journal['journal_entry_id'],
          'reason': 'source_changed',
        },
      ];
      value['noncash_components'] = [];
      for (final row in value['financing_liabilities']) {
        for (final key in [
          'cash_changes',
          'noncash_changes',
          'opening_adjustments',
          'difference',
        ]) {
          row[key] = null;
        }
        row['reconciled'] = false;
      }
      expect(validateJournalDisclosures(value)['coverage']['blocked_count'], 1);
      journal['components'][0]['debit_line_id'] =
          '00000000-0000-4000-8000-000000000099';
      expect(() => validateJournalDisclosures(value), throwsFormatException);
    },
  );
  test('actual mixed-journal contract preserves financing changes', () {
    final result = validateJournalDisclosures(disclosureContract());
    expect(result['status'], 'complete_for_posted_ledger');
    expect(
      (result['financing_liabilities'] as List).first['noncash_changes'],
      '600.00',
    );
  });
  final mutations = <void Function(Map<String, dynamic>)>[
    (v) => v['coverage']['reviewed_count']++,
    (v) => v['noncash_components'][0]['amount'] = '601.00',
    (v) => v['financing_liabilities'][0]['closing_balance'] = '601.00',
    (v) {
      v['financing_liabilities'][0]['cash_changes'] = '100.00';
      v['financing_liabilities'][0]['noncash_changes'] = '500.00';
    },
    (v) => v['journals'][0]['components'][0]['amount'] = '399.00',
    (v) => v['journals'][0]['lines'][1]['cash_allocations'][0]['category'] =
        'financing',
    (v) => v['journals'][0]['components'][1]['amount'] = 600,
    (v) => v['journals'][0]['components'][1]['amount'] = '600.001',
    (v) => v['journals'][0]['components'][1]['amount'] = '-600.00',
    (v) => v['journals'][0]['components'][0]['classification'] =
        'noncash_investing',
    (v) => v['journals'][0]['components'].removeLast(),
  ];
  for (var i = 0; i < mutations.length; i++) {
    test('altered report is rejected $i', () {
      final value = disclosureContract();
      mutations[i](value);
      expect(() => validateJournalDisclosures(value), throwsFormatException);
    });
  }
  test('remaining allocations preserve exact cents', () {
    final journal = disclosureContract()['journals'][0] as Map<String, dynamic>;
    final result = journalDisclosureRemaining(
      (journal['lines'] as List).cast<Map<String, dynamic>>(),
      [(journal['components'] as List).first as Map<String, dynamic>],
    );
    expect(result.values.toList(), ['600.00', '0.00', '600.00']);
  });
}
