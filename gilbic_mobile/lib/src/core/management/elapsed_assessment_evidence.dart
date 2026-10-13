import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';

const elapsedAssessmentBase =
    '$sourceAccountingBase/period-elapsed-assessments';
Map<String, dynamic> _pick(Map<String, dynamic> value, List<String> keys) => {
  for (final key in keys) key: value[key],
};
BigInt _cents(Object? value, {bool signed = false}) =>
    BigInt.parse(TreasuryMoney(value, signed: signed).text.replaceAll('.', ''));
void _verifyExpectedLoss(Map<String, dynamic> v) {
  final raw = v['weighted_expected_cash_present_value_raw'];
  accountingCheck(
    raw is String &&
        RegExp(r'^(0|[1-9]\d{0,15})(\.\d{1,1000})?$').hasMatch(raw),
  );
  final parts = (raw as String).split('.'),
      fraction = parts.length == 1 ? '' : parts[1],
      places = fraction.length < 2 ? 2 : fraction.length;
  final factor = BigInt.from(10).pow(places - 2),
      pv = BigInt.parse(parts[0] + fraction.padRight(places, '0'));
  BigInt round(BigInt n) => (n + factor ~/ BigInt.from(2)) ~/ factor;
  final gross = _cents(v['gross_carrying_amount']), delta = gross * factor - pv;
  accountingCheck(
    _cents(v['expected_cash_present_value']) == round(pv) &&
        _cents(v['ecl_amount']) ==
            (delta > BigInt.zero ? round(delta) : BigInt.zero),
  );
  final shown = gross - _cents(v['expected_cash_present_value']);
  accountingCheck(
    _cents(v['ecl_amount']) ==
        (shown > BigInt.zero ? shown : BigInt.zero) +
            _cents(v['currency_rounding_adjustment'], signed: true),
  );
}

String _text(Object? value, int min, int max) {
  accountingCheck(
    value is String && value.trim().length >= min && value.trim().length <= max,
    'Supply a reference or rationale of $min–$max characters.',
  );
  return (value as String).trim();
}

Map<String, dynamic>? _eligibleRisk(Object? value, Object? asOf) {
  if (value == null) return null;
  final v = accountingObject(value), reviewId = v['id'];
  final timestamp = v['reviewed_at'];
  accountingCheck(
    reviewId is int &&
        reviewId > 0 &&
        reviewId <= 9007199254740991 &&
        [
          'stage_1_12_month',
          'stage_2_lifetime',
          'stage_3_credit_impaired',
        ].contains(v['stage_label']) &&
        v['default_label'] is bool &&
        (v['stage_label'] != 'stage_1_12_month' ||
            v['default_label'] == false) &&
        [
          'none',
          'cured',
          'cash_recovery_observed',
        ].contains(v['recovery_label']) &&
        accountingDate(v['as_of_date']) &&
        v['as_of_date'] == asOf &&
        timestamp is String &&
        RegExp(
          r'^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$',
        ).hasMatch(timestamp) &&
        DateTime.tryParse(timestamp) != null &&
        [
          'contractual_dpd',
          'protected_collection_history',
          'verified_source_document',
          'verified_qualitative_credit_event',
          'authoritative_external_evidence',
        ].contains(v['primary_evidence_basis']),
  );
  _text(v['evidence_reference'], 1, 300);
  if (v.containsKey('write_off_label')) {
    accountingCheck(
      [
        'none',
        'supported_no_reasonable_expectation_of_recovery',
      ].contains(v['write_off_label']),
    );
  }
  return {
    ..._pick(v, [
      'id',
      'stage_label',
      'default_label',
      'recovery_label',
      'reviewed_at',
      'as_of_date',
      'evidence_reference',
      'primary_evidence_basis',
    ]),
    if (v.containsKey('write_off_label'))
      'write_off_label': v['write_off_label'],
  };
}

bool _reviewedOpening(Map<String, dynamic> v, Object? asOf) {
  if (!accountingDate(v['opening_cutoff_date']) || !accountingDate(asOf)) {
    return false;
  }
  final compared = (v['opening_cutoff_date'] as String).compareTo(
    asOf as String,
  );
  return (treasuryUuid(v['opening_assessment_id']) &&
          v['opening_renewal_review_id'] == null &&
          compared < 0) ||
      (v['opening_assessment_id'] == null &&
          treasuryUuid(v['opening_renewal_review_id']) &&
          compared <= 0);
}

