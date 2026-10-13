import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';

BigInt _cents(Object? value) =>
    BigInt.parse((value as String).replaceAll('.', ''));
String _reviewText(Object? value, [int minimum = 20]) {
  accountingCheck(
    value is String &&
        value.trim().length >= minimum &&
        value.trim().length <= 2000,
    'Supply explicit evidence of $minimum–2000 characters.',
  );
  return (value as String).trim();
}

Map<String, dynamic> _impairedBoundary(Object? raw, Object? allowance) {
  final value = accountingObject(raw);
  for (final key in ['allowance_before', 'allowance_after']) {
    TreasuryMoney(value[key]);
  }
  TreasuryMoney(value['allowance_unwind'], signed: true);
  TreasuryMoney(value['impairment_adjustment'], signed: true);
  accountingCheck(
    _cents(value['allowance_before']) +
                _cents(value['allowance_unwind']) +
                _cents(value['impairment_adjustment']) ==
            _cents(value['allowance_after']) &&
        value['allowance_after'] == allowance,
  );
  return {
    for (final key in [
      'allowance_before',
      'allowance_unwind',
      'impairment_adjustment',
      'allowance_after',
    ])
      key: value[key],
  };
}

Map<String, dynamic> validateRenewalCandidate(
  Map<String, dynamic> value, {
  required String bookId,
  required String accountId,
  required String payoutId,
}) {
  accountingCheck(
    value['policy_version'] == 'native_regular_renewal_measurement_v1' &&
        value['book_id'] == bookId &&
        value['treasury_account_id'] == accountId &&
        value['payout_id'] == payoutId &&
        [
          'execution_id',
          'old_loan_id',
          'new_loan_id',
          'accounting_asset_id',
          'schedule_id',
        ].every((key) => treasuryUuid(value[key])) &&
        value['old_loan_id'] != value['new_loan_id'] &&
        accountingDate(value['effective_date']) &&
        accountingDigest(value['source_digest']),
  );
  const monetary = [
    'fresh_cash',
    'old_loan_component',
    'old_accrued_interest',
    'old_allowance',
    'old_gross_carrying',
    'revised_pv',
    'nominal_settlement',
    'contractual_total',
  ];
  for (final key in monetary) {
    TreasuryMoney(value[key]);
  }
  final rate = value['original_daily_eir'];
  accountingCheck(
    _cents(value['old_loan_component']) +
                _cents(value['old_accrued_interest']) ==
            _cents(value['old_gross_carrying']) &&
        rate is String &&
        RegExp(r'^\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$').hasMatch(rate) &&
        (double.tryParse(rate) ?? 0) > 0 &&
        (double.tryParse(rate)?.isFinite ?? false),
  );
  accountingCheck(
    !value.containsKey('predecessor_credit_impaired') ||
        value['predecessor_credit_impaired'] is bool,
  );
  final impaired = value['predecessor_credit_impaired'] == true;
  accountingCheck(
    impaired
        ? value['derecognition_blocker'] ==
              'successor_credit_adjusted_eir_policy_required'
        : value['derecognition_blocker'] == null,
  );
  final boundary = impaired
      ? _impairedBoundary(
          value['credit_impaired_boundary'],
          value['old_allowance'],
        )
      : null;
  accountingCheck(
    boundary != null || value['credit_impaired_boundary'] == null,
  );
  Map<String, dynamic>? retained;
  if (value['retained_review'] != null) {
    final row = accountingObject(value['retained_review']);
    accountingCheck(
      treasuryUuid(row['id']) &&
          [
            'modification_no_derecognition',
            'derecognition',
          ].contains(row['decision']) &&
          accountingDigest(row['measurement_digest']),
    );
    retained = {
      for (final key in ['id', 'decision', 'measurement_digest']) key: row[key],
    };
  }
  accountingCheck(!impaired || retained?['decision'] != 'derecognition');
  return accountingObject(
    immutableTreasury({
      for (final key in [
        'policy_version',
        'book_id',
        'payout_id',
        'execution_id',
        'old_loan_id',
        'new_loan_id',
        'accounting_asset_id',
        'treasury_account_id',
        'effective_date',
        'source_digest',
        'original_daily_eir',
        'schedule_id',
        'contract_reference',
        'evidence_reference',
        ...monetary,
      ])
        key: value[key],
      if (value.containsKey('predecessor_credit_impaired')) ...{
        'predecessor_credit_impaired': value['predecessor_credit_impaired'],
        'derecognition_blocker': value['derecognition_blocker'],
      },
      if (boundary != null) 'credit_impaired_boundary': boundary,
      'retained_review': retained,
    }),
  );
}

