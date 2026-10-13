import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';

Map<String, dynamic> _pick(Map<String, dynamic> value, List<String> keys) => {
  for (final key in keys) key: value[key],
};

Map<String, dynamic> validateApplicationAccounting(
  Map<String, dynamic> value, {
  required String bookId,
  required String accountId,
  required String applicationId,
}) {
  accountingCheck(
    value['book_id'] == bookId &&
        value['treasury_account_id'] == accountId &&
        value['application_id'] == applicationId &&
        [
          'receipt_id',
          'transaction_id',
          'event_id',
          'loan_id',
          'fiscal_period_id',
        ].every((key) => treasuryUuid(value[key])) &&
        accountingDate(value['posting_date']) &&
        accountingDigest(value['source_digest']),
  );
  TreasuryMoney(value['amount'], positive: true);
  final payoff =
      value['product_model'] == 'fixed_daily' &&
      value['accounting_policy_version'] ==
          'treasury_regular_original_full_payoff_v1';
  final regular =
      value['product_model'] == 'fixed_daily' &&
      [
        'treasury_regular_original_first_cash_v1',
        'treasury_regular_original_chronological_cash_v1',
        'treasury_regular_renewal_chronological_cash_v1',
        'treasury_regular_original_full_payoff_v1',
      ].contains(value['accounting_policy_version']);
  final seven =
      value['product_model'] == 'seven_by_seven' &&
      value['accounting_policy_version'] ==
          'treasury_seven_by_seven_application_v1';
  accountingCheck(regular || seven);
  final principal = regular ? '1100' : '1110';
  final income = regular ? '4000' : '4010';
  final lines = accountingRows(value['lines']);
  accountingCheck(lines.length >= 2 && lines.length <= (payoff ? 6 : 5));
  final lineNumbers = <int>{};
  final coordinates = <String, BigInt>{};
  var balance = BigInt.zero;
  for (final row in lines) {
    accountingCheck(
      row['line_number'] is int &&
          (row['line_number'] as int) > 0 &&
          lineNumbers.add(row['line_number'] as int) &&
          [
            '2200',
            principal,
            '1120',
            income,
            if (payoff) '4030',
            if (payoff) '5020',
          ].contains(row['account_code']) &&
          accountingObject(row['account_snapshot'])['name'] is String,
    );
    TreasuryMoney(row['debit']);
    TreasuryMoney(row['credit']);
    final debit = BigInt.parse((row['debit'] as String).replaceAll('.', ''));
    final credit = BigInt.parse((row['credit'] as String).replaceAll('.', ''));
    accountingCheck((debit > BigInt.zero) != (credit > BigInt.zero));
    final code = row['account_code'] as String;
    final coordinate = '$code:${debit > BigInt.zero ? 'debit' : 'credit'}';
    accountingCheck(
      !coordinates.containsKey(coordinate) &&
          (code != '2200' || credit == BigInt.zero) &&
          (code != '5020' || credit == BigInt.zero) &&
          (code != '4030' || debit == BigInt.zero) &&
          (code != principal && code != income || debit == BigInt.zero),
    );
    coordinates[coordinate] = debit + credit;
    balance += debit - credit;
  }
  BigInt amountAt(String coordinate) => coordinates[coordinate] ?? BigInt.zero;
  final amount = BigInt.parse((value['amount'] as String).replaceAll('.', ''));
  accountingCheck(
    balance == BigInt.zero &&
        amountAt('2200:debit') == amount &&
        amountAt('1120:debit') == amountAt('$income:credit') &&
        amountAt('$principal:credit') +
                amountAt('1120:credit') +
                amountAt('4030:credit') -
                amountAt('5020:debit') ==
            amount,
  );
  Map<String, dynamic>? reviewed;
  Map<String, dynamic>? closedTerm;
  if (value['closed_term'] != null) {
    final c = accountingObject(value['closed_term']);
    accountingCheck(
      regular &&
          treasuryUuid(c['closed_term_review_id']) &&
          c['closed_term_treatment'] ==
              'original_eir_through_maturity_no_extension' &&
          c['closed_term_rationale'] is String &&
          (c['closed_term_rationale'] as String).length >= 20,
    );
    closedTerm = _pick(c, [
      'closed_term_review_id',
      'closed_term_treatment',
      'closed_term_rationale',
    ]);
  }
  if (payoff) {
    final p = accountingObject(value['payoff']);
    final difference = p['settlement_difference'];
    accountingCheck(
      treasuryUuid(p['payoff_review_id']) &&
          p['payoff_treatment'] == 'full_contractual_payoff_no_rebate' &&
          p['contract_evidence_reference'] is String &&
          (p['contract_evidence_reference'] as String).length >= 3 &&
          p['payoff_review_rationale'] is String &&
          (p['payoff_review_rationale'] as String).length >= 20 &&
          difference is String &&
          RegExp(r'^-?(0|[1-9]\d{0,15})\.\d{2}$').hasMatch(difference) &&
          difference != '-0.00',
    );
    TreasuryMoney(p['gross_carrying_before']);
    accountingCheck(
      amountAt('$principal:credit') + amountAt('1120:credit') ==
              BigInt.parse(
                (p['gross_carrying_before'] as String).replaceAll('.', ''),
              ) &&
          amountAt('4030:credit') - amountAt('5020:debit') ==
              BigInt.parse((difference as String).replaceAll('.', '')) &&
          lines
                  .where(
                    (row) => ['4030', '5020'].contains(row['account_code']),
                  )
                  .length <=
              1,
    );
    reviewed = _pick(p, [
      'payoff_review_id',
      'payoff_treatment',
      'contract_evidence_reference',
      'payoff_review_rationale',
      'gross_carrying_before',
      'settlement_difference',
    ]);
  }
  return accountingObject(
    immutableTreasury({
      ..._pick(value, [
        'book_id',
        'treasury_account_id',
        'application_id',
        'receipt_id',
        'transaction_id',
        'event_id',
        'loan_id',
        'fiscal_period_id',
        'posting_date',
        'source_digest',
        'amount',
        'product_model',
        'accounting_policy_version',
      ]),
      if (payoff) 'payoff': reviewed,
      if (closedTerm != null) 'closed_term': closedTerm,
      'lines': lines
          .map(
            (row) => {
              ..._pick(row, ['line_number', 'account_code', 'debit', 'credit']),
              'name': accountingObject(row['account_snapshot'])['name'],
            },
          )
          .toList(),
    }),
  );
}