Map<String, dynamic> _renewalOpeningField(Map<String, dynamic> v) => {
  if (v.containsKey('opening_renewal_review_id'))
    'opening_renewal_review_id': v['opening_renewal_review_id'],
};

Map<String, dynamic>? _impairedInterest(Object? value, Object? asOf) {
  if (value == null) return null;
  final v = accountingObject(value);
  accountingCheck(accountingDate(asOf));
  for (final key in ['gross_interest', 'net_interest']) {
    TreasuryMoney(v[key]);
  }
  final unwind = _cents(v['allowance_unwind'], signed: true);
  final hasRounding = v.containsKey('currency_rounding_adjustment');
  if (hasRounding) {
    final adjustment = _cents(v['currency_rounding_adjustment'], signed: true);
    accountingCheck(
      unwind - adjustment >= BigInt.zero &&
          _cents(v['gross_interest']) - adjustment >= BigInt.zero,
    );
  } else {
    accountingCheck(unwind >= BigInt.zero);
  }
  accountingCheck(
    _cents(v['gross_interest']) - _cents(v['net_interest']) == unwind,
  );
  if (v['basis'] == 'gross_before_initial_impaired_cutoff') {
    accountingCheck(
      v['opening_assessment_id'] == null &&
          v['opening_renewal_review_id'] == null &&
          v['opening_cutoff_date'] == null &&
          v['impairment_boundary_date'] == asOf &&
          v['allowance_unwind'] == '0.00',
    );
  } else {
    accountingCheck(
      v['basis'] == 'original_eir_on_reviewed_net_carrying' &&
          _reviewedOpening(v, asOf) &&
          v['impairment_boundary_date'] == v['opening_cutoff_date'],
    );
  }
  return {
    ..._pick(v, [
      'basis',
      'opening_assessment_id',
      'opening_cutoff_date',
      'impairment_boundary_date',
      'gross_interest',
      'net_interest',
      'allowance_unwind',
    ]),
    ..._renewalOpeningField(v),
    if (hasRounding)
      'currency_rounding_adjustment': v['currency_rounding_adjustment'],
  };
}