Map<String, dynamic> validateRenewalReviewInputs(
  Map<String, dynamic> value,
  Map<String, dynamic> candidate,
) {
  accountingCheck(
    [
      'modification_no_derecognition',
      'derecognition',
    ].contains(value['decision']),
    'Choose the reviewed renewal treatment explicitly.',
  );
  accountingCheck(
    value['decision'] != 'derecognition' ||
        candidate['derecognition_blocker'] == null,
    'Derecognition requires a supported initial credit status and credit-adjusted EIR policy for the successor.',
  );
  final qualitative = accountingObject(value['qualitative_assessment']);
  accountingCheck(
    qualitative['signed_contract_reviewed'] == true &&
        qualitative['cash_flow_terms_reviewed'] == true &&
        qualitative['substantial_change_assessed'] == true,
    'Confirm the signed contract bundle and both qualitative assessments.',
  );
  TreasuryMoney(value['settlement_consideration']);
  TreasuryMoney(value['settlement_rebate']);
  accountingCheck(
    _cents(value['settlement_consideration']) +
            _cents(value['settlement_rebate']) ==
        _cents(candidate['nominal_settlement']),
    'Consideration and rebate must equal the signed nominal settlement.',
  );
  final result = <String, dynamic>{
    'decision': value['decision'],
    'accounting_policy_reference': _reviewText(
      value['accounting_policy_reference'],
      1,
    ),
    'qualitative_assessment': {
      'signed_contract_reviewed': true,
      'cash_flow_terms_reviewed': true,
      'substantial_change_assessed': true,
      'decision_basis': _reviewText(qualitative['decision_basis']),
    },
    'decision_rationale': _reviewText(value['decision_rationale']),
    'settlement_consideration': value['settlement_consideration'],
    'settlement_rebate': value['settlement_rebate'],
    'settlement_basis': _reviewText(value['settlement_basis']),
    'new_initial_fair_value': null,
    'fair_value_effective_date': null,
    'fair_value_basis': null,
    'day_one_difference_rationale': null,
  };
  if (value['decision'] == 'derecognition') {
    TreasuryMoney(value['new_initial_fair_value'], positive: true);
    accountingCheck(
      value['fair_value_effective_date'] == candidate['effective_date'],
      'Fair value must use the renewal effective date.',
    );
    result.addAll({
      'new_initial_fair_value': value['new_initial_fair_value'],
      'fair_value_effective_date': value['fair_value_effective_date'],
      'fair_value_basis': _reviewText(value['fair_value_basis']),
      'day_one_difference_rationale': _reviewText(
        value['day_one_difference_rationale'],
      ),
    });
  } else {
    accountingCheck(
      [
        'new_initial_fair_value',
        'fair_value_effective_date',
        'fair_value_basis',
        'day_one_difference_rationale',
      ].every((key) => value[key] == null || value[key] == ''),
      'Modification retains the original EIR; clear new fair-value inputs.',
    );
  }
  return accountingObject(immutableTreasury(result));
}

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
  accountingCheck(
    value['accounting_policy_version'] == null ||
        value['accounting_policy_version'] ==
            'native_regular_renewal_completion_v1',
  );
  if (value['accounting_policy_version'] ==
      'native_regular_renewal_completion_v1') {
    return _validateRenewalCompletion(value);
  }
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

