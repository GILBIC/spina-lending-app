import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';

const journalDisclosureLabels = <String, String>{
  'cash_operating': 'Cash · operating',
  'cash_investing': 'Cash · investing',
  'cash_financing': 'Cash · financing',
  'cash_internal': 'Cash · internal transfer',
  'noncash_investing': 'Noncash · investing',
  'noncash_financing': 'Noncash · financing',
  'noncash_investing_financing': 'Noncash · investing and financing',
  'noncash_operating': 'Noncash · operating adjustment',
  'noncash_reclassification': 'Noncash · other reclassification',
};
const journalDisclosureStatusLabels = <String, String>{
  'complete_for_posted_ledger': 'Reviewed for the posted ledger',
  'disclosure_policy_required': 'Financing policy needs review',
  'disclosure_review_required': 'Journal disclosure review required',
  'financing_reconciliation_required': 'Financing reconciliation required',
};
BigInt _c(Object? value) =>
    BigInt.parse(TreasuryMoney(value, signed: true).text.replaceAll('.', ''));
String _m(BigInt value) {
  final digits = value.abs().toString().padLeft(3, '0');
  return '${value.isNegative ? '-' : ''}${digits.substring(0, digits.length - 2)}.${digits.substring(digits.length - 2)}';
}

void _evidence(Map<String, dynamic> part) {
  final reference = part['evidence_reference'];
  accountingCheck(
    reference is String &&
        reference.isNotEmpty &&
        reference.length <= 1000 &&
        reference.trim() == reference &&
        accountingDigest(part['evidence_digest']),
  );
}

Map<String, String> journalDisclosureRemaining(
  List<Map<String, dynamic>> lines,
  List<Map<String, dynamic>> components,
) {
  final remaining = <String, BigInt>{
    for (final line in lines)
      line['id'] as String: _c(line['debit']) + _c(line['credit']),
  };
  for (final part in components) {
    for (final key in ['debit_line_id', 'credit_line_id']) {
      accountingCheck(part[key] is String && remaining.containsKey(part[key]));
      remaining[part[key] as String] =
          remaining[part[key]]! - _c(part['amount']);
    }
  }
  return remaining.map((key, value) => MapEntry(key, _m(value)));
}

List<Map<String, dynamic>> journalDisclosureComponents(
  List<Map<String, dynamic>> lines,
  List<Map<String, dynamic>> components,
  List<dynamic> cashCodes, {
  bool verifyCashPolicy = true,
}) {
  accountingCheck(
    lines.length > 1 && components.isNotEmpty && components.length <= 1000,
  );
  final byId = <String, Map<String, dynamic>>{
    for (final line in lines) line['id'] as String: line,
  };
  accountingCheck(byId.length == lines.length);
  final pairs = <String>{},
      cash = <String, BigInt>{},
      expected = <String, BigInt>{};
  for (final part in components) {
    _evidence(part);
    accountingCheck(
      (part.keys.toList()..sort()).join(',') ==
          'amount,classification,credit_line_id,debit_line_id,evidence_digest,evidence_reference',
    );
    final debit = byId[part['debit_line_id']],
        credit = byId[part['credit_line_id']],
        category = part['classification'];
    final amount = _c(part['amount']);
    accountingCheck(
      amount > BigInt.zero &&
          debit != null &&
          credit != null &&
          category is String &&
          journalDisclosureLabels.containsKey(category),
    );
    accountingCheck(
      _c(debit!['debit']) > BigInt.zero &&
          _c(debit['credit']) == BigInt.zero &&
          _c(credit!['credit']) > BigInt.zero &&
          _c(credit['debit']) == BigInt.zero,
    );
    accountingCheck(
      pairs.add('${debit['id']}/${credit!['id']}/$category'),
      'Combine duplicate debit, credit and category portions.',
    );
    if (verifyCashPolicy) {
      accountingCheck(
        [
              debit,
              credit,
            ].any((line) => cashCodes.contains(line['account_code'])) ==
            (category as String).startsWith('cash_'),
      );
    }
    for (final pair in [(debit, BigInt.one), (credit, -BigInt.one)]) {
      if (cashCodes.contains(pair.$1['account_code'])) {
        final key = '${pair.$1['id']}/${category.substring(5)}';
        cash[key] = (cash[key] ?? BigInt.zero) + amount * pair.$2;
      }
    }
  }
  accountingCheck(
    journalDisclosureRemaining(
      lines,
      components,
    ).values.every((value) => value == '0.00'),
    'Allocate every original debit and credit exactly.',
  );
  // Retained stale components still need valid identities and exact coverage.
  // Their old cash classification is rechecked when a new review is prepared.
  if (!verifyCashPolicy) {
    return components
        .map((part) => accountingObject(immutableTreasury(part)))
        .toList(growable: false);
  }
  for (final line in lines) {
    if (cashCodes.contains(line['account_code'])) {
      final allocations = accountingRows(line['cash_allocations']);
      accountingCheck(
        allocations.isNotEmpty,
        'Review cash-flow classifications first.',
      );
      for (final part in allocations) {
        final key = '${line['id']}/${part['category']}';
        expected[key] = (expected[key] ?? BigInt.zero) + _c(part['amount']);
      }
    }
  }
  accountingCheck(
    cash.length == expected.length &&
        cash.entries.every((entry) => expected[entry.key] == entry.value),
    'Match the retained cash-flow classifications.',
  );
  return components
      .map((part) => accountingObject(immutableTreasury(part)))
      .toList(growable: false);
}

