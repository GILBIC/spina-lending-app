import 'package:gilbic_mobile/src/core/management/tax_value.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class TaxLiabilityOverview {
  const TaxLiabilityOverview({
    required this.summary,
    required this.items,
    required this.permissions,
    required this.accountingStatus,
    required this.limit,
    required this.offset,
    required this.protectedTaxLiabilityPostingEnabled,
    required this.taxSettlementEnabled,
    required this.taxAdjustmentReversalEnabled,
    required this.automaticSourcePosting,
    required this.notice,
  });

  final TaxLiabilitySummary summary;
  final List<TaxLiabilityItem> items;
  final TaxLiabilityPermissions permissions;
  final String accountingStatus;
  final int limit;
  final int offset;
  final bool protectedTaxLiabilityPostingEnabled;
  final bool taxSettlementEnabled;
  final bool taxAdjustmentReversalEnabled;
  final bool automaticSourcePosting;
  final String notice;

  factory TaxLiabilityOverview.fromPayload(Map<String, dynamic> payload) {
    final rawItems = payload['items'];
    if (rawItems is! List) throw invalidTaxPayload('liability items');
    final result = TaxLiabilityOverview(
      summary: TaxLiabilitySummary.fromPayload(stringMap(payload['summary'])),
      items: rawItems
          .map((value) => TaxLiabilityItem.fromPayload(stringMap(value)))
          .toList(growable: false),
      permissions: TaxLiabilityPermissions.fromPayload(
        stringMap(payload['permissions']),
      ),
      accountingStatus: taxEnum(
        payload,
        'accounting_status',
        taxLiabilityFilters,
      ),
      limit: taxPositiveInt(payload, 'limit'),
      offset: taxNonNegativeInt(payload, 'offset'),
      protectedTaxLiabilityPostingEnabled: taxBool(
        payload,
        'protected_tax_liability_posting_enabled',
      ),
      taxSettlementEnabled: taxBool(payload, 'tax_settlement_enabled'),
      taxAdjustmentReversalEnabled: taxBool(
        payload,
        'tax_adjustment_reversal_enabled',
      ),
      automaticSourcePosting: taxBool(payload, 'automatic_source_posting'),
      notice: taxText(payload, 'notice'),
    );
    if (!result.protectedTaxLiabilityPostingEnabled ||
        !result.taxSettlementEnabled ||
        !result.taxAdjustmentReversalEnabled ||
        result.automaticSourcePosting ||
        result.limit > 200 ||
        !result.summary.protectedTaxLiabilityPostingEnabled ||
        !result.summary.taxSettlementEnabled ||
        !result.summary.taxAdjustmentReversalEnabled ||
        result.summary.automaticSourcePosting) {
      throw invalidTaxPayload('liability policy');
    }
    return result;
  }
}

class TaxLiabilitySummary {
  const TaxLiabilitySummary({
    required this.evidenceItemCount,
    required this.readyToPrepareCount,
    required this.preparedCount,
    required this.postedCount,
    required this.noLiabilityRequiredCount,
    required this.adjustedPostingCount,
    required this.coveredReplacementCount,
    required this.blockedOrAdjustmentReviewCount,
    required this.postedTaxLiabilityTotal,
    required this.protectedTaxLiabilityPostingEnabled,
    required this.taxSettlementEnabled,
    required this.taxAdjustmentReversalEnabled,
    required this.automaticSourcePosting,
  });
  final int evidenceItemCount;
  final int readyToPrepareCount;
  final int preparedCount;
  final int postedCount;
  final int noLiabilityRequiredCount;
  final int adjustedPostingCount;
  final int coveredReplacementCount;
  final int blockedOrAdjustmentReviewCount;
  final String postedTaxLiabilityTotal;
  final bool protectedTaxLiabilityPostingEnabled;
  final bool taxSettlementEnabled;
  final bool taxAdjustmentReversalEnabled;
  final bool automaticSourcePosting;

