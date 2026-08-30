import 'package:gilbic_mobile/src/core/management/tax_value.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class TaxAdjustmentOverview {
  const TaxAdjustmentOverview({
    required this.summary,
    required this.items,
    required this.adjustmentCandidates,
    required this.permissions,
    required this.adjustmentStatus,
    required this.limit,
    required this.offset,
    required this.notice,
  });
  final TaxAdjustmentSummary summary;
  final List<TaxAdjustmentItem> items;
  final List<TaxAdjustmentCandidate> adjustmentCandidates;
  final TaxAdjustmentPermissions permissions;
  final String adjustmentStatus;
  final int limit;
  final int offset;
  final String notice;

  factory TaxAdjustmentOverview.fromPayload(Map<String, dynamic> payload) {
    _requireAdjustmentPolicy(payload);
    final rawItems = payload['items'];
    final rawCandidates = payload['adjustment_candidates'];
    if (rawItems is! List || rawCandidates is! List) {
      throw invalidTaxPayload('adjustment collections');
    }
    final result = TaxAdjustmentOverview(
      summary: TaxAdjustmentSummary.fromPayload(stringMap(payload['summary'])),
      items: rawItems
          .map((value) => TaxAdjustmentItem.fromPayload(stringMap(value)))
          .toList(growable: false),
      adjustmentCandidates: rawCandidates
          .map((value) => TaxAdjustmentCandidate.fromPayload(stringMap(value)))
          .toList(growable: false),
      permissions: TaxAdjustmentPermissions.fromPayload(
        stringMap(payload['permissions']),
      ),
      adjustmentStatus: taxEnum(
        payload,
        'adjustment_status',
        taxAdjustmentFilters,
      ),
      limit: taxPositiveInt(payload, 'limit'),
      offset: taxNonNegativeInt(payload, 'offset'),
      notice: taxText(payload, 'notice'),
    );
    if (result.limit > 200) throw invalidTaxPayload('adjustment limit');
    return result;
  }
}

class TaxAdjustmentSummary {
  const TaxAdjustmentSummary({
    required this.adjustmentEvidenceCount,
    required this.readyToPrepareCount,
    required this.preparedCount,
    required this.postedReversalCount,
    required this.postedRecoverableCount,
    required this.furtherReviewCount,
    required this.blockedCount,
    required this.postedAdjustmentTotal,
  });
  final int adjustmentEvidenceCount;
  final int readyToPrepareCount;
  final int preparedCount;
  final int postedReversalCount;
  final int postedRecoverableCount;
  final int furtherReviewCount;
  final int blockedCount;
  final String postedAdjustmentTotal;

  factory TaxAdjustmentSummary.fromPayload(Map<String, dynamic> payload) {
    _requireAdjustmentPolicy(payload);
    return TaxAdjustmentSummary(
      adjustmentEvidenceCount: taxNonNegativeInt(
        payload,
        'adjustment_evidence_count',
      ),
      readyToPrepareCount: taxNonNegativeInt(payload, 'ready_to_prepare_count'),
      preparedCount: taxNonNegativeInt(payload, 'prepared_count'),
      postedReversalCount: taxNonNegativeInt(payload, 'posted_reversal_count'),
      postedRecoverableCount: taxNonNegativeInt(
        payload,
        'posted_recoverable_count',
      ),
      furtherReviewCount: taxNonNegativeInt(payload, 'further_review_count'),
      blockedCount: taxNonNegativeInt(payload, 'blocked_count'),
      postedAdjustmentTotal: taxMoney(payload, 'posted_adjustment_total'),
    );
  }
}

class TaxAdjustmentPermissions {
  const TaxAdjustmentPermissions({
    required this.adjustmentEvidenceRecord,
    required this.adjustmentPrepare,
    required this.adjustmentPost,
  });
  final bool adjustmentEvidenceRecord;
  final bool adjustmentPrepare;
  final bool adjustmentPost;
  factory TaxAdjustmentPermissions.fromPayload(Map<String, dynamic> payload) =>
      TaxAdjustmentPermissions(
        adjustmentEvidenceRecord: taxBool(
          payload,
          'adjustment_evidence_record',
        ),
        adjustmentPrepare: taxBool(payload, 'adjustment_prepare'),
        adjustmentPost: taxBool(payload, 'adjustment_post'),
      );
}