Map<String, dynamic> _validateRenewalCompletion(Map<String, dynamic> value) {
  accountingCheck(
    value['stage'] == 'completion' &&
        treasuryUuid(value['old_loan_id']) &&
        value['old_loan_id'] != value['loan_id'] &&
        treasuryUuid(value['accounting_asset_id']) &&
        treasuryUuid(value['renewal_review_id']) &&
        [
          'modification_no_derecognition',
          'derecognition',
        ].contains(value['renewal_decision']),
  );
  final m = accountingObject(value['measurement']);
  const amountKeys = [
    'old_gross_carrying',
    'old_allowance',
    'fresh_cash',
    'new_initial_carrying',
    'new_initial_allowance',
  ];
  for (final key in amountKeys) {
    TreasuryMoney(m[key]);
  }
  for (final key in ['old_asset_difference', 'new_asset_difference']) {
    TreasuryMoney(m[key], signed: true);
  }
  accountingCheck(
    m['fresh_cash'] == value['amount'] &&
        m['accounting_asset_continues'] ==
            (value['renewal_decision'] == 'modification_no_derecognition'),
  );
  accountingCheck(
    m['accounting_asset_continues'] == true
        ? m['new_initial_allowance'] == m['old_allowance'] &&
              m['new_asset_difference'] == '0.00'
        : m['new_initial_allowance'] == '0.00' &&
              value['accounting_asset_id'] == value['loan_id'],
  );
  accountingCheck(
    !value.containsKey('predecessor_credit_impaired') ||
        value['predecessor_credit_impaired'] is bool,
  );
  final boundary = value['predecessor_credit_impaired'] == true
      ? _impairedBoundary(value['credit_impaired_boundary'], m['old_allowance'])
      : null;
  accountingCheck(
    boundary != null
        ? value['renewal_decision'] == 'modification_no_derecognition'
        : value['credit_impaired_boundary'] == null,
  );
  final rows = accountingRows(value['lines']);
  accountingCheck(
    rows.length >= 3 &&
        rows.length <= (boundary != null ? 14 : 10) &&
        rows.map((r) => r['line_number']).toSet().length == rows.length,
  );
  const roles = <String, List<String>>{
    'renewed_asset': ['1100', 'debit', 'new'],
    'old_loan_component': ['1100', 'credit', 'old'],
    'old_accrued_interest': ['1120', 'credit', 'old'],
    'fresh_cash_transit': ['1050', 'credit', 'new'],
    'old_allowance': ['1190', 'debit', 'old'],
    'continued_allowance': ['1190', 'credit', 'new'],
  };
  for (final row in rows) {
    TreasuryMoney(row['debit']);
    TreasuryMoney(row['credit']);
    accountingCheck(
      row['line_number'] is int &&
          (row['line_number'] as int) > 0 &&
          (_cents(row['debit']) > BigInt.zero) !=
              (_cents(row['credit']) > BigInt.zero) &&
          accountingObject(row['account_snapshot'])['name'] is String,
    );
    var role = roles[row['component']];
    if ([
      'old_asset_difference',
      'new_asset_difference',
    ].contains(row['component'])) {
      final positive = _cents(m[row['component']]) >= BigInt.zero;
      role = [
        positive ? '4020' : '5010',
        positive ? 'credit' : 'debit',
        row['component'] == 'old_asset_difference' ? 'old' : 'new',
      ];
    }
    if (row['component'] == 'old_asset_elapsed_interest') {
      role = row['account_code'] == '1120'
          ? ['1120', 'debit', 'old']
          : ['4000', 'credit', 'old'];
    }
    if (boundary != null && row['component'] == 'old_asset_allowance_unwind') {
      final increase = _cents(boundary['allowance_unwind']) > BigInt.zero;
      role = row['account_code'] == '4000'
          ? ['4000', increase ? 'debit' : 'credit', 'old']
          : ['1190', increase ? 'credit' : 'debit', 'old'];
    }
    if (boundary != null &&
        row['component'] == 'old_asset_impaired_adjustment') {
      final positive = _cents(boundary['impairment_adjustment']) > BigInt.zero;
      role = row['account_code'] == '5000'
          ? ['5000', positive ? 'debit' : 'credit', 'old']
          : ['1190', positive ? 'credit' : 'debit', 'old'];
    }
    accountingCheck(role != null);
    final exactRole = role!;
    accountingCheck(
      row['account_code'] == exactRole[0] &&
          row[exactRole[1]] != '0.00' &&
          row['loan_id'] ==
              (exactRole[2] == 'old' ? value['old_loan_id'] : value['loan_id']),
    );
  }
  BigInt sum(String component, String side) => rows
      .where((r) => r['component'] == component)
      .fold(BigInt.zero, (n, r) => n + _cents(r[side]));
  for (final component in [
    ...roles.keys,
    'old_asset_difference',
    'new_asset_difference',
  ]) {
    accountingCheck(rows.where((r) => r['component'] == component).length <= 1);
  }
  accountingCheck(
    sum('renewed_asset', 'debit') == _cents(m['new_initial_carrying']) &&
        sum('fresh_cash_transit', 'credit') == _cents(m['fresh_cash']) &&
        sum('old_loan_component', 'credit') +
                sum('old_accrued_interest', 'credit') ==
            _cents(m['old_gross_carrying']) &&
        sum('old_allowance', 'debit') == _cents(m['old_allowance']) &&
        sum('continued_allowance', 'credit') ==
            _cents(m['new_initial_allowance']),
  );
  for (final key in ['old_asset_difference', 'new_asset_difference']) {
    accountingCheck(sum(key, 'credit') - sum(key, 'debit') == _cents(m[key]));
  }
  void paired(String component, BigInt? amount, Set<String> accounts) {
    final pair = rows.where((r) => r['component'] == component).toList();
    if (amount == BigInt.zero) {
      accountingCheck(pair.isEmpty);
      return;
    }
    if (amount == null && pair.isEmpty) return;
    accountingCheck(
      pair.length == 2 &&
          pair.map((r) => r['account_code']).toSet().length == 2 &&
          pair.every((r) => accounts.contains(r['account_code'])) &&
          sum(component, 'debit') == sum(component, 'credit') &&
          (amount == null || sum(component, 'debit') == amount.abs()),
    );
  }

  paired('old_asset_elapsed_interest', null, {'1120', '4000'});
  paired(
    'old_asset_allowance_unwind',
    boundary == null ? BigInt.zero : _cents(boundary['allowance_unwind']),
    {'4000', '1190'},
  );
  paired(
    'old_asset_impaired_adjustment',
    boundary == null ? BigInt.zero : _cents(boundary['impairment_adjustment']),
    {'5000', '1190'},
  );
  accountingCheck(
    sum('old_asset_elapsed_interest', 'debit') ==
            sum('old_asset_elapsed_interest', 'credit') &&
        rows.fold(
              BigInt.zero,
              (n, r) => n + _cents(r['debit']) - _cents(r['credit']),
            ) ==
            BigInt.zero,
  );
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
        'accounting_policy_version',
        'old_loan_id',
        'accounting_asset_id',
        'renewal_review_id',
        'renewal_decision',
      ])
        key: value[key],
      if (boundary != null) ...{
        'predecessor_credit_impaired': true,
        'credit_impaired_boundary': boundary,
      },
      'measurement': {
        for (final key in [
          ...amountKeys,
          'old_asset_difference',
          'new_asset_difference',
          'accounting_asset_continues',
        ])
          key: m[key],
      },
      'lines': [
        for (final row in rows)
          {
            for (final key in [
              'line_number',
              'account_code',
              'debit',
              'credit',
              'loan_id',
              'component',
            ])
              key: row[key],
            'name': accountingObject(row['account_snapshot'])['name'],
          },
      ],
    }),
  );
}
