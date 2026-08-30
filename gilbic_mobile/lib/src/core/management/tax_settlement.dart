import 'package:gilbic_mobile/src/core/management/tax_value.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class TaxSettlementOverview {
  const TaxSettlementOverview({
    required this.summary,
    required this.items,
    required this.returnLiabilityCandidates,
    required this.permissions,
    required this.settlementStatus,
    required this.limit,
    required this.offset,
    required this.notice,
  });

  final TaxSettlementSummary summary;
  final List<TaxSettlementItem> items;
  final List<TaxReturnLiabilityCandidate> returnLiabilityCandidates;
  final TaxSettlementPermissions permissions;
  final String settlementStatus;
  final int limit;
  final int offset;
  final String notice;

  factory TaxSettlementOverview.fromPayload(Map<String, dynamic> payload) {
    _requireSettlementPolicy(payload);
    final rawItems = payload['items'];
    final rawCandidates = payload['return_liability_candidates'];
    if (rawItems is! List || rawCandidates is! List) {
      throw invalidTaxPayload('settlement collections');
    }
    final result = TaxSettlementOverview(
      summary: TaxSettlementSummary.fromPayload(stringMap(payload['summary'])),
      items: rawItems
          .map((value) => TaxSettlementItem.fromPayload(stringMap(value)))
          .toList(growable: false),
      returnLiabilityCandidates: rawCandidates
          .map(
            (value) =>
                TaxReturnLiabilityCandidate.fromPayload(stringMap(value)),
          )
          .toList(growable: false),
      permissions: TaxSettlementPermissions.fromPayload(
        stringMap(payload['permissions']),
      ),
      settlementStatus: taxEnum(
        payload,
        'settlement_status',
        taxSettlementFilters,
      ),
      limit: taxPositiveInt(payload, 'limit'),
      offset: taxNonNegativeInt(payload, 'offset'),
      notice: taxText(payload, 'notice'),
    );
    if (result.limit > 200) throw invalidTaxPayload('settlement limit');
    return result;
  }
}

class TaxSettlementSummary {
  const TaxSettlementSummary({
    required this.returnCount,
    required this.awaitingPaymentEvidenceCount,
    required this.readyToPrepareCount,
    required this.preparedCount,
    required this.settledCount,
    required this.settledAdjustmentReviewCount,
    required this.settledAdjustmentInProgressCount,
    required this.settledAdjustmentRecordedCount,
    required this.blockedCount,
    required this.settledTaxTotal,
  });
  final int returnCount;
  final int awaitingPaymentEvidenceCount;
  final int readyToPrepareCount;
  final int preparedCount;
  final int settledCount;
  final int settledAdjustmentReviewCount;
  final int settledAdjustmentInProgressCount;
  final int settledAdjustmentRecordedCount;
  final int blockedCount;
  final String settledTaxTotal;

  factory TaxSettlementSummary.fromPayload(Map<String, dynamic> payload) {
    _requireSettlementPolicy(payload);
    return TaxSettlementSummary(
      returnCount: taxNonNegativeInt(payload, 'return_count'),
      awaitingPaymentEvidenceCount: taxNonNegativeInt(
        payload,
        'awaiting_payment_evidence_count',
      ),
      readyToPrepareCount: taxNonNegativeInt(payload, 'ready_to_prepare_count'),
      preparedCount: taxNonNegativeInt(payload, 'prepared_count'),
      settledCount: taxNonNegativeInt(payload, 'settled_count'),
      settledAdjustmentReviewCount: taxNonNegativeInt(
        payload,
        'settled_adjustment_review_count',
      ),
      settledAdjustmentInProgressCount: taxNonNegativeInt(
        payload,
        'settled_adjustment_in_progress_count',
      ),
      settledAdjustmentRecordedCount: taxNonNegativeInt(
        payload,
        'settled_adjustment_recorded_count',
      ),
      blockedCount: taxNonNegativeInt(payload, 'blocked_count'),
      settledTaxTotal: taxMoney(payload, 'settled_tax_total'),
    );
  }
}