class TaxAdjustmentCandidate {
  const TaxAdjustmentCandidate({
    required this.adjustmentKind,
    required this.taxType,
    required this.taxLiabilityPostingId,
    required this.originalEvidenceId,
    required this.originalEvidenceVersion,
    required this.replacementEvidenceId,
    required this.replacementEvidenceVersion,
    required this.sourceId,
    required this.loanId,
    required this.clientId,
    required this.originalTaxDue,
    required this.replacementTaxDue,
    required this.adjustmentAmount,
    required this.originalEvidenceDigest,
    required this.replacementEvidenceDigest,
    required this.fiscalPeriodId,
    required this.fiscalPeriodStart,
    required this.fiscalPeriodEnd,
    required this.settlementPostingId,
  });
  final String adjustmentKind;
  final String taxType;
  final String taxLiabilityPostingId;
  final String originalEvidenceId;
  final int originalEvidenceVersion;
  final String replacementEvidenceId;
  final int replacementEvidenceVersion;
  final String sourceId;
  final String loanId;
  final String clientId;
  final String originalTaxDue;
  final String replacementTaxDue;
  final String adjustmentAmount;
  final String originalEvidenceDigest;
  final String replacementEvidenceDigest;
  final String fiscalPeriodId;
  final String fiscalPeriodStart;
  final String fiscalPeriodEnd;
  final String? settlementPostingId;

  factory TaxAdjustmentCandidate.fromPayload(Map<String, dynamic> payload) {
    final result = TaxAdjustmentCandidate(
      adjustmentKind: taxEnum(payload, 'adjustment_kind', taxAdjustmentKinds),
      taxType: taxTypeValue(payload, 'tax_type'),
      taxLiabilityPostingId: taxUuid(payload, 'tax_liability_posting_id'),
      originalEvidenceId: taxUuid(payload, 'original_evidence_id'),
      originalEvidenceVersion: taxPositiveInt(
        payload,
        'original_evidence_version',
      ),
      replacementEvidenceId: taxUuid(payload, 'replacement_evidence_id'),
      replacementEvidenceVersion: taxPositiveInt(
        payload,
        'replacement_evidence_version',
      ),
      sourceId: taxUuid(payload, 'source_id'),
      loanId: taxUuid(payload, 'loan_id'),
      clientId: taxUuid(payload, 'client_id'),
      originalTaxDue: taxPositiveMoney(payload, 'original_tax_due'),
      replacementTaxDue: taxMoney(payload, 'replacement_tax_due'),
      adjustmentAmount: taxPositiveMoney(payload, 'adjustment_amount'),
      originalEvidenceDigest: taxDigest(payload, 'original_evidence_digest'),
      replacementEvidenceDigest: taxDigest(
        payload,
        'replacement_evidence_digest',
      ),
      fiscalPeriodId: taxUuid(payload, 'fiscal_period_id'),
      fiscalPeriodStart: taxDate(payload, 'fiscal_period_start'),
      fiscalPeriodEnd: taxDate(payload, 'fiscal_period_end'),
      settlementPostingId: taxOptionalUuid(payload, 'settlement_posting_id'),
    );
    result._validate();
    return result;
  }

  void _validate() {
    if (replacementEvidenceVersion <= originalEvidenceVersion ||
        DateTime.parse(
          fiscalPeriodEnd,
        ).isBefore(DateTime.parse(fiscalPeriodStart))) {
      throw invalidTaxPayload('adjustment candidate coordinates');
    }
    final original = taxCents(originalTaxDue);
    final replacement = taxCents(replacementTaxDue);
    final amount = taxCents(adjustmentAmount);
    if (adjustmentKind == 'reverse_unsettled_liability') {
      if (settlementPostingId != null || amount != original) {
        throw invalidTaxPayload('unsettled adjustment candidate');
      }
    } else if (settlementPostingId == null ||
        replacement >= original ||
        amount != original - replacement) {
      throw invalidTaxPayload('settled adjustment candidate');
    }
  }
}