Map<String, dynamic> validateElapsedPreparation(
  Map<String, dynamic> value, {
  required String bookId,
  required String periodId,
  required String loanId,
  Map<String, dynamic>? candidate,
}) {
  final renewed =
      value['policy_version'] == 'regular_exact_renewal_zero_ecl_v1';
  final settled =
      renewed || value['policy_version'] == 'regular_exact_payoff_zero_ecl_v1';
  final reviewedStage1 =
      value['policy_version'] ==
      'historical_native_reviewed_12_month_cash_shortfall_v1';
  final lifetime =
      reviewedStage1 ||
      value['policy_version'] == 'historical_native_lifetime_cash_shortfall_v1';
  accountingCheck(
    value['book_id'] == bookId &&
        value['period_id'] == periodId &&
        value['loan_id'] == loanId &&
        treasuryUuid(value['preparation_id']) &&
        accountingDigest(value['source_digest']) &&
        accountingDigest(value['confirmation_digest']) &&
        accountingDate(value['as_of_date']) &&
        (settled ||
            lifetime ||
            value['policy_version'] ==
                'historical_original_timing_cash_shortfall_v1') &&
        value['comprehensive_source_coverage'] == false &&
        value['scenario_count'] is int &&
        (settled
            ? value['scenario_count'] == 0
            : (value['scenario_count'] as int) >= 2 &&
                  (value['scenario_count'] as int) <= 20),
  );
  final timestamp = value['calculated_at'];
  accountingCheck(
    timestamp is String &&
        RegExp(
          r'^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$',
        ).hasMatch(timestamp) &&
        DateTime.tryParse(timestamp) != null,
  );
  for (final key in [
    'cumulative_interest',
    'incremental_interest',
    'prior_allowance',
    'ecl_amount',
  ]) {
    TreasuryMoney(value[key]);
  }
  final impaired = _impairedInterest(
    value['credit_impaired_interest'],
    value['as_of_date'],
  );
  accountingCheck(
    _cents(value['ecl_amount']) -
            _cents(value['prior_allowance']) -
            (impaired == null
                ? BigInt.zero
                : _cents(impaired['allowance_unwind'], signed: true)) ==
        _cents(value['allowance_delta'], signed: true),
  );
  if (candidate != null) {
    accountingCheck(
      canonicalTreasury(impaired) ==
          canonicalTreasury(candidate['credit_impaired_interest']),
    );
    final eir = accountingObject(candidate['eir']);
    accountingCheck(
      value['source_digest'] == candidate['source_digest'] &&
          value['as_of_date'] == candidate['as_of_date'] &&
          value['cumulative_interest'] == eir['cumulative_interest'] &&
          value['incremental_interest'] == eir['incremental_interest'] &&
          value['prior_allowance'] == candidate['prior_allowance'],
    );
  }
  final Map<String, dynamic> reviewInputs;
  if (settled) {
    final flag = renewed
        ? 'settled_by_exact_renewal'
        : 'settled_by_exact_payoff';
    final otherFlag = renewed
        ? 'settled_by_exact_payoff'
        : 'settled_by_exact_renewal';
    final key = renewed ? 'renewal_review_id' : 'payoff_review_id';
    accountingCheck(
      value[flag] == true &&
          value[otherFlag] != true &&
          treasuryUuid(value[key]) &&
          value['ecl_amount'] == '0.00' &&
          value['incremental_interest'] == '0.00',
    );
    if (candidate != null) {
      accountingCheck(candidate[flag] == true && candidate[key] == value[key]);
    }
    reviewInputs = renewed
        ? validateElapsedRenewedInputs(accountingObject(value['review_inputs']))
        : validateElapsedSettledInputs(
            accountingObject(value['review_inputs']),
          );
    accountingCheck(reviewInputs[key] == value[key]);
  } else if (lifetime) {
    accountingCheck(candidate != null);
    final risk = accountingObject(candidate!['eligible_credit_risk_review']);
    accountingCheck(
      value['settled_by_exact_payoff'] != true &&
          value['settled_by_exact_renewal'] != true &&
          candidate['settled_by_exact_payoff'] != true &&
          candidate['settled_by_exact_renewal'] != true &&
          risk['id'] == value['credit_risk_review_id'] &&
          risk['stage_label'] == value['stage_label'] &&
          risk['default_label'] == value['default_label'] &&
          value['loss_horizon'] == (reviewedStage1 ? '12_month' : 'lifetime') &&
          (reviewedStage1
              ? value['stage_label'] == 'stage_1_12_month'
              : [
                  'stage_2_lifetime',
                  'stage_3_credit_impaired',
                ].contains(value['stage_label'])),
    );
    final stage3 = value['stage_label'] == 'stage_3_credit_impaired';
    accountingCheck(
      value['loss_basis'] ==
          (stage3
              ? 'gross_carrying_less_expected_pv'
              : 'contractual_cash_shortfall'),
    );
    if (stage3) {
      accountingCheck(
        impaired != null &&
            value['gross_carrying_amount'] ==
                candidate['gross_carrying_amount'],
      );
      _verifyExpectedLoss(value);
    }
    reviewInputs = validateElapsedRiskInputs(
      accountingObject(value['review_inputs']),
      candidate,
    );
    accountingCheck(
      reviewInputs['credit_risk_review_id'] == value['credit_risk_review_id'] &&
          (reviewInputs['scenarios'] as List).length == value['scenario_count'],
    );
  } else {
    accountingCheck(
      value['settled_by_exact_payoff'] != true &&
          candidate?['settled_by_exact_payoff'] != true &&
          value['settled_by_exact_renewal'] != true &&
          candidate?['settled_by_exact_renewal'] != true &&
          candidate?['eligible_credit_risk_review'] == null &&
          impaired == null,
    );
    final reviewed = accountingObject(value['review_inputs']),
        risk = accountingObject(
          accountingObject(value['review_inputs'])['risk_review'],
        );
    accountingCheck(
      risk['as_of_date'] == value['as_of_date'] &&
          risk['stage_label'] == 'stage_1_12_month' &&
          risk['default_label'] == false &&
          risk['write_off_label'] == 'none' &&
          risk['recovery_label'] == 'none' &&
          risk['primary_evidence_basis'] == 'contractual_dpd',
    );
    reviewInputs = validateElapsedInputs({
      ...reviewed,
      'evidence_reference': risk['evidence_reference'],
      'review_note': risk['review_note'],
    }, value['as_of_date'] as String);
    accountingCheck(
      (reviewInputs['scenarios'] as List).length == value['scenario_count'],
    );
  }
  return accountingObject(
    immutableTreasury({
      ..._pick(value, [
        'preparation_id',
        'book_id',
        'period_id',
        'loan_id',
        'as_of_date',
        'source_digest',
        'confirmation_digest',
        'calculated_at',
        'policy_version',
        'cumulative_interest',
        'incremental_interest',
        'prior_allowance',
        'ecl_amount',
        'allowance_delta',
        'scenario_count',
        'comprehensive_source_coverage',
      ]),
      'review_inputs': reviewInputs,
      if (impaired != null) 'credit_impaired_interest': impaired,
      if (lifetime)
        ..._pick(value, [
          'credit_risk_review_id',
          'stage_label',
          'default_label',
          'loss_horizon',
          'loss_basis',
        ]),
      if (lifetime && value['stage_label'] == 'stage_3_credit_impaired')
        ..._pick(value, [
          'gross_carrying_amount',
          'expected_cash_present_value',
          'weighted_expected_cash_present_value_raw',
          'currency_rounding_adjustment',
        ]),
      if (settled && !renewed) ...{
        'settled_by_exact_payoff': true,
        'payoff_review_id': value['payoff_review_id'],
      },
      if (renewed) ...{
        'settled_by_exact_renewal': true,
        'renewal_review_id': value['renewal_review_id'],
      },
    }),
  );
}