Map<String, dynamic> validateJournalDisclosures(Map<String, dynamic> value) {
  accountingCheck(
    journalDisclosureStatusLabels.containsKey(value['status']) &&
        value['scope'] == 'all_posted_journals',
  );
  final period = accountingObject(value['period']);
  accountingCheck(
    treasuryUuid(value['book_id']) &&
        treasuryUuid(period['id']) &&
        ['open', 'review', 'closed'].contains(period['status']) &&
        value['cash_account_codes'] is List,
  );
  final cashCodes = value['cash_account_codes'] as List;
  final journals = accountingRows(value['journals']),
      blockers = accountingRows(value['blockers']),
      disclosed = accountingRows(value['noncash_components']),
      financing = accountingRows(value['financing_liabilities']);
  accountingRows(value['financing_account_options']);
  final coverage = accountingObject(value['coverage']);
  for (final key in [
    'journal_count',
    'reviewed_count',
    'excluded_count',
    'blocked_count',
  ]) {
    accountingCheck(coverage[key] is int && (coverage[key] as int) >= 0);
  }
  accountingCheck(
    coverage['journal_count'] == journals.length &&
        coverage['journal_count'] ==
            coverage['reviewed_count'] +
                coverage['excluded_count'] +
                coverage['blocked_count'] &&
        coverage['blocked_count'] == blockers.length,
  );
  final policy = value['policy'] == null
      ? null
      : accountingObject(value['policy']);
  final valid = policy?['definition_valid'] == true;
  if (policy != null) {
    accountingCheck(
      treasuryUuid(policy['id']) &&
          policy['book_id'] == value['book_id'] &&
          policy['fiscal_period_id'] == period['id'] &&
          treasuryUuid(policy['reporting_policy_id']) &&
          policy['version'] is int &&
          (policy['version'] as int) > 0 &&
          policy['definition_valid'] is bool &&
          policy['financing_account_codes'] is List,
    );
    final codes = policy['financing_account_codes'] as List;
    accountingCheck(
      codes.every((code) => code is String) &&
          codes.toSet().length == codes.length,
    );
    if (valid) {
      accountingCheck(
        (codes.toList()..sort()).join(',') ==
            (financing.map((row) => row['account_code']).toList()..sort()).join(
              ',',
            ),
      );
    }
  }
  final changes = <String, Map<String, BigInt>>{
    for (final row in financing)
      row['account_code'] as String: {
        'cash': BigInt.zero,
        'noncash': BigInt.zero,
        'opening': BigInt.zero,
      },
  };
  accountingCheck(changes.length == financing.length);
  final seen = <String>{}, expectedDisclosed = <Map<String, dynamic>>[];
  var reviewed = 0, excluded = 0, blocked = 0;
  for (final row in journals) {
    accountingCheck(
      treasuryUuid(row['journal_entry_id']) &&
          seen.add(row['journal_entry_id'] as String) &&
          row['entry_number'] is String &&
          accountingDate(row['posting_date']) &&
          row['review_version'] is int &&
          (row['review_version'] as int) >= 0,
    );
    accountingCheck(
      row['reversal_of_entry_id'] == null ||
          treasuryUuid(row['reversal_of_entry_id']),
    );
    accountingCheck(
      row['source_digest'] == null || accountingDigest(row['source_digest']),
    );
    final lines = accountingRows(row['lines']);
    for (final line in lines) {
      accountingCheck(
        treasuryUuid(line['id']) &&
            line['account_code'] is String &&
            line['account_name'] is String &&
            _c(line['debit']) >= BigInt.zero &&
            _c(line['credit']) >= BigInt.zero &&
            (_c(line['debit']) == BigInt.zero) !=
                (_c(line['credit']) == BigInt.zero),
      );
    }
    if (row['components'] != null &&
        (row['source_status'] != 'current' ||
            row['review_status'] != 'current')) {
      journalDisclosureComponents(
        lines,
        accountingRows(row['components']),
        cashCodes,
        verifyCashPolicy: false,
      );
    }
    if (row['source_status'] != 'current' ||
        (row['protected_kind'] == null && row['review_status'] != 'current')) {
      blocked++;
      continue;
    }
    if (row['protected_kind'] != null) {
      accountingCheck(
        [
          'opening',
          'opening_reversal',
          'period_close',
        ].contains(row['protected_kind']),
      );
      excluded++;
      if (row['protected_kind'] != 'period_close') {
        for (final line in lines) {
          final target = changes[line['account_code']];
          if (target != null) {
            target['opening'] =
                target['opening']! + _c(line['credit']) - _c(line['debit']);
          }
        }
      }
      continue;
    }
    accountingCheck(
      (row['review_version'] as int) > 0 &&
          treasuryUuid(row['review_id']) &&
          accountingDigest(row['source_digest']),
    );
    final parts = journalDisclosureComponents(
      lines,
      accountingRows(row['components']),
      cashCodes,
    );
    reviewed++;
    final byId = {for (final line in lines) line['id']: line};
    for (final part in parts) {
      final bucket = (part['classification'] as String).startsWith('cash_')
          ? 'cash'
          : 'noncash';
      if (bucket == 'noncash') {
        expectedDisclosed.add({
          'journal_entry_id': row['journal_entry_id'],
          ...part,
        });
      }
      for (final side in [
        ('debit_line_id', -BigInt.one),
        ('credit_line_id', BigInt.one),
      ]) {
        final target = changes[byId[part[side.$1]]!['account_code']];
        if (target != null) {
          target[bucket] = target[bucket]! + _c(part['amount']) * side.$2;
        }
      }
    }
  }
  accountingCheck(
    coverage['reviewed_count'] == reviewed &&
        coverage['excluded_count'] == excluded &&
        coverage['blocked_count'] == blocked,
  );
  for (final blocker in blockers) {
    accountingCheck(
      seen.contains(blocker['journal_entry_id']) && blocker['reason'] is String,
    );
  }
  if (valid) {
    accountingCheck(expectedDisclosed.length == disclosed.length);
    for (var i = 0; i < expectedDisclosed.length; i++) {
      for (final entry in expectedDisclosed[i].entries) {
        accountingCheck(disclosed[i][entry.key] == entry.value);
      }
    }
  } else {
    accountingCheck(
      value['status'] == 'disclosure_policy_required' && disclosed.isEmpty,
    );
  }
  for (final row in financing) {
    accountingCheck(
      row['account_code'] is String &&
          row['account_name'] is String &&
          row['reconciled'] is bool,
    );
    final opening = _c(row['opening_balance']),
        closing = _c(row['closing_balance']);
    if (row['cash_changes'] == null ||
        row['noncash_changes'] == null ||
        row['opening_adjustments'] == null) {
      accountingCheck(
        row['reconciled'] == false &&
            row['difference'] == null &&
            value['status'] != 'complete_for_posted_ledger',
      );
    } else {
      final expected = changes[row['account_code']]!;
      accountingCheck(
        blocked == 0 &&
            valid &&
            _c(row['cash_changes']) == expected['cash'] &&
            _c(row['noncash_changes']) == expected['noncash'] &&
            _c(row['opening_adjustments']) == expected['opening'],
      );
      final difference =
          closing -
          opening -
          _c(row['cash_changes']) -
          _c(row['noncash_changes']) -
          _c(row['opening_adjustments']);
      accountingCheck(
        difference == _c(row['difference']) &&
            row['reconciled'] == (difference == BigInt.zero),
      );
    }
  }
  if (value['status'] == 'complete_for_posted_ledger') {
    accountingCheck(
      valid &&
          blocked == 0 &&
          financing.every((row) => row['reconciled'] == true),
    );
  }
  return accountingObject(immutableTreasury(value));
}