class TaxAdjustmentItem {
  const TaxAdjustmentItem({
    required this.adjustmentEvidenceId,
    required this.adjustmentKind,
    required this.taxType,
    required this.taxLiabilityPostingId,
    required this.originalEvidenceId,
    required this.replacementEvidenceId,
    required this.sourceId,
    required this.loanId,
    required this.clientId,
    required this.originalTaxDue,
    required this.replacementTaxDue,
    required this.adjustmentAmount,
    required this.adjustmentDate,
    required this.adjustmentReference,
    required this.evidenceReference,
    required this.evidenceDigest,
    required this.recordedByUserId,
    required this.recordedAt,
    required this.settlementPostingId,
    required this.originalSettlementJournalEntryId,
    required this.preparationId,
    required this.journalEntryId,
    required this.journalStatus,
    required this.entryNumber,
    required this.fiscalPeriodId,
    required this.debitAccountId,
    required this.debitAccountCode,
    required this.debitAccountName,
    required this.creditAccountId,
    required this.creditAccountCode,
    required this.creditAccountName,
    required this.preparedByUserId,
    required this.preparedAt,
    required this.adjustmentPostingId,
    required this.confirmationDigest,
    required this.postedByUserId,
    required this.postedAt,
    required this.adjustmentStatus,
    required this.adjustmentBlocker,
  });
  final String adjustmentEvidenceId;
  final String adjustmentKind;
  final String taxType;
  final String taxLiabilityPostingId;
  final String originalEvidenceId;
  final String replacementEvidenceId;
  final String sourceId;
  final String loanId;
  final String clientId;
  final String originalTaxDue;
  final String replacementTaxDue;
  final String adjustmentAmount;
  final String adjustmentDate;
  final String adjustmentReference;
  final String evidenceReference;
  final String evidenceDigest;
  final String recordedByUserId;
  final DateTime recordedAt;
  final String? settlementPostingId;
  final String? originalSettlementJournalEntryId;
  final String? preparationId;
  final String? journalEntryId;
  final String? journalStatus;
  final String? entryNumber;
  final String? fiscalPeriodId;
  final String? debitAccountId;
  final String? debitAccountCode;
  final String? debitAccountName;
  final String? creditAccountId;
  final String? creditAccountCode;
  final String? creditAccountName;
  final String? preparedByUserId;
  final DateTime? preparedAt;
  final String? adjustmentPostingId;
  final String? confirmationDigest;
  final String? postedByUserId;
  final DateTime? postedAt;
  final String adjustmentStatus;
  final String? adjustmentBlocker;

  bool get isEvidenceReady => adjustmentStatus == 'evidence_ready';
  bool get isPrepared => adjustmentStatus == 'prepared_not_posted';
  bool get isPosted => adjustmentStatus.startsWith('posted_');

  factory TaxAdjustmentItem.fromPayload(Map<String, dynamic> payload) {
    _requireAdjustmentPolicy(payload);
    final item = TaxAdjustmentItem(
      adjustmentEvidenceId: taxUuid(payload, 'adjustment_evidence_id'),
      adjustmentKind: taxEnum(payload, 'adjustment_kind', taxAdjustmentKinds),
      taxType: taxTypeValue(payload, 'tax_type'),
      taxLiabilityPostingId: taxUuid(payload, 'tax_liability_posting_id'),
      originalEvidenceId: taxUuid(payload, 'original_evidence_id'),
      replacementEvidenceId: taxUuid(payload, 'replacement_evidence_id'),
      sourceId: taxUuid(payload, 'source_id'),
      loanId: taxUuid(payload, 'loan_id'),
      clientId: taxUuid(payload, 'client_id'),
      originalTaxDue: taxPositiveMoney(payload, 'original_tax_due'),
      replacementTaxDue: taxMoney(payload, 'replacement_tax_due'),
      adjustmentAmount: taxPositiveMoney(payload, 'adjustment_amount'),
      adjustmentDate: taxDate(payload, 'adjustment_date'),
      adjustmentReference: taxText(payload, 'adjustment_reference'),
      evidenceReference: taxText(payload, 'evidence_reference'),
      evidenceDigest: taxDigest(payload, 'evidence_digest'),
      recordedByUserId: taxUuid(payload, 'recorded_by_user_id'),
      recordedAt: taxDateTime(payload, 'recorded_at'),
      settlementPostingId: taxOptionalUuid(payload, 'settlement_posting_id'),
      originalSettlementJournalEntryId: taxOptionalUuid(
        payload,
        'original_settlement_journal_entry_id',
      ),
      preparationId: taxOptionalUuid(payload, 'preparation_id'),
      journalEntryId: taxOptionalUuid(payload, 'journal_entry_id'),
      journalStatus: _optionalJournalStatus(payload),
      entryNumber: taxOptionalText(payload, 'entry_number'),
      fiscalPeriodId: taxOptionalUuid(payload, 'fiscal_period_id'),
      debitAccountId: taxOptionalUuid(payload, 'debit_account_id'),
      debitAccountCode: taxOptionalText(payload, 'debit_account_code'),
      debitAccountName: taxOptionalText(payload, 'debit_account_name'),
      creditAccountId: taxOptionalUuid(payload, 'credit_account_id'),
      creditAccountCode: taxOptionalText(payload, 'credit_account_code'),
      creditAccountName: taxOptionalText(payload, 'credit_account_name'),
      preparedByUserId: taxOptionalUuid(payload, 'prepared_by_user_id'),
      preparedAt: taxOptionalDateTime(payload, 'prepared_at'),
      adjustmentPostingId: taxOptionalUuid(payload, 'adjustment_posting_id'),
      confirmationDigest: taxOptionalDigest(payload, 'confirmation_digest'),
      postedByUserId: taxOptionalUuid(payload, 'posted_by_user_id'),
      postedAt: taxOptionalDateTime(payload, 'posted_at'),
      adjustmentStatus: taxEnum(
        payload,
        'adjustment_status',
        taxAdjustmentStatuses,
      ),
      adjustmentBlocker: taxOptionalText(payload, 'adjustment_blocker'),
    );
    item._validate();
    return item;
  }