Map<String, dynamic> validateElapsedCandidate(
  Map<String, dynamic> value, {
  required String bookId,
  required String periodId,
  required String loanId,
}) {
  accountingCheck(
    accountingObject(value['book'])['book_id'] == bookId &&
        value['period_id'] == periodId &&
        value['loan_id'] == loanId &&
        value['ready'] is bool &&
        value['current_confirmation'] is bool &&
        value['blockers'] is List &&
        (value['blockers'] as List).every((x) => x is String) &&
        value['comprehensive_source_coverage'] == false,
  );
  final out = _pick(value, [
    'period_id',
    'loan_id',
    'ready',
    'current_confirmation',
    'as_of_date',
    'source_digest',
    'gross_carrying_amount',
    'prior_allowance',
    'days_past_due',
    'comprehensive_source_coverage',
    'blockers',
  ]);
  out['eir'] = null;
  out['preparation'] = null;
  accountingCheck(
    value['impaired_cash_reviews'] == null ||
        value['impaired_cash_reviews'] is List,
  );
  final cashRows = accountingRows(
    value['impaired_cash_reviews'] ?? [],
  ).map(_impairedCashRow).toList();
  accountingCheck(
    cashRows.map((r) => r['application_id']).toSet().length == cashRows.length,
  );
  out['impaired_cash_reviews'] = cashRows;
  out['eligible_credit_risk_review'] = _eligibleRisk(
    value['eligible_credit_risk_review'],
    value['as_of_date'],
  );
  final impaired = _impairedInterest(
    value['credit_impaired_interest'],
    value['as_of_date'],
  );
  if (impaired != null) {
    accountingCheck(value['ready'] == true);
    out['credit_impaired_interest'] = impaired;
  }
  if (out['eligible_credit_risk_review'] != null) {
    accountingCheck(
      value['ready'] == true &&
          value['settled_by_exact_payoff'] != true &&
          value['settled_by_exact_renewal'] != true,
    );
    if (out['eligible_credit_risk_review']['stage_label'] ==
        'stage_3_credit_impaired') {
      accountingCheck(impaired != null);
    }
  }
  accountingCheck(
    !value.containsKey('settled_by_exact_payoff') ||
        value['settled_by_exact_payoff'] is bool,
  );
  out['settled_by_exact_payoff'] = value['settled_by_exact_payoff'] == true;
  out['payoff_review_id'] = value['payoff_review_id'];
  if (out['settled_by_exact_payoff'] == true) {
    accountingCheck(
      value['ready'] == true &&
          treasuryUuid(value['payoff_review_id']) &&
          value['gross_carrying_amount'] == '0.00' &&
          accountingObject(value['eir'])['incremental_interest'] == '0.00',
    );
  } else {
    accountingCheck(value['payoff_review_id'] == null);
  }
  accountingCheck(
    !value.containsKey('settled_by_exact_renewal') ||
        value['settled_by_exact_renewal'] is bool,
  );
  out['settled_by_exact_renewal'] = value['settled_by_exact_renewal'] == true;
  out['renewal_review_id'] = value['renewal_review_id'];
  if (out['settled_by_exact_renewal'] == true) {
    accountingCheck(
      value['ready'] == true &&
          out['settled_by_exact_payoff'] != true &&
          treasuryUuid(value['renewal_review_id']) &&
          value['gross_carrying_amount'] == '0.00' &&
          accountingObject(value['eir'])['incremental_interest'] == '0.00',
    );
  } else {
    accountingCheck(value['renewal_review_id'] == null);
  }
  if (value['ready'] == true) {
    accountingCheck(
      (value['blockers'] as List).isEmpty &&
          accountingDate(value['as_of_date']) &&
          accountingDigest(value['source_digest']) &&
          value['days_past_due'] is int &&
          (value['days_past_due'] as int) >= 0,
    );
    TreasuryMoney(value['gross_carrying_amount']);
    TreasuryMoney(value['prior_allowance']);
    final eir = accountingObject(value['eir']);
    accountingCheck(
      _cents(eir['prior_recognized_interest']) +
              _cents(eir['incremental_interest']) ==
          _cents(eir['cumulative_interest']),
    );
    out['eir'] = _pick(eir, [
      'cumulative_interest',
      'prior_recognized_interest',
      'incremental_interest',
    ]);
    if (value['preparation'] != null) {
      out['preparation'] = validateElapsedPreparation(
        accountingObject(value['preparation']),
        bookId: bookId,
        periodId: periodId,
        loanId: loanId,
        candidate: out,
      );
    }
    accountingCheck(
      value['current_confirmation'] != true || out['preparation'] != null,
    );
  } else {
    accountingCheck(
      value['current_confirmation'] == false &&
          value['source_digest'] == null &&
          value['eir'] == null &&
          value['gross_carrying_amount'] == null &&
          value['prior_allowance'] == null &&
          value['preparation'] == null,
    );
  }
  return accountingObject(immutableTreasury(out));
}

