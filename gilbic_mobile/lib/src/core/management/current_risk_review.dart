import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';

const currentRiskStages = [
  'stage_1_12_month',
  'stage_2_lifetime',
  'stage_3_credit_impaired',
];
const currentRiskWriteOffs = [
  'none',
  'supported_no_reasonable_expectation_of_recovery',
];
const currentRiskRecoveries = ['none', 'cash_recovery_observed', 'cured'];
const currentRiskBases = [
  'contractual_dpd',
  'protected_collection_history',
  'verified_source_document',
  'verified_qualitative_credit_event',
  'authoritative_external_evidence',
];
bool currentRiskTime(Object? v) =>
    v is String &&
    RegExp(r'^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$').hasMatch(v) &&
    DateTime.tryParse(v) != null;
Map<String, dynamic> _pick(Map<String, dynamic> v, List<String> keys) => {
  for (final key in keys) key: v[key],
};
bool _positive(Object? v) => v is int && v > 0 && v <= 9007199254740991;
Map<String, dynamic> validateCurrentRiskContext(
  Map<String, dynamic> v, {
  required String bookId,
  required String periodId,
  required String loanId,
}) {
  accountingCheck(
    v['book_id'] == bookId &&
        v['period_id'] == periodId &&
        v['loan_id'] == loanId &&
        v['ready'] is bool &&
        v['blockers'] is List &&
        (v['blockers'] as List).every((x) => x is String) &&
        accountingDate(v['as_of_date']),
  );
  if (v['ready'] == true) {
    accountingCheck(
      (v['blockers'] as List).isEmpty &&
          accountingDigest(v['source_digest']) &&
          treasuryUuid(v['schedule_id']) &&
          _positive(v['schedule_version']) &&
          v['days_past_due'] is int &&
          (v['days_past_due'] as int) >= 0 &&
          v['thirty_day_sicr_backstop_reached'] ==
              ((v['days_past_due'] as int) >= 30) &&
          v['ninety_day_default_backstop_reached'] ==
              ((v['days_past_due'] as int) >= 90),
    );
    TreasuryMoney(v['due_unpaid_amount']);
  } else {
    accountingCheck(v['source_digest'] == null);
  }
  final out = _pick(v, [
    'book_id',
    'period_id',
    'loan_id',
    'ready',
    'blockers',
    'as_of_date',
    'source_digest',
    'schedule_id',
    'schedule_version',
    'days_past_due',
    'due_unpaid_amount',
    'thirty_day_sicr_backstop_reached',
    'ninety_day_default_backstop_reached',
  ]);
  out['prior_review'] = null;
  if (v['prior_review'] != null) {
    final p = accountingObject(v['prior_review']);
    accountingCheck(
      _positive(p['id']) &&
          _positive(p['review_version']) &&
          currentRiskStages.contains(p['stage_label']) &&
          p['default_label'] is bool &&
          currentRiskWriteOffs.contains(p['write_off_label']) &&
          currentRiskRecoveries.contains(p['recovery_label']) &&
          currentRiskTime(p['reviewed_at']),
    );
    out['prior_review'] = _pick(p, [
      'id',
      'review_version',
      'stage_label',
      'default_label',
      'write_off_label',
      'recovery_label',
      'reviewed_at',
    ]);
  }
  out['inherited_review'] = null;
  if (v['inherited_review'] != null) {
    final p = accountingObject(v['inherited_review']);
    accountingCheck(
      _positive(p['id']) &&
          _positive(p['review_version']) &&
          treasuryUuid(p['loan_id']) &&
          p['loan_id'] != loanId &&
          currentRiskStages.contains(p['stage_label']) &&
          p['default_label'] is bool &&
          currentRiskWriteOffs.contains(p['write_off_label']) &&
          currentRiskRecoveries.contains(p['recovery_label']) &&
          currentRiskTime(p['reviewed_at']),
    );
    out['inherited_review'] = _pick(p, [
      'id',
      'review_version',
      'loan_id',
      'stage_label',
      'default_label',
      'write_off_label',
      'recovery_label',
      'reviewed_at',
    ]);
  }
  return accountingObject(immutableTreasury(out));
}

String _text(Object? v, int max) {
  accountingCheck(
    v is String && v.trim().isNotEmpty && v.trim().length <= max,
    'Supply a dated evidence reference or rationale within its length limit.',
  );
  return (v as String).trim().replaceAll(RegExp(r'\s+'), ' ');
}

