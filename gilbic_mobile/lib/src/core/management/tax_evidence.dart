import 'package:gilbic_mobile/src/core/management/tax_value.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class TaxEvidenceOverview {
  const TaxEvidenceOverview({
    required this.summary,
    required this.rules,
    required this.dst,
    required this.percentageTax,
    required this.permissions,
    required this.readiness,
    required this.limit,
    required this.offset,
    required this.evidenceBackedTaxReadinessEnabled,
    required this.taxPostingEnabled,
    required this.automaticSourcePosting,
    required this.notice,
  });

  final TaxEvidenceSummary summary;
  final List<TaxRuleEvidence> rules;
  final List<DstTaxReadiness> dst;
  final List<PercentageTaxReadiness> percentageTax;
  final TaxEvidencePermissions permissions;
  final String readiness;
  final int limit;
  final int offset;
  final bool evidenceBackedTaxReadinessEnabled;
  final bool taxPostingEnabled;
  final bool automaticSourcePosting;
  final String notice;

  factory TaxEvidenceOverview.fromPayload(Map<String, dynamic> payload) {
    final rawRules = payload['rules'];
    final rawDst = payload['dst'];
    final rawPercentage = payload['percentage_tax'];
    if (rawRules is! List || rawDst is! List || rawPercentage is! List) {
      throw invalidTaxPayload('evidence collections');
    }
    final result = TaxEvidenceOverview(
      summary: TaxEvidenceSummary.fromPayload(stringMap(payload['summary'])),
      rules: rawRules
          .map((value) => TaxRuleEvidence.fromPayload(stringMap(value)))
          .toList(growable: false),
      dst: rawDst
          .map((value) => DstTaxReadiness.fromPayload(stringMap(value)))
          .toList(growable: false),
      percentageTax: rawPercentage
          .map((value) => PercentageTaxReadiness.fromPayload(stringMap(value)))
          .toList(growable: false),
      permissions: TaxEvidencePermissions.fromPayload(
        stringMap(payload['permissions']),
      ),
      readiness: taxEnum(payload, 'readiness', const <String>{
        'all',
        'ready',
        'blocked',
      }),
      limit: taxPositiveInt(payload, 'limit'),
      offset: taxNonNegativeInt(payload, 'offset'),
      evidenceBackedTaxReadinessEnabled: taxBool(
        payload,
        'evidence_backed_tax_readiness_enabled',
      ),
      taxPostingEnabled: taxBool(payload, 'tax_posting_enabled'),
      automaticSourcePosting: taxBool(payload, 'automatic_source_posting'),
      notice: taxText(payload, 'notice'),
    );
    if (!result.evidenceBackedTaxReadinessEnabled ||
        result.taxPostingEnabled ||
        result.automaticSourcePosting ||
        result.limit > 200 ||
        !result.summary.evidenceBackedTaxReadinessEnabled ||
        result.summary.taxPostingEnabled ||
        result.summary.automaticSourcePosting) {
      throw invalidTaxPayload('evidence policy');
    }
    return result;
  }
}

class TaxEvidenceSummary {
  const TaxEvidenceSummary({
    required this.ruleEvidenceCount,
    required this.dstSourceCount,
    required this.dstReadyCount,
    required this.dstBlockedCount,
    required this.dstEvidenceTaxTotal,
    required this.percentageSourceCount,
    required this.percentageReadyCount,
    required this.percentageBlockedCount,
    required this.percentageTaxableReceiptTotal,
    required this.percentageEvidenceTaxTotal,
    required this.evidenceBackedTaxReadinessEnabled,
    required this.taxPostingEnabled,
    required this.automaticSourcePosting,
  });