Map<String, dynamic> validateElapsedSettledInputs(Map<String, dynamic> value) {
  accountingCheck(
    treasuryUuid(value['payoff_review_id']),
    'Exact posted payoff review is required.',
  );
  return accountingObject(
    immutableTreasury({
      'payoff_review_id': value['payoff_review_id'],
      'review_rationale': _text(value['review_rationale'], 20, 2000),
    }),
  );
}

Map<String, dynamic> validateElapsedRenewedInputs(Map<String, dynamic> value) {
  accountingCheck(
    treasuryUuid(value['renewal_review_id']),
    'Exact posted renewal review is required.',
  );
  return accountingObject(
    immutableTreasury({
      'renewal_review_id': value['renewal_review_id'],
      'review_rationale': _text(value['review_rationale'], 20, 2000),
    }),
  );
}

Map<String, dynamic> _impairedCashRow(Map<String, dynamic> v) {
  accountingCheck(
    treasuryUuid(v['application_id']) &&
        accountingDate(v['as_of_date']) &&
        v['ready'] is bool &&
        v['blockers'] is List &&
        (v['blockers'] as List).every((x) => x is String) &&
        v['current_confirmation'] is bool &&
        (v['retained_review_id'] == null ||
            treasuryUuid(v['retained_review_id'])),
  );
  if (v['ready'] == true) {
    accountingCheck(
      (v['blockers'] as List).isEmpty &&
          accountingDigest(v['source_digest']) &&
          _reviewedOpening(v, v['as_of_date']) &&
          (v['current_confirmation'] != true ||
              treasuryUuid(v['retained_review_id'])),
    );
    TreasuryMoney(v['gross_carrying_amount']);
  } else {
    accountingCheck(
      v['source_digest'] == null &&
          v['gross_carrying_amount'] == null &&
          v['current_confirmation'] == false,
    );
  }
  return {
    ..._pick(v, [
      'application_id',
      'as_of_date',
      'ready',
      'blockers',
      'source_digest',
      'gross_carrying_amount',
      'opening_assessment_id',
      'opening_cutoff_date',
      'retained_review_id',
      'current_confirmation',
    ]),
    ..._renewalOpeningField(v),
  };
}