class TaxSettlementPermissions {
  const TaxSettlementPermissions({
    required this.returnEvidenceRecord,
    required this.paymentEvidenceRecord,
    required this.settlementPrepare,
    required this.settlementPost,
  });
  final bool returnEvidenceRecord;
  final bool paymentEvidenceRecord;
  final bool settlementPrepare;
  final bool settlementPost;
  factory TaxSettlementPermissions.fromPayload(Map<String, dynamic> payload) =>
      TaxSettlementPermissions(
        returnEvidenceRecord: taxBool(payload, 'return_evidence_record'),
        paymentEvidenceRecord: taxBool(payload, 'payment_evidence_record'),
        settlementPrepare: taxBool(payload, 'settlement_prepare'),
        settlementPost: taxBool(payload, 'settlement_post'),
      );
}

class TaxReturnLiabilityCandidate {
  const TaxReturnLiabilityCandidate({
    required this.taxType,
    required this.postingId,
    required this.evidenceId,
    required this.evidenceVersion,
    required this.sourceId,
    required this.loanId,
    required this.clientId,
    required this.recognitionDate,
    required this.taxDue,
    required this.evidenceDigest,
    required this.entryNumber,
    required this.fiscalPeriodId,
  });
  final String taxType;
  final String postingId;
  final String evidenceId;
  final int evidenceVersion;
  final String sourceId;
  final String loanId;
  final String clientId;
  final String recognitionDate;
  final String taxDue;
  final String evidenceDigest;
  final String entryNumber;
  final String fiscalPeriodId;

  factory TaxReturnLiabilityCandidate.fromPayload(
    Map<String, dynamic> payload,
  ) => TaxReturnLiabilityCandidate(
    taxType: taxTypeValue(payload, 'tax_type'),
    postingId: taxUuid(payload, 'posting_id'),
    evidenceId: taxUuid(payload, 'evidence_id'),
    evidenceVersion: taxPositiveInt(payload, 'evidence_version'),
    sourceId: taxUuid(payload, 'source_id'),
    loanId: taxUuid(payload, 'loan_id'),
    clientId: taxUuid(payload, 'client_id'),
    recognitionDate: taxDate(payload, 'recognition_date'),
    taxDue: taxPositiveMoney(payload, 'tax_due'),
    evidenceDigest: taxDigest(payload, 'evidence_digest'),
    entryNumber: taxText(payload, 'entry_number'),
    fiscalPeriodId: taxUuid(payload, 'fiscal_period_id'),
  );
}

class TaxSettlementItem {
  const TaxSettlementItem({
    required this.taxReturnId,
    required this.taxType,
    required this.returnPeriodStart,
    required this.returnPeriodEnd,
    required this.filingDate,
    required this.declaredTaxDue,
    required this.returnReference,
    required this.returnEvidenceReference,
    required this.returnEvidenceDigest,
    required this.returnRecordedByUserId,
    required this.returnRecordedAt,
    required this.liabilityCount,
    required this.currentExactCount,
    required this.liabilityTotal,
    required this.paymentEvidenceId,
    required this.paymentDate,
    required this.paymentAmount,
    required this.cashAccountSystemKey,
    required this.cashAccountCode,
    required this.cashAccountName,
    required this.taxPayableAccountCode,
    required this.taxPayableAccountName,
    required this.paymentReference,
    required this.paymentEvidenceReference,
    required this.paymentEvidenceDigest,
    required this.paymentRecordedByUserId,
    required this.paymentRecordedAt,
    required this.preparationId,
    required this.journalEntryId,
    required this.journalStatus,
    required this.entryNumber,
    required this.fiscalPeriodId,
    required this.preparedByUserId,
    required this.preparedAt,
    required this.settlementPostingId,
    required this.confirmationDigest,
    required this.postedByUserId,
    required this.postedAt,
    required this.settlementStatus,
    required this.settlementBlocker,
  });
  final String taxReturnId;
  final String taxType;
  final String returnPeriodStart;
  final String returnPeriodEnd;
  final String filingDate;
  final String declaredTaxDue;
  final String returnReference;
  final String returnEvidenceReference;
  final String returnEvidenceDigest;
  final String returnRecordedByUserId;
  final DateTime returnRecordedAt;
  final int liabilityCount;
  final int currentExactCount;
  final String liabilityTotal;
  final String? paymentEvidenceId;
  final String? paymentDate;
  final String? paymentAmount;
  final String? cashAccountSystemKey;
  final String? cashAccountCode;
  final String? cashAccountName;
  final String? taxPayableAccountCode;
  final String? taxPayableAccountName;
  final String? paymentReference;
  final String? paymentEvidenceReference;
  final String? paymentEvidenceDigest;
  final String? paymentRecordedByUserId;
  final DateTime? paymentRecordedAt;
  final String? preparationId;
  final String? journalEntryId;
  final String? journalStatus;
  final String? entryNumber;
  final String? fiscalPeriodId;
  final String? preparedByUserId;
  final DateTime? preparedAt;
  final String? settlementPostingId;
  final String? confirmationDigest;
  final String? postedByUserId;
  final DateTime? postedAt;
  final String settlementStatus;
  final String? settlementBlocker;

