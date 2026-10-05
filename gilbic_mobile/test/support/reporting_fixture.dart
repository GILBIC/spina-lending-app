String reportingId(int n) =>
    '00000000-0000-4000-8000-${n.toString().padLeft(12, '0')}';

Map<String, dynamic> reportingTestSupplement({bool withPolicy = false}) {
  final notes = <Map<String, dynamic>>[
    {
      'title': 'Borrowing terms',
      'text': 'Actual retained terms.',
      'evidence_reference': 'Agreement A',
      'evidence_digest': 'a' * 64,
    },
  ];
  final policy = withPolicy
      ? {
          'id': reportingId(31),
          'book_id': reportingId(2),
          'fiscal_period_id': reportingId(30),
          'version': 2,
          'cash_definition_valid': true,
          'cash_account_codes': ['1010'],
          'framework_label': 'Actual reporting basis',
          'notes': notes,
          'evidence_reference': 'Policy record',
          'evidence_digest': 'a' * 64,
        }
      : null;
  return {
    'changes_in_equity': {
      'opening_equity': '90071992547409.93',
      'profit_or_loss': '10.00',
      'other_equity_movements': [],
      'closing_equity': '90071992547419.93',
      'reconciliation_difference': '0.00',
      'reconciled': true,
    },
    'cash_flows': {
      'policy': policy,
      'status': withPolicy
          ? 'classification_required'
          : 'cash_definition_required',
      'opening_cash': withPolicy ? '200.00' : null,
      'closing_cash': withPolicy ? '100.00' : null,
      'opening_balance_adjustments': withPolicy ? '0.00' : null,
      'net_cash_flow': null,
      'reconciliation_difference': null,
      'reconciled': false,
      'categories': withPolicy
          ? {
              for (final category in ['operating', 'investing', 'financing'])
                category: {
                  'receipts': '0.00',
                  'payments': '0.00',
                  'net': '0.00',
                },
            }
          : <String, dynamic>{},
      'cash_lines': withPolicy
          ? [
              {
                'journal_line_id': reportingId(32),
                'journal_entry_id': reportingId(33),
                'account_code': '1010',
                'entry_number': 'GJ-33',
                'amount': '-100.00',
                'source_type': 'manual',
                'is_opening_adjustment': false,
                'classification_version': 3,
                'allocations': null,
              },
            ]
          : [],
      'unclassified_lines': [],
      'unclassified_line_count': withPolicy ? 1 : 0,
    },
    'notes': {
      'status': withPolicy
          ? 'retained_management_notes'
          : 'reporting_policy_required',
      'framework_label': withPolicy ? 'Actual reporting basis' : null,
      'items': withPolicy ? notes : [],
    },
    'noncash_activity': [],
    'comparative': null,
  };
}