Map<String, dynamic> validateCurrentRiskInputs(
  Map<String, dynamic> v,
  Map<String, dynamic> c,
) {
  accountingCheck(
    c['ready'] == true &&
        currentRiskStages.contains(v['stage_label']) &&
        v['default_label'] is bool &&
        currentRiskWriteOffs.contains(v['write_off_label']) &&
        currentRiskRecoveries.contains(v['recovery_label']) &&
        currentRiskBases.contains(v['primary_evidence_basis']) &&
        v['sicr_backstop_rebutted'] is bool &&
        v['default_backstop_rebutted'] is bool,
    'Choose every risk label and evidence basis explicitly.',
  );
  final out = _pick(v, [
    'stage_label',
    'default_label',
    'write_off_label',
    'recovery_label',
    'primary_evidence_basis',
    'sicr_backstop_rebutted',
    'default_backstop_rebutted',
  ]);
  out['evidence_reference'] = _text(v['evidence_reference'], 300);
  out['review_note'] = _text(v['review_note'], 1200);
  final stage1 = v['stage_label'] == 'stage_1_12_month',
      defaulted = v['default_label'] == true,
      dpd = c['days_past_due'] as int,
      sicr = v['sicr_backstop_rebutted'] == true,
      defaultRebuttal = v['default_backstop_rebutted'] == true,
      noncontractual = v['primary_evidence_basis'] != 'contractual_dpd';
  accountingCheck(
    !(stage1 && defaulted),
    'Stage 1 cannot have a default label.',
  );
  accountingCheck(
    !(stage1 && dpd >= 30 && !sicr),
    'Stage 1 at the SICR backstop requires a separate evidenced rebuttal.',
  );
  accountingCheck(
    !(!defaulted && dpd >= 90 && !defaultRebuttal),
    'A nondefault label at the default backstop requires a separate evidenced rebuttal.',
  );
  accountingCheck(!sicr || dpd >= 30);
  accountingCheck(!defaultRebuttal || dpd >= 90);
  for (final key in [
    'rebuttal_evidence_reference',
    'rebuttal_note',
    'write_off_evidence_reference',
    'write_off_note',
  ]) {
    out[key] = v[key] == null || v[key] == ''
        ? null
        : _text(v[key], key.endsWith('note') ? 1200 : 300);
  }
  accountingCheck(
    sicr || defaultRebuttal
        ? noncontractual &&
              out['rebuttal_evidence_reference'] != null &&
              out['rebuttal_note'] != null
        : out['rebuttal_evidence_reference'] == null &&
              out['rebuttal_note'] == null,
    'Supply separate rebuttal evidence only for an explicit rebuttal.',
  );
  accountingCheck(
    !((!stage1 && dpd < 30) || (defaulted && dpd < 90)) || noncontractual,
    'This label requires a substantive basis beyond contractual days past due.',
  );
  accountingCheck(
    v['write_off_label'] == 'none'
        ? out['write_off_evidence_reference'] == null &&
              out['write_off_note'] == null
        : v['stage_label'] == 'stage_3_credit_impaired' &&
              defaulted &&
              noncontractual &&
              out['write_off_evidence_reference'] != null &&
              out['write_off_note'] != null,
    'Write-off support requires a separate evidenced Stage 3 default review.',
  );
  out['recovery_transaction_id'] = v['recovery_transaction_id'] == ''
      ? null
      : v['recovery_transaction_id'];
  accountingCheck(
    v['recovery_label'] == 'cash_recovery_observed'
        ? treasuryUuid(out['recovery_transaction_id'])
        : out['recovery_transaction_id'] == null,
    'A cash recovery requires its actual protected transaction.',
  );
  return accountingObject(immutableTreasury(out));
}

void validateCurrentRiskReceipt(
  Map<String, dynamic> v,
  Map<String, dynamic> c,
  Map<String, dynamic> inputs,
) {
  accountingCheck(
    _positive(v['review_id']) &&
        currentRiskTime(v['reviewed_at']) &&
        v['as_of_date'] == c['as_of_date'] &&
        v['stage_label'] == inputs['stage_label'] &&
        v['default_label'] == inputs['default_label'] &&
        v['recovery_label'] == inputs['recovery_label'],
  );
}