  final int ruleEvidenceCount;
  final int dstSourceCount;
  final int dstReadyCount;
  final int dstBlockedCount;
  final String dstEvidenceTaxTotal;
  final int percentageSourceCount;
  final int percentageReadyCount;
  final int percentageBlockedCount;
  final String percentageTaxableReceiptTotal;
  final String percentageEvidenceTaxTotal;
  final bool evidenceBackedTaxReadinessEnabled;
  final bool taxPostingEnabled;
  final bool automaticSourcePosting;

  factory TaxEvidenceSummary.fromPayload(Map<String, dynamic> payload) =>
      TaxEvidenceSummary(
        ruleEvidenceCount: taxNonNegativeInt(payload, 'rule_evidence_count'),
        dstSourceCount: taxNonNegativeInt(payload, 'dst_source_count'),
        dstReadyCount: taxNonNegativeInt(payload, 'dst_ready_count'),
        dstBlockedCount: taxNonNegativeInt(payload, 'dst_blocked_count'),
        dstEvidenceTaxTotal: taxMoney(payload, 'dst_evidence_tax_total'),
        percentageSourceCount: taxNonNegativeInt(
          payload,
          'percentage_source_count',
        ),
        percentageReadyCount: taxNonNegativeInt(
          payload,
          'percentage_ready_count',
        ),
        percentageBlockedCount: taxNonNegativeInt(
          payload,
          'percentage_blocked_count',
        ),
        percentageTaxableReceiptTotal: taxMoney(
          payload,
          'percentage_taxable_receipt_total',
        ),
        percentageEvidenceTaxTotal: taxMoney(
          payload,
          'percentage_evidence_tax_total',
        ),
        evidenceBackedTaxReadinessEnabled: taxBool(
          payload,
          'evidence_backed_tax_readiness_enabled',
        ),
        taxPostingEnabled: taxBool(payload, 'tax_posting_enabled'),
        automaticSourcePosting: taxBool(payload, 'automatic_source_posting'),
      );
}

class TaxEvidencePermissions {
  const TaxEvidencePermissions({
    required this.ruleEvidenceRecord,
    required this.dstEvidenceRecord,
    required this.percentageEvidenceRecord,
  });
  final bool ruleEvidenceRecord;
  final bool dstEvidenceRecord;
  final bool percentageEvidenceRecord;

  factory TaxEvidencePermissions.fromPayload(Map<String, dynamic> payload) =>
      TaxEvidencePermissions(
        ruleEvidenceRecord: taxBool(payload, 'rule_evidence_record'),
        dstEvidenceRecord: taxBool(payload, 'dst_evidence_record'),
        percentageEvidenceRecord: taxBool(
          payload,
          'percentage_evidence_record',
        ),
      );
}

class TaxRuleEvidence {
  const TaxRuleEvidence({
    required this.id,
    required this.taxType,
    required this.ruleKey,
    required this.ruleVersion,
    required this.effectiveFrom,
    required this.effectiveTo,
    required this.treatment,
    required this.rate,
    required this.maturityMaxDays,
    required this.legalSource,
    required this.legalReference,
    required this.retainedSourceReference,
    required this.evidenceDigest,
    required this.managementRationale,
    required this.supersedesRuleId,
    required this.recordedByUserId,
    required this.recordedAt,
  });
  final String id;
  final String taxType;
  final String ruleKey;
  final int ruleVersion;
  final String effectiveFrom;
  final String? effectiveTo;
  final String treatment;
  final String rate;
  final int? maturityMaxDays;
  final String legalSource;
  final String legalReference;
  final String retainedSourceReference;
  final String evidenceDigest;
  final String managementRationale;
  final String? supersedesRuleId;
  final String recordedByUserId;
  final DateTime recordedAt;