Map<String, dynamic> validateCutoffCandidate(
  Map<String, dynamic> value, {
  required String bookId,
  required String periodId,
  required String loanId,
}) {
  final blockers = value['blockers'];
  accountingCheck(
    accountingObject(value['book'])['book_id'] == bookId &&
        value['period_id'] == periodId &&
        value['loan_id'] == loanId &&
        value['ready'] is bool &&
        value['current_confirmation'] is bool &&
        value['comprehensive_source_coverage'] == false &&
        blockers is List &&
        blockers.every((item) => item is String && item.isNotEmpty) &&
        [
          'preparation_id',
          'confirmation_id',
        ].every((key) => value[key] == null || treasuryUuid(value[key])),
  );
  if (value['ready'] == false) {
    accountingCheck(
      (blockers as List).isNotEmpty &&
          [
            'source_digest',
            'measurement',
            'balances',
            'boundary',
            'cutoff_date',
            'policy_version',
            'preparation_id',
            'confirmation_id',
          ].every((key) => value[key] == null) &&
          value['current_confirmation'] == false,
    );
  } else {
    final measurement = accountingObject(value['measurement']),
        boundary = accountingObject(value['boundary']),
        balances = accountingObject(value['balances']);
    accountingCheck(
      (blockers as List).isEmpty &&
          accountingDigest(value['source_digest']) &&
          accountingDate(value['cutoff_date']) &&
          value['policy_version'] ==
              'regular_release_day_cutoff_assessment_v1' &&
          treasuryUuid(measurement['id']) &&
          measurement['date'] == value['cutoff_date'] &&
          measurement['version'] is int &&
          (measurement['version'] as int) > 0 &&
          accountingDigest(measurement['calculation_digest']) &&
          boundary['anchor_date'] == value['cutoff_date'] &&
          boundary['release_source_key'] is String &&
          (value['current_confirmation'] == false ||
              treasuryUuid(value['confirmation_id'])),
    );
    TreasuryMoney(measurement['ecl_amount']);
    for (final code in ['1100', '1110', '1120', '1190']) {
      TreasuryMoney(balances[code]);
    }
  }
  return accountingObject(
    immutableTreasury({
      ..._pick(value, [
        'period_id',
        'loan_id',
        'ready',
        'blockers',
        'source_digest',
        'current_confirmation',
        'preparation_id',
        'confirmation_id',
        'cutoff_date',
        'policy_version',
      ]),
      'measurement': value['ready'] == true
          ? _pick(accountingObject(value['measurement']), [
              'id',
              'date',
              'version',
              'calculation_digest',
              'ecl_amount',
            ])
          : null,
      'balances': value['ready'] == true
          ? _pick(accountingObject(value['balances']), [
              '1100',
              '1110',
              '1120',
              '1190',
            ])
          : null,
      'boundary': value['ready'] == true
          ? _pick(accountingObject(value['boundary']), [
              'anchor_date',
              'release_source_key',
            ])
          : null,
    }),
  );
}