  void requirePrepareCoordinates() {
    if (!isEvidenceReady || preparationId != null || journalEntryId != null) {
      throw ArgumentError('Exact adjustment evidence-ready state is required.');
    }
  }

  void requirePostCoordinates() {
    if (!isPrepared ||
        preparationId == null ||
        journalEntryId == null ||
        journalStatus != 'draft' ||
        fiscalPeriodId == null ||
        debitAccountId == null ||
        debitAccountCode == null ||
        debitAccountName == null ||
        creditAccountId == null ||
        creditAccountCode == null ||
        creditAccountName == null ||
        preparedByUserId == null ||
        preparedAt == null) {
      throw ArgumentError(
        'Exact prepared adjustment coordinates are required.',
      );
    }
  }

  void _validate() {
    try {
      if (isEvidenceReady) requirePrepareCoordinates();
      if (isPrepared) requirePostCoordinates();
    } on ArgumentError {
      throw invalidTaxPayload('adjustment action coordinates');
    }
    if (isPosted &&
        (preparationId == null ||
            journalEntryId == null ||
            journalStatus != 'posted' ||
            entryNumber == null ||
            fiscalPeriodId == null ||
            adjustmentPostingId == null ||
            confirmationDigest == null ||
            postedByUserId == null ||
            postedAt == null)) {
      throw invalidTaxPayload('posted adjustment state');
    }
  }
}

const taxAdjustmentKinds = <String>{
  'reverse_unsettled_liability',
  'recognize_settled_tax_recoverable',
};
const taxAdjustmentFilters = <String>{
  'all',
  'ready',
  'prepared',
  'posted',
  'review',
  'blocked',
};
const taxAdjustmentStatuses = <String>{
  'posted_further_adjustment_review_required',
  'posted_unsettled_liability_reversal',
  'posted_settled_tax_recoverable',
  'blocked_original_liability_not_stale',
  'blocked_replacement_evidence_changed',
  'blocked_untracked_adjustment_journal_state',
  'blocked_original_period_not_open',
  'prepared_not_posted',
  'evidence_ready',
};

void _requireAdjustmentPolicy(Map<String, dynamic> payload) {
  if (!taxBool(payload, 'tax_settlement_enabled') ||
      !taxBool(payload, 'tax_adjustment_reversal_enabled') ||
      taxBool(payload, 'automatic_source_posting')) {
    throw invalidTaxPayload('adjustment policy');
  }
}

String? _optionalJournalStatus(Map<String, dynamic> payload) {
  if (payload['journal_status'] == null) return null;
  return taxEnum(payload, 'journal_status', const <String>{'draft', 'posted'});
}
