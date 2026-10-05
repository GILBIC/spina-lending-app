import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';

const elapsedAssessmentBase =
    '$sourceAccountingBase/period-elapsed-assessments';
Map<String, dynamic> _pick(Map<String, dynamic> value, List<String> keys) => {
  for (final key in keys) key: value[key],
};
BigInt _cents(Object? value, {bool signed = false}) =>
    BigInt.parse(TreasuryMoney(value, signed: signed).text.replaceAll('.', ''));
String _text(Object? value, int min, int max) {
  accountingCheck(
    value is String && value.trim().length >= min && value.trim().length <= max,
    'Supply a reference or rationale of $min–$max characters.',
  );
  return (value as String).trim();
}

Map<String, dynamic> validateElapsedPreparation(
  Map<String, dynamic> value, {
  required String bookId,
  required String periodId,
  required String loanId,
  Map<String, dynamic>? candidate,
}) {
  accountingCheck(
    value['book_id'] == bookId &&
        value['period_id'] == periodId &&
        value['loan_id'] == loanId &&
        treasuryUuid(value['preparation_id']) &&
        accountingDigest(value['source_digest']) &&
        accountingDigest(value['confirmation_digest']) &&
        accountingDate(value['as_of_date']) &&
        value['policy_version'] ==
            'historical_original_timing_cash_shortfall_v1' &&
        value['comprehensive_source_coverage'] == false &&
        value['scenario_count'] is int &&
        (value['scenario_count'] as int) >= 2 &&
        (value['scenario_count'] as int) <= 20,
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
  accountingCheck(
    _cents(value['ecl_amount']) - _cents(value['prior_allowance']) ==
        _cents(value['allowance_delta'], signed: true),
  );
  if (candidate != null) {
    final eir = accountingObject(candidate['eir']);
    accountingCheck(
      value['source_digest'] == candidate['source_digest'] &&
          value['as_of_date'] == candidate['as_of_date'] &&
          value['cumulative_interest'] == eir['cumulative_interest'] &&
          value['incremental_interest'] == eir['incremental_interest'] &&
          value['prior_allowance'] == candidate['prior_allowance'],
    );
  }
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
  final reviewInputs = validateElapsedInputs({
    ...reviewed,
    'evidence_reference': risk['evidence_reference'],
    'review_note': risk['review_note'],
  }, value['as_of_date'] as String);
  accountingCheck(
    (reviewInputs['scenarios'] as List).length == value['scenario_count'],
  );
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

Map<String, dynamic> validateElapsedInputs(
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