Map<String, dynamic> validatePayoffCandidate(
  Map<String, dynamic> value, {
  required String bookId,
  required String accountId,
  required String applicationId,
}) {
  final difference = value['settlement_difference'];
  accountingCheck(
    value['ready'] == true &&
        value['book_id'] == bookId &&
        value['treasury_account_id'] == accountId &&
        value['application_id'] == applicationId &&
        value['blockers'] is List &&
        (value['blockers'] as List).isEmpty &&
        accountingDigest(value['source_digest']) &&
        value['contract_evidence_reference'] is String &&
        (value['contract_evidence_reference'] as String).length >= 3 &&
        (value['review_id'] == null || treasuryUuid(value['review_id'])) &&
        difference is String &&
        RegExp(r'^-?(0|[1-9]\d{0,15})\.\d{2}$').hasMatch(difference) &&
        difference != '-0.00',
  );
  TreasuryMoney(value['amount'], positive: true);
  TreasuryMoney(value['gross_carrying_before']);
  BigInt cents(String key) =>
      BigInt.parse((value[key] as String).replaceAll('.', ''));
  accountingCheck(
    cents('amount') - cents('gross_carrying_before') ==
        cents('settlement_difference'),
  );
  return accountingObject(
    immutableTreasury(
      _pick(value, [
        'ready',
        'source_digest',
        'book_id',
        'treasury_account_id',
        'application_id',
        'contract_evidence_reference',
        'amount',
        'gross_carrying_before',
        'settlement_difference',
        'review_id',
      ]),
    ),
  );
}

Map<String, dynamic> validateClosedTermCandidate(
  Map<String, dynamic> value, {
  required String bookId,
  required String accountId,
  required String applicationId,
}) {
  accountingCheck(
    value['ready'] == true &&
        value['book_id'] == bookId &&
        value['treasury_account_id'] == accountId &&
        value['application_id'] == applicationId &&
        treasuryUuid(value['loan_id']) &&
        accountingDate(value['contractual_due_date']) &&
        accountingDigest(value['source_digest']) &&
        value['blockers'] is List &&
        (value['blockers'] as List).isEmpty &&
        value['treatment'] == 'original_eir_through_maturity_no_extension' &&
        value['contract_evidence_reference'] is String &&
        (value['contract_evidence_reference'] as String).length >= 3 &&
        (value['review_id'] == null || treasuryUuid(value['review_id'])),
  );
  return accountingObject(
    immutableTreasury(
      _pick(value, [
        'ready',
        'source_digest',
        'book_id',
        'treasury_account_id',
        'application_id',
        'loan_id',
        'contractual_due_date',
        'treatment',
        'contract_evidence_reference',
        'review_id',
      ]),
    ),
  );
}

String cutoffBlockerLabel(String code) =>
    const {
      'accounting_book_identity_required':
          'Configure the accounting book identity.',
      'single_protected_regular_anchor_required':
          'One protected Regular loan release boundary is required.',
      'protected_regular_anchor_not_exact':
          'The protected loan release evidence needs reconciliation.',
      'elapsed_eir_boundary_adapter_required':
          'Elapsed interest through this cutoff still requires supported accounting proof.',
      'source_state_requires_extended_assessment_adapter':
          'This loan history requires an additional supported assessment.',
      'dated_quantitative_measurement_required':
          'An actual quantitative allowance measurement at this cutoff is required.',
      'dated_measurement_source_snapshot_mismatch':
          'The dated allowance measurement does not match its source evidence.',
      'dated_contractual_cashflow_snapshot_mismatch':
          'The retained contractual cash flows need reconciliation.',
      'dated_forward_evidence_required':
          'Forward-looking evidence valid at this cutoff is required.',
      'dated_receivable_components_not_reconciled':
          'The dated receivable components do not reconcile.',
      'dated_allowance_posting_not_reconciled':
          'The dated allowance and its posting do not reconcile.',
      'unrecognized_loan_control_journal':
          'A loan control journal requires separate accounting review.',
    }[code] ??
    code.replaceAll('_', ' ');