  factory TaxRuleEvidence.fromPayload(Map<String, dynamic> payload) {
    final rate = taxText(payload, 'rate');
    if (!taxRatePattern.hasMatch(rate)) throw invalidTaxPayload('rate');
    return TaxRuleEvidence(
      id: taxUuid(payload, 'id'),
      taxType: taxTypeValue(payload, 'tax_type'),
      ruleKey: taxText(payload, 'rule_key'),
      ruleVersion: taxPositiveInt(payload, 'rule_version'),
      effectiveFrom: taxDate(payload, 'effective_from'),
      effectiveTo: taxOptionalDate(payload, 'effective_to'),
      treatment: taxEnum(payload, 'treatment', const <String>{
        'taxable',
        'exempt',
      }),
      rate: rate,
      maturityMaxDays: taxOptionalPositiveInt(payload, 'maturity_max_days'),
      legalSource: taxText(payload, 'legal_source'),
      legalReference: taxText(payload, 'legal_reference'),
      retainedSourceReference: taxText(payload, 'retained_source_reference'),
      evidenceDigest: taxDigest(payload, 'evidence_digest'),
      managementRationale: taxText(payload, 'management_rationale'),
      supersedesRuleId: taxOptionalUuid(payload, 'supersedes_rule_id'),
      recordedByUserId: taxUuid(payload, 'recorded_by_user_id'),
      recordedAt: taxDateTime(payload, 'recorded_at'),
    );
  }
}

class DstTaxReadiness {
  const DstTaxReadiness({
    required this.loanId,
    required this.clientId,
    required this.disbursementEventId,
    required this.issueDate,
    required this.protectedIssuePrice,
    required this.protectedTermDays,
    required this.evidenceId,
    required this.evidenceVersion,
    required this.ruleEvidenceId,
    required this.taxDue,
    required this.calculationDigest,
    required this.taxStatus,
    required this.taxBlocker,
  });
  final String loanId;
  final String clientId;
  final String disbursementEventId;
  final String issueDate;
  final String protectedIssuePrice;
  final int protectedTermDays;
  final String? evidenceId;
  final int? evidenceVersion;
  final String? ruleEvidenceId;
  final String? taxDue;
  final String? calculationDigest;
  final String taxStatus;
  final String? taxBlocker;

  factory DstTaxReadiness.fromPayload(Map<String, dynamic> payload) {
    _requireEvidencePolicy(payload);
    return DstTaxReadiness(
      loanId: taxUuid(payload, 'loan_id'),
      clientId: taxUuid(payload, 'client_id'),
      disbursementEventId: taxUuid(payload, 'disbursement_event_id'),
      issueDate: taxDate(payload, 'issue_date'),
      protectedIssuePrice: taxPositiveMoney(payload, 'protected_issue_price'),
      protectedTermDays: taxPositiveInt(payload, 'protected_term_days'),
      evidenceId: taxOptionalUuid(payload, 'evidence_id'),
      evidenceVersion: taxOptionalPositiveInt(payload, 'evidence_version'),
      ruleEvidenceId: taxOptionalUuid(payload, 'rule_evidence_id'),
      taxDue: taxOptionalMoney(payload, 'tax_due'),
      calculationDigest: taxOptionalDigest(payload, 'calculation_digest'),
      taxStatus: taxEnum(payload, 'tax_status', _dstTaxStatuses),
      taxBlocker: taxOptionalText(payload, 'tax_blocker'),
    );
  }
}

class PercentageTaxReadiness {
  const PercentageTaxReadiness({
    required this.transactionId,
    required this.loanId,
    required this.clientId,
    required this.collectionDate,
    required this.entryType,
    required this.sourceCashAmount,
    required this.isVoided,
    required this.evidenceId,
    required this.evidenceVersion,
    required this.ruleEvidenceId,
    required this.taxableLendingReceiptAmount,
    required this.principalReceiptAmount,
    required this.taxDue,
    required this.allocationDigest,
    required this.taxStatus,
    required this.taxBlocker,
  });
  final String transactionId;
  final String loanId;
  final String clientId;
  final String collectionDate;
  final String entryType;
  final String sourceCashAmount;
  final bool isVoided;
  final String? evidenceId;
  final int? evidenceVersion;
  final String? ruleEvidenceId;
  final String? taxableLendingReceiptAmount;
  final String? principalReceiptAmount;
  final String? taxDue;
  final String? allocationDigest;
  final String taxStatus;
  final String? taxBlocker;