Map<String, dynamic> validateImpairedCashCandidate(
  Map<String, dynamic> v, {
  required String bookId,
  required String periodId,
  required String loanId,
  required String applicationId,
}) {
  accountingCheck(
    accountingObject(v['book'])['book_id'] == bookId &&
        v['period_id'] == periodId &&
        v['loan_id'] == loanId &&
        v['application_id'] == applicationId,
  );
  final out = {
    ..._pick(v, ['period_id', 'loan_id']),
    ..._impairedCashRow(v),
    'review': null,
  };
  if (v['review'] != null) {
    accountingCheck(v['ready'] == true);
    out['review'] = validateImpairedCashReview(
      accountingObject(v['review']),
      bookId: bookId,
      periodId: periodId,
      loanId: loanId,
      applicationId: applicationId,
      candidate: out,
    );
    accountingCheck(
      out['retained_review_id'] == accountingObject(out['review'])['review_id'],
    );
  }
  accountingCheck(v['current_confirmation'] != true || out['review'] != null);
  return accountingObject(immutableTreasury(out));
}

Map<String, dynamic> validateImpairedCashInputs(
  Map<String, dynamic> v,
  Map<String, dynamic> c,
) {
  accountingCheck(c['ready'] == true);
  return accountingObject(
    immutableTreasury({
      'scenarios': _elapsedScenarios(v, c['as_of_date'] as String),
      'review_rationale': _text(v['review_rationale'], 20, 2000),
    }),
  );
}

Map<String, dynamic> validateImpairedCashReview(
  Map<String, dynamic> v, {
  required String bookId,
  required String periodId,
  required String loanId,
  required String applicationId,
  required Map<String, dynamic> candidate,
}) {
  final c = candidate, timestamp = v['calculated_at'];
  accountingCheck(
    v['book_id'] == bookId &&
        v['period_id'] == periodId &&
        v['loan_id'] == loanId &&
        v['application_id'] == applicationId &&
        treasuryUuid(v['review_id']) &&
        v['as_of_date'] == c['as_of_date'] &&
        timestamp is String &&
        RegExp(
          r'^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$',
        ).hasMatch(timestamp) &&
        DateTime.tryParse(timestamp) != null &&
        v['source_digest'] == c['source_digest'] &&
        accountingDigest(v['confirmation_digest']) &&
        v['policy_version'] == 'native_impaired_cash_expected_receipts_v1' &&
        v['loss_basis'] == 'gross_carrying_less_expected_pv' &&
        v['opening_assessment_id'] == c['opening_assessment_id'] &&
        v['opening_renewal_review_id'] == c['opening_renewal_review_id'] &&
        v['opening_cutoff_date'] == c['opening_cutoff_date'] &&
        v['gross_carrying_amount'] == c['gross_carrying_amount'],
  );
  _verifyExpectedLoss(v);
  final inputs = validateImpairedCashInputs(
    accountingObject(v['review_inputs']),
    c,
  );
  accountingCheck(v['scenario_count'] == (inputs['scenarios'] as List).length);
  return accountingObject(
    immutableTreasury({
      ..._pick(v, [
        'review_id',
        'book_id',
        'period_id',
        'loan_id',
        'application_id',
        'as_of_date',
        'calculated_at',
        'source_digest',
        'confirmation_digest',
        'policy_version',
        'loss_basis',
        'opening_assessment_id',
        'opening_cutoff_date',
        'gross_carrying_amount',
        'expected_cash_present_value',
        'weighted_expected_cash_present_value_raw',
        'currency_rounding_adjustment',
        'ecl_amount',
        'scenario_count',
      ]),
      ..._renewalOpeningField(v),
      'review_inputs': inputs,
    }),
  );
}