  factory TaxLiabilitySummary.fromPayload(
    Map<String, dynamic> payload,
  ) => TaxLiabilitySummary(
    evidenceItemCount: taxNonNegativeInt(payload, 'evidence_item_count'),
    readyToPrepareCount: taxNonNegativeInt(payload, 'ready_to_prepare_count'),
    preparedCount: taxNonNegativeInt(payload, 'prepared_count'),
    postedCount: taxNonNegativeInt(payload, 'posted_count'),
    noLiabilityRequiredCount: taxNonNegativeInt(
      payload,
      'no_liability_required_count',
    ),
    adjustedPostingCount: taxNonNegativeInt(payload, 'adjusted_posting_count'),
    coveredReplacementCount: taxNonNegativeInt(
      payload,
      'covered_replacement_count',
    ),
    blockedOrAdjustmentReviewCount: taxNonNegativeInt(
      payload,
      'blocked_or_adjustment_review_count',
    ),
    postedTaxLiabilityTotal: taxMoney(payload, 'posted_tax_liability_total'),
    protectedTaxLiabilityPostingEnabled: taxBool(
      payload,
      'protected_tax_liability_posting_enabled',
    ),
    taxSettlementEnabled: taxBool(payload, 'tax_settlement_enabled'),
    taxAdjustmentReversalEnabled: taxBool(
      payload,
      'tax_adjustment_reversal_enabled',
    ),
    automaticSourcePosting: taxBool(payload, 'automatic_source_posting'),
  );
}

class TaxLiabilityPermissions {
  const TaxLiabilityPermissions({
    required this.liabilityPrepare,
    required this.liabilityPost,
  });
  final bool liabilityPrepare;
  final bool liabilityPost;
  factory TaxLiabilityPermissions.fromPayload(Map<String, dynamic> payload) =>
      TaxLiabilityPermissions(
        liabilityPrepare: taxBool(payload, 'liability_prepare'),
        liabilityPost: taxBool(payload, 'liability_post'),
      );
}

class TaxLiabilityItem {
  const TaxLiabilityItem({
    required this.taxType,
    required this.evidenceId,
    required this.evidenceVersion,
    required this.sourceId,
    required this.loanId,
    required this.clientId,
    required this.recognitionDate,
    required this.taxDue,
    required this.evidenceDigest,
    required this.evidenceStatus,
    required this.evidenceBlocker,
    required this.expenseAccountCode,
    required this.expenseAccountName,
    required this.taxPayableAccountCode,
    required this.taxPayableAccountName,
    required this.preparationId,
    required this.journalEntryId,
    required this.journalStatus,
    required this.entryNumber,
    required this.fiscalPeriodId,
    required this.preparedByUserId,
    required this.preparedAt,
    required this.postingId,
    required this.confirmationDigest,
    required this.postedByUserId,
    required this.postedAt,
    required this.accountingStatus,
    required this.accountingBlocker,
  });
  final String taxType;
  final String evidenceId;
  final int evidenceVersion;
  final String sourceId;
  final String loanId;
  final String clientId;
  final String recognitionDate;
  final String taxDue;
  final String evidenceDigest;
  final String evidenceStatus;
  final String? evidenceBlocker;
  final String? expenseAccountCode;
  final String? expenseAccountName;
  final String? taxPayableAccountCode;
  final String? taxPayableAccountName;
  final String? preparationId;
  final String? journalEntryId;
  final String? journalStatus;
  final String? entryNumber;
  final String? fiscalPeriodId;
  final String? preparedByUserId;
  final DateTime? preparedAt;
  final String? postingId;
  final String? confirmationDigest;
  final String? postedByUserId;
  final DateTime? postedAt;
  final String accountingStatus;
  final String? accountingBlocker;

  bool get isEvidenceReady => accountingStatus == 'evidence_ready';
  bool get isPrepared => accountingStatus == 'prepared_not_posted';
  bool get isPosted => accountingStatus == 'posted';