  factory PercentageTaxReadiness.fromPayload(Map<String, dynamic> payload) {
    _requireEvidencePolicy(payload);
    return PercentageTaxReadiness(
      transactionId: taxUuid(payload, 'transaction_id'),
      loanId: taxUuid(payload, 'loan_id'),
      clientId: taxUuid(payload, 'client_id'),
      collectionDate: taxDate(payload, 'collection_date'),
      entryType: taxEnum(payload, 'entry_type', const <String>{
        'payment',
        'advance',
      }),
      sourceCashAmount: taxPositiveMoney(payload, 'source_cash_amount'),
      isVoided: taxBool(payload, 'is_voided'),
      evidenceId: taxOptionalUuid(payload, 'evidence_id'),
      evidenceVersion: taxOptionalPositiveInt(payload, 'evidence_version'),
      ruleEvidenceId: taxOptionalUuid(payload, 'rule_evidence_id'),
      taxableLendingReceiptAmount: taxOptionalMoney(
        payload,
        'taxable_lending_receipt_amount',
      ),
      principalReceiptAmount: taxOptionalMoney(
        payload,
        'principal_receipt_amount',
      ),
      taxDue: taxOptionalMoney(payload, 'tax_due'),
      allocationDigest: taxOptionalDigest(payload, 'allocation_digest'),
      taxStatus: taxEnum(payload, 'tax_status', _percentageTaxStatuses),
      taxBlocker: taxOptionalText(payload, 'tax_blocker'),
    );
  }
}

class TaxRuleEvidenceDraft {
  const TaxRuleEvidenceDraft({
    required this.taxType,
    required this.ruleKey,
    required this.effectiveFrom,
    required this.effectiveTo,
    required this.treatment,
    required this.rate,
    required this.maturityMaxDays,
    required this.legalSource,
    required this.legalReference,
    required this.retainedSourceReference,
    required this.evidenceDigest,
    required this.managementRationale,
    required this.supersedesRuleId,
  });
  final String taxType;
  final String ruleKey;
  final String effectiveFrom;
  final String? effectiveTo;
  final String treatment;
  final String rate;
  final int? maturityMaxDays;
  final String legalSource;
  final String legalReference;
  final String retainedSourceReference;
  final String evidenceDigest;
  final String managementRationale;
  final String? supersedesRuleId;

  void validate() {
    final payload = toPayload('11111111-1111-4111-8111-111111111111');
    taxTypeValue(payload, 'tax_type');
    taxText(payload, 'rule_key');
    final from = taxDate(payload, 'effective_from');
    final to = taxOptionalDate(payload, 'effective_to');
    final normalizedTreatment = taxEnum(payload, 'treatment', const <String>{
      'taxable',
      'exempt',
    });
    if (!taxRatePattern.hasMatch(rate) ||
        (normalizedTreatment == 'taxable' && _zeroRate(rate)) ||
        (normalizedTreatment == 'exempt' && !_zeroRate(rate)) ||
        (to != null && to.compareTo(from) < 0) ||
        (maturityMaxDays != null && maturityMaxDays! <= 0) ||
        managementRationale.trim().length < 20) {
      throw ArgumentError('Invalid retained tax rule evidence.');
    }
    taxText(payload, 'legal_source');
    taxText(payload, 'legal_reference');
    taxText(payload, 'retained_source_reference');
    taxDigest(payload, 'evidence_digest');
    if (supersedesRuleId != null &&
        !taxUuidPattern.hasMatch(supersedesRuleId!)) {
      throw ArgumentError('Invalid superseded tax rule identity.');
    }
  }