  bool get isAwaitingPayment =>
      settlementStatus == 'return_recorded_awaiting_payment';
  bool get isReady => settlementStatus == 'payment_evidence_ready';
  bool get isPrepared => settlementStatus == 'settlement_prepared';
  bool get isSettled => settlementStatus == 'settled';

  factory TaxSettlementItem.fromPayload(Map<String, dynamic> payload) {
    _requireSettlementPolicy(payload);
    final item = TaxSettlementItem(
      taxReturnId: taxUuid(payload, 'tax_return_id'),
      taxType: taxTypeValue(payload, 'tax_type'),
      returnPeriodStart: taxDate(payload, 'return_period_start'),
      returnPeriodEnd: taxDate(payload, 'return_period_end'),
      filingDate: taxDate(payload, 'filing_date'),
      declaredTaxDue: taxPositiveMoney(payload, 'declared_tax_due'),
      returnReference: taxText(payload, 'return_reference'),
      returnEvidenceReference: taxText(payload, 'return_evidence_reference'),
      returnEvidenceDigest: taxDigest(payload, 'return_evidence_digest'),
      returnRecordedByUserId: taxUuid(payload, 'return_recorded_by_user_id'),
      returnRecordedAt: taxDateTime(payload, 'return_recorded_at'),
      liabilityCount: taxPositiveInt(payload, 'liability_count'),
      currentExactCount: taxNonNegativeInt(payload, 'current_exact_count'),
      liabilityTotal: taxMoney(payload, 'liability_total'),
      paymentEvidenceId: taxOptionalUuid(payload, 'payment_evidence_id'),
      paymentDate: taxOptionalDate(payload, 'payment_date'),
      paymentAmount: taxOptionalMoney(payload, 'payment_amount'),
      cashAccountSystemKey: _optionalCashKey(payload),
      cashAccountCode: taxOptionalText(payload, 'cash_account_code'),
      cashAccountName: taxOptionalText(payload, 'cash_account_name'),
      taxPayableAccountCode: taxOptionalText(
        payload,
        'tax_payable_account_code',
      ),
      taxPayableAccountName: taxOptionalText(
        payload,
        'tax_payable_account_name',
      ),
      paymentReference: taxOptionalText(payload, 'payment_reference'),
      paymentEvidenceReference: taxOptionalText(
        payload,
        'payment_evidence_reference',
      ),
      paymentEvidenceDigest: taxOptionalDigest(
        payload,
        'payment_evidence_digest',
      ),
      paymentRecordedByUserId: taxOptionalUuid(
        payload,
        'payment_recorded_by_user_id',
      ),
      paymentRecordedAt: taxOptionalDateTime(payload, 'payment_recorded_at'),
      preparationId: taxOptionalUuid(payload, 'preparation_id'),
      journalEntryId: taxOptionalUuid(payload, 'journal_entry_id'),
      journalStatus: _optionalJournalStatus(payload),
      entryNumber: taxOptionalText(payload, 'entry_number'),
      fiscalPeriodId: taxOptionalUuid(payload, 'fiscal_period_id'),
      preparedByUserId: taxOptionalUuid(payload, 'prepared_by_user_id'),
      preparedAt: taxOptionalDateTime(payload, 'prepared_at'),
      settlementPostingId: taxOptionalUuid(payload, 'settlement_posting_id'),
      confirmationDigest: taxOptionalDigest(payload, 'confirmation_digest'),
      postedByUserId: taxOptionalUuid(payload, 'posted_by_user_id'),
      postedAt: taxOptionalDateTime(payload, 'posted_at'),
      settlementStatus: taxEnum(
        payload,
        'settlement_status',
        taxSettlementStatuses,
      ),
      settlementBlocker: taxOptionalText(payload, 'settlement_blocker'),
    );
    item._validate();
    return item;
  }