Map<String, dynamic> validateElapsedRiskInputs(
  Map<String, dynamic> value,
  Map<String, dynamic> candidate,
) {
  final risk = _eligibleRisk(
    candidate['eligible_credit_risk_review'],
    candidate['as_of_date'],
  );
  accountingCheck(
    risk != null && value['credit_risk_review_id'] == risk['id'],
    'Select the exact retained credit-risk review for this cutoff.',
  );
  return accountingObject(
    immutableTreasury({
      'credit_risk_review_id': risk!['id'],
      'scenarios': _elapsedScenarios(value, candidate['as_of_date'] as String),
      'review_rationale': _text(value['review_rationale'], 20, 2000),
    }),
  );
}

List<Map<String, dynamic>> _elapsedScenarios(
  Map<String, dynamic> value,
  String asOf,
) {
  accountingCheck(accountingDate(asOf));
  final raw = accountingRows(value['scenarios']);
  accountingCheck(
    raw.length >= 2 && raw.length <= 20,
    'Provide 2–20 evidence-backed receipt scenarios.',
  );
  var sum = BigInt.zero;
  final keys = <String>{};
  final scenarios = raw.map((s) {
    final key = _text(s['scenario_key'], 1, 80);
    accountingCheck(keys.add(key), 'Scenario names must be distinct.');
    final probability = s['probability'];
    accountingCheck(
      probability is String &&
          RegExp(r'^(0|1)(\.\d{1,12})?$').hasMatch(probability),
      'Enter probability as a decimal from 0 to 1, with at most 12 decimal places.',
    );
    final parts = (probability as String).split('.');
    final units = BigInt.parse(
      parts[0] + (parts.length == 2 ? parts[1] : '').padRight(12, '0'),
    );
    accountingCheck(units > BigInt.zero && units <= BigInt.from(1000000000000));
    sum += units;
    final evidence = s['forward_evidence_ids'];
    accountingCheck(
      evidence is List &&
          evidence.isNotEmpty &&
          evidence.length <= 100 &&
          evidence.every(treasuryUuid) &&
          evidence.toSet().length == evidence.length,
      'Select distinct retained forecast evidence.',
    );
    final dates = <String>{};
    final flows = accountingRows(s['expected_cash_flows']);
    accountingCheck(flows.length <= 3660);
    final receipts = flows.map((f) {
      accountingCheck(
        accountingDate(f['cash_date']) &&
            (f['cash_date'] as String).compareTo(asOf) >= 0 &&
            dates.add(f['cash_date'] as String),
        'Receipt dates must be valid, distinct within each scenario, and on or after the cutoff.',
      );
      TreasuryMoney(f['amount'], positive: true);
      return _pick(f, ['cash_date', 'amount']);
    }).toList();
    return {
      'scenario_key': key,
      'probability': probability,
      'evidence_reference': _text(s['evidence_reference'], 3, 1000),
      'management_rationale': _text(s['management_rationale'], 20, 2000),
      'forward_evidence_ids': evidence,
      'expected_cash_flows': receipts,
    };
  }).toList();
  accountingCheck(
    sum == BigInt.from(1000000000000),
    'Scenario probabilities must total exactly 1.',
  );
  return scenarios;
}

Map<String, dynamic> validateElapsedInputs(
  Map<String, dynamic> value,
  String asOf,
) {
  final scenarios = _elapsedScenarios(value, asOf);
  return accountingObject(
    immutableTreasury({
      'risk_review': {
        'as_of_date': asOf,
        'stage_label': 'stage_1_12_month',
        'default_label': false,
        'write_off_label': 'none',
        'recovery_label': 'none',
        'primary_evidence_basis': 'contractual_dpd',
        'evidence_reference': _text(value['evidence_reference'], 3, 1000),
        'review_note': _text(value['review_note'], 20, 2000),
      },
      'scenarios': scenarios,
      'review_rationale': _text(value['review_rationale'], 20, 2000),
    }),
  );
}