  Map<String, Object?> toPayload(String idempotencyKey) => <String, Object?>{
    'confirm': true,
    'idempotency_key': idempotencyKey,
    'tax_type': taxType,
    'rule_key': ruleKey.trim(),
    'effective_from': effectiveFrom,
    'effective_to': effectiveTo,
    'treatment': treatment,
    'rate': rate,
    'maturity_max_days': maturityMaxDays,
    'legal_source': legalSource.trim(),
    'legal_reference': legalReference.trim(),
    'retained_source_reference': retainedSourceReference.trim(),
    'evidence_digest': evidenceDigest,
    'management_rationale': managementRationale.trim(),
    'supersedes_rule_id': supersedesRuleId,
  };
}

class DstEvidenceDraft {
  const DstEvidenceDraft({
    required this.ruleEvidenceId,
    required this.expectedTaxDue,
    required this.instrumentReference,
    required this.instrumentDigest,
    required this.calculationReference,
    required this.calculationDigest,
    required this.managementRationale,
  });
  final String ruleEvidenceId;
  final String expectedTaxDue;
  final String instrumentReference;
  final String instrumentDigest;
  final String calculationReference;
  final String calculationDigest;
  final String managementRationale;

  void validate() {
    if (!taxUuidPattern.hasMatch(ruleEvidenceId) ||
        !taxMoneyPattern.hasMatch(expectedTaxDue) ||
        instrumentReference.trim().isEmpty ||
        calculationReference.trim().isEmpty ||
        !taxDigestPattern.hasMatch(instrumentDigest) ||
        !taxDigestPattern.hasMatch(calculationDigest) ||
        managementRationale.trim().length < 20) {
      throw ArgumentError('Invalid retained DST evidence.');
    }
  }
}

class PercentageTaxEvidenceDraft {
  const PercentageTaxEvidenceDraft({
    required this.ruleEvidenceId,
    required this.taxableLendingReceiptAmount,
    required this.principalReceiptAmount,
    required this.expectedTaxDue,
    required this.allocationReference,
    required this.allocationDigest,
    required this.managementRationale,
  });
  final String ruleEvidenceId;
  final String taxableLendingReceiptAmount;
  final String principalReceiptAmount;
  final String expectedTaxDue;
  final String allocationReference;
  final String allocationDigest;
  final String managementRationale;

  void validate(String sourceCashAmount) {
    if (!taxUuidPattern.hasMatch(ruleEvidenceId) ||
        !taxMoneyPattern.hasMatch(taxableLendingReceiptAmount) ||
        !taxMoneyPattern.hasMatch(principalReceiptAmount) ||
        !taxMoneyPattern.hasMatch(expectedTaxDue) ||
        taxCents(taxableLendingReceiptAmount) +
                taxCents(principalReceiptAmount) !=
            taxCents(sourceCashAmount) ||
        allocationReference.trim().isEmpty ||
        !taxDigestPattern.hasMatch(allocationDigest) ||
        managementRationale.trim().length < 20) {
      throw ArgumentError('Invalid retained percentage-tax evidence.');
    }
  }
}

void _requireEvidencePolicy(Map<String, dynamic> payload) {
  if (taxBool(payload, 'tax_posting_enabled') ||
      taxBool(payload, 'automatic_source_posting')) {
    throw invalidTaxPayload('evidence item policy');
  }
}

const _dstTaxStatuses = <String>{
  'blocked_source_voided',
  'evidence_required',
  'blocked_source_changed',
  'blocked_rule_not_applicable',
  'blocked_rule_superseded',
  'evidence_ready',
};

const _percentageTaxStatuses = <String>{
  'blocked_source_voided',
  'allocation_evidence_required',
  'blocked_source_changed',
  'blocked_allocation_unreconciled',
  'blocked_rule_not_applicable',
  'blocked_rule_superseded',
  'evidence_ready',
};

bool _zeroRate(String value) => taxZeroRatePattern.hasMatch(value);