  void requirePaymentCoordinates() {
    if (!isAwaitingPayment || paymentEvidenceId != null) {
      throw ArgumentError('Exact return awaiting payment is required.');
    }
  }

  void requirePrepareCoordinates() {
    if (!isReady ||
        !_hasPayment ||
        taxPayableAccountCode == null ||
        taxPayableAccountName == null ||
        preparationId != null) {
      throw ArgumentError('Exact payment-ready settlement is required.');
    }
  }

  void requirePostCoordinates() {
    if (!isPrepared ||
        !_hasPayment ||
        preparationId == null ||
        journalEntryId == null ||
        journalStatus != 'draft' ||
        fiscalPeriodId == null ||
        preparedByUserId == null ||
        preparedAt == null ||
        taxPayableAccountCode == null) {
      throw ArgumentError(
        'Exact prepared settlement coordinates are required.',
      );
    }
  }

  bool get _hasPayment =>
      paymentEvidenceId != null &&
      paymentDate != null &&
      paymentAmount == declaredTaxDue &&
      cashAccountSystemKey != null &&
      cashAccountCode != null &&
      cashAccountName != null &&
      paymentReference != null &&
      paymentEvidenceReference != null &&
      paymentEvidenceDigest != null &&
      paymentRecordedByUserId != null &&
      paymentRecordedAt != null;

  void _validate() {
    if (DateTime.parse(
          returnPeriodEnd,
        ).isBefore(DateTime.parse(returnPeriodStart)) ||
        DateTime.parse(filingDate).isBefore(DateTime.parse(returnPeriodEnd)) ||
        currentExactCount > liabilityCount) {
      throw invalidTaxPayload('settlement chronology');
    }
    try {
      if (isAwaitingPayment) requirePaymentCoordinates();
      if (isReady) requirePrepareCoordinates();
      if (isPrepared) requirePostCoordinates();
    } on ArgumentError {
      throw invalidTaxPayload('settlement action coordinates');
    }
    if (isSettled &&
        (!_hasPayment ||
            preparationId == null ||
            journalEntryId == null ||
            journalStatus != 'posted' ||
            entryNumber == null ||
            fiscalPeriodId == null ||
            settlementPostingId == null ||
            confirmationDigest == null ||
            postedByUserId == null ||
            postedAt == null)) {
      throw invalidTaxPayload('settled state');
    }
  }
}

const taxSettlementFilters = <String>{
  'all',
  'awaiting_payment',
  'ready',
  'prepared',
  'settled',
  'adjustment_review',
  'adjustment_in_progress',
  'adjusted',
  'blocked',
};

const taxSettlementStatuses = <String>{
  'settled_adjustment_review_required',
  'settled',
  'blocked_return_composition_changed',
  'return_recorded_awaiting_payment',
  'blocked_payment_amount_mismatch',
  'blocked_payment_date',
  'blocked_cash_account',
  'blocked_untracked_settlement_journal_state',
  'prepared_blocked_period_revalidation',
  'settlement_prepared',
  'blocked_no_open_payment_period',
  'payment_evidence_ready',
  'settled_adjustment_in_progress',
  'settled_adjustment_recorded',
};

void _requireSettlementPolicy(Map<String, dynamic> payload) {
  if (!taxBool(payload, 'tax_settlement_enabled') ||
      !taxBool(payload, 'tax_adjustment_reversal_enabled') ||
      taxBool(payload, 'automatic_source_posting')) {
    throw invalidTaxPayload('settlement policy');
  }
}

String? _optionalCashKey(Map<String, dynamic> payload) {
  if (payload['cash_account_system_key'] == null) return null;
  return taxEnum(payload, 'cash_account_system_key', const <String>{
    'cash_office',
    'cash_bank_gcash',
  });
}

String? _optionalJournalStatus(Map<String, dynamic> payload) {
  if (payload['journal_status'] == null) return null;
  return taxEnum(payload, 'journal_status', const <String>{'draft', 'posted'});
}