  factory TaxLiabilityItem.fromPayload(Map<String, dynamic> payload) {
    _requireLiabilityPolicy(payload);
    final item = TaxLiabilityItem(
      taxType: taxTypeValue(payload, 'tax_type'),
      evidenceId: taxUuid(payload, 'evidence_id'),
      evidenceVersion: taxPositiveInt(payload, 'evidence_version'),
      sourceId: taxUuid(payload, 'source_id'),
      loanId: taxUuid(payload, 'loan_id'),
      clientId: taxUuid(payload, 'client_id'),
      recognitionDate: taxDate(payload, 'recognition_date'),
      taxDue: taxMoney(payload, 'tax_due'),
      evidenceDigest: taxDigest(payload, 'evidence_digest'),
      evidenceStatus: taxText(payload, 'evidence_status'),
      evidenceBlocker: taxOptionalText(payload, 'evidence_blocker'),
      expenseAccountCode: taxOptionalText(payload, 'expense_account_code'),
      expenseAccountName: taxOptionalText(payload, 'expense_account_name'),
      taxPayableAccountCode: taxOptionalText(
        payload,
        'tax_payable_account_code',
      ),
      taxPayableAccountName: taxOptionalText(
        payload,
        'tax_payable_account_name',
      ),
      preparationId: taxOptionalUuid(payload, 'preparation_id'),
      journalEntryId: taxOptionalUuid(payload, 'journal_entry_id'),
      journalStatus: _optionalJournalStatus(payload),
      entryNumber: taxOptionalText(payload, 'entry_number'),
      fiscalPeriodId: taxOptionalUuid(payload, 'fiscal_period_id'),
      preparedByUserId: taxOptionalUuid(payload, 'prepared_by_user_id'),
      preparedAt: taxOptionalDateTime(payload, 'prepared_at'),
      postingId: taxOptionalUuid(payload, 'posting_id'),
      confirmationDigest: taxOptionalDigest(payload, 'confirmation_digest'),
      postedByUserId: taxOptionalUuid(payload, 'posted_by_user_id'),
      postedAt: taxOptionalDateTime(payload, 'posted_at'),
      accountingStatus: taxEnum(
        payload,
        'accounting_status',
        taxLiabilityStatuses,
      ),
      accountingBlocker: taxOptionalText(payload, 'accounting_blocker'),
    );
    item._validateState();
    return item;
  }

  void requirePrepareCoordinates() {
    if (!isEvidenceReady ||
        taxDue == '0.00' ||
        expenseAccountCode == null ||
        taxPayableAccountCode == null ||
        preparationId != null ||
        journalEntryId != null ||
        fiscalPeriodId != null ||
        accountingBlocker != null) {
      throw ArgumentError('Exact evidence-ready tax coordinates are required.');
    }
  }

  void requirePostCoordinates() {
    if (!isPrepared ||
        preparationId == null ||
        journalEntryId == null ||
        journalStatus != 'draft' ||
        fiscalPeriodId == null ||
        preparedByUserId == null ||
        preparedAt == null ||
        expenseAccountCode == null ||
        taxPayableAccountCode == null) {
      throw ArgumentError(
        'Exact prepared tax-liability coordinates are required.',
      );
    }
  }

  void _validateState() {
    try {
      if (isEvidenceReady) requirePrepareCoordinates();
      if (isPrepared) requirePostCoordinates();
    } on ArgumentError {
      throw invalidTaxPayload('liability action coordinates');
    }
    if (isPosted &&
        (postingId == null ||
            journalEntryId == null ||
            journalStatus != 'posted' ||
            entryNumber == null ||
            fiscalPeriodId == null ||
            confirmationDigest == null ||
            postedByUserId == null ||
            postedAt == null)) {
      throw invalidTaxPayload('posted liability state');
    }
  }
}

const taxLiabilityFilters = <String>{
  'all',
  'ready',
  'prepared',
  'posted',
  'adjustment_review',
  'adjusted',
  'covered',
  'blocked',
};

const taxLiabilityStatuses = <String>{
  'evidence_ready',
  'prepared_not_posted',
  'posted',
  'no_liability_required',
  'posted_adjustment_review_required',
  'posted_adjusted_reversed',
  'posted_adjusted_recoverable',
  'covered_by_settled_adjustment',
  'blocked_evidence',
  'blocked_untracked_journal_state',
  'prepared_blocked_revalidation',
  'blocked_accounts',
  'blocked_no_open_period',
};

void _requireLiabilityPolicy(Map<String, dynamic> payload) {
  if (!taxBool(payload, 'protected_tax_liability_posting_enabled') ||
      !taxBool(payload, 'tax_settlement_enabled') ||
      !taxBool(payload, 'tax_adjustment_reversal_enabled') ||
      taxBool(payload, 'automatic_source_posting')) {
    throw invalidTaxPayload('liability item policy');
  }
}

String? _optionalJournalStatus(Map<String, dynamic> payload) {
  if (payload['journal_status'] == null) return null;
  return taxEnum(payload, 'journal_status', const <String>{'draft', 'posted'});
}
