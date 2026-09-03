import 'package:gilbic_mobile/src/core/management/tax_value.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class TaxRecoverableWorkspace {
  const TaxRecoverableWorkspace({required this.refunds, required this.credits});
  final TaxRecoverableRefundOverview refunds;
  final TaxRecoverableCreditOverview credits;
}

class TaxRecoverableSummary {
  const TaxRecoverableSummary({
    required this.evidenceCount,
    required this.readyCount,
    required this.preparedCount,
    required this.completedCount,
    required this.blockedCount,
    required this.completedTotal,
  });
  final int evidenceCount;
  final int readyCount;
  final int preparedCount;
  final int completedCount;
  final int blockedCount;
  final String completedTotal;

  factory TaxRecoverableSummary.refund(Map<String, dynamic> payload) =>
      TaxRecoverableSummary(
        evidenceCount: taxNonNegativeInt(payload, 'refund_evidence_count'),
        readyCount: taxNonNegativeInt(payload, 'ready_to_prepare_count'),
        preparedCount: taxNonNegativeInt(payload, 'prepared_count'),
        completedCount: taxNonNegativeInt(payload, 'realized_count'),
        blockedCount: taxNonNegativeInt(payload, 'blocked_count'),
        completedTotal: taxMoney(payload, 'realized_refund_total'),
      );

  factory TaxRecoverableSummary.credit(Map<String, dynamic> payload) =>
      TaxRecoverableSummary(
        evidenceCount: taxNonNegativeInt(payload, 'credit_evidence_count'),
        readyCount: taxNonNegativeInt(payload, 'ready_to_prepare_count'),
        preparedCount: taxNonNegativeInt(payload, 'prepared_count'),
        completedCount: taxNonNegativeInt(payload, 'applied_count'),
        blockedCount: taxNonNegativeInt(payload, 'blocked_count'),
        completedTotal: taxMoney(payload, 'applied_credit_total'),
      );
}

class TaxRecoverableRefundPermissions {
  const TaxRecoverableRefundPermissions({
    required this.evidenceRecord,
    required this.prepare,
    required this.post,
  });
  final bool evidenceRecord;
  final bool prepare;
  final bool post;

  factory TaxRecoverableRefundPermissions.fromPayload(
    Map<String, dynamic> payload,
  ) => TaxRecoverableRefundPermissions(
    evidenceRecord: taxBool(payload, 'refund_evidence_record'),
    prepare: taxBool(payload, 'refund_prepare'),
    post: taxBool(payload, 'refund_post'),
  );
}

class TaxRecoverableCreditPermissions {
  const TaxRecoverableCreditPermissions({
    required this.evidenceRecord,
    required this.prepare,
    required this.post,
  });
  final bool evidenceRecord;
  final bool prepare;
  final bool post;

  factory TaxRecoverableCreditPermissions.fromPayload(
    Map<String, dynamic> payload,
  ) => TaxRecoverableCreditPermissions(
    evidenceRecord: taxBool(payload, 'credit_evidence_record'),
    prepare: taxBool(payload, 'credit_prepare'),
    post: taxBool(payload, 'credit_post'),
  );
}

class TaxRecoverableRefundOverview {
  const TaxRecoverableRefundOverview({
    required this.summary,
    required this.items,
    required this.candidates,
    required this.permissions,
    required this.status,
    required this.limit,
    required this.offset,
    required this.notice,
  });
  final TaxRecoverableSummary summary;
  final List<TaxRecoverableRefundItem> items;
  final List<TaxRecoverableRefundCandidate> candidates;
  final TaxRecoverableRefundPermissions permissions;
  final String status;
  final int limit;
  final int offset;
  final String notice;

  factory TaxRecoverableRefundOverview.fromPayload(
    Map<String, dynamic> payload,
  ) {
    _requirePolicy(payload);
    final rawItems = payload['items'];
    final rawCandidates = payload['refund_candidates'];
    if (rawItems is! List || rawCandidates is! List) {
      throw invalidTaxPayload('recoverable refund collections');
    }
    final result = TaxRecoverableRefundOverview(
      summary: TaxRecoverableSummary.refund(stringMap(payload['summary'])),
      items: rawItems
          .map((item) => TaxRecoverableRefundItem.fromPayload(stringMap(item)))
          .toList(growable: false),
      candidates: rawCandidates
          .map(
            (item) =>
                TaxRecoverableRefundCandidate.fromPayload(stringMap(item)),
          )
          .toList(growable: false),
      permissions: TaxRecoverableRefundPermissions.fromPayload(
        stringMap(payload['permissions']),
      ),
      status: taxEnum(payload, 'refund_status', refundStatusFilters),
      limit: taxPositiveInt(payload, 'limit'),
      offset: taxNonNegativeInt(payload, 'offset'),
      notice: taxText(payload, 'notice'),
    );
    if (result.limit > 200) throw invalidTaxPayload('recoverable refund limit');
    return result;
  }
}

class TaxRecoverableCreditOverview {
  const TaxRecoverableCreditOverview({
    required this.summary,
    required this.items,
    required this.candidates,
    required this.permissions,
    required this.status,
    required this.limit,
    required this.offset,
    required this.notice,
  });
  final TaxRecoverableSummary summary;
  final List<TaxRecoverableCreditItem> items;
  final List<TaxRecoverableCreditCandidate> candidates;
  final TaxRecoverableCreditPermissions permissions;
  final String status;
  final int limit;
  final int offset;
  final String notice;

  factory TaxRecoverableCreditOverview.fromPayload(
    Map<String, dynamic> payload,
  ) {
    _requirePolicy(payload);
    final rawItems = payload['items'];
    final rawCandidates = payload['credit_candidates'];
    if (rawItems is! List || rawCandidates is! List) {
      throw invalidTaxPayload('recoverable credit collections');
    }
    final result = TaxRecoverableCreditOverview(
      summary: TaxRecoverableSummary.credit(stringMap(payload['summary'])),
      items: rawItems
          .map((item) => TaxRecoverableCreditItem.fromPayload(stringMap(item)))
          .toList(growable: false),
      candidates: rawCandidates
          .map(
            (item) =>
                TaxRecoverableCreditCandidate.fromPayload(stringMap(item)),
          )
          .toList(growable: false),
      permissions: TaxRecoverableCreditPermissions.fromPayload(
        stringMap(payload['permissions']),
      ),
      status: taxEnum(payload, 'credit_status', creditStatusFilters),
      limit: taxPositiveInt(payload, 'limit'),
      offset: taxNonNegativeInt(payload, 'offset'),
      notice: taxText(payload, 'notice'),
    );
    if (result.limit > 200) throw invalidTaxPayload('recoverable credit limit');
    return result;
  }
}

class TaxRecoverableRefundCandidate {
  const TaxRecoverableRefundCandidate({
    required this.adjustmentPostingId,
    required this.adjustmentEvidenceId,
    required this.taxType,
    required this.sourceId,
    required this.loanId,
    required this.clientId,
    required this.recoverableAmount,
    required this.minimumRefundDate,
    required this.adjustmentEvidenceDigest,
    required this.entryNumber,
    required this.fiscalPeriodId,
  });
  final String adjustmentPostingId;
  final String adjustmentEvidenceId;
  final String taxType;
  final String sourceId;
  final String loanId;
  final String clientId;
  final String recoverableAmount;
  final String minimumRefundDate;
  final String adjustmentEvidenceDigest;
  final String entryNumber;
  final String fiscalPeriodId;

  factory TaxRecoverableRefundCandidate.fromPayload(
    Map<String, dynamic> payload,
  ) => TaxRecoverableRefundCandidate(
    adjustmentPostingId: taxUuid(payload, 'adjustment_posting_id'),
    adjustmentEvidenceId: taxUuid(payload, 'adjustment_evidence_id'),
    taxType: taxTypeValue(payload, 'tax_type'),
    sourceId: taxUuid(payload, 'source_id'),
    loanId: taxUuid(payload, 'loan_id'),
    clientId: taxUuid(payload, 'client_id'),
    recoverableAmount: taxPositiveMoney(payload, 'recoverable_amount'),
    minimumRefundDate: taxDate(payload, 'minimum_refund_date'),
    adjustmentEvidenceDigest: taxDigest(payload, 'adjustment_evidence_digest'),
    entryNumber: taxText(payload, 'entry_number'),
    fiscalPeriodId: taxUuid(payload, 'fiscal_period_id'),
  );
}

class TaxRecoverableCreditCandidate {
  TaxRecoverableCreditCandidate._({
    required this.adjustmentPostingId,
    required this.adjustmentEvidenceId,
    required this.taxType,
    required this.sourceId,
    required this.loanId,
    required this.clientId,
    required this.creditAmount,
    required this.targetTaxReturnId,
    required this.targetPeriodStart,
    required this.targetPeriodEnd,
    required this.targetFilingDate,
    required this.targetDeclaredTaxDue,
    required this.targetReturnReference,
    required this.targetReturnEvidenceDigest,
    required this.minimumApplicationDate,
    required this.adjustmentEvidenceDigest,
    required this.entryNumber,
    required this.fiscalPeriodId,
  });
  final String adjustmentPostingId;
  final String adjustmentEvidenceId;
  final String taxType;
  final String sourceId;
  final String loanId;
  final String clientId;
  final String creditAmount;
  final String targetTaxReturnId;
  final String targetPeriodStart;
  final String targetPeriodEnd;
  final String targetFilingDate;
  final String targetDeclaredTaxDue;
  final String targetReturnReference;
  final String targetReturnEvidenceDigest;
  final String minimumApplicationDate;
  final String adjustmentEvidenceDigest;
  final String entryNumber;
  final String fiscalPeriodId;

  factory TaxRecoverableCreditCandidate.fromPayload(
    Map<String, dynamic> payload,
  ) {
    final result = TaxRecoverableCreditCandidate._(
      adjustmentPostingId: taxUuid(payload, 'adjustment_posting_id'),
      adjustmentEvidenceId: taxUuid(payload, 'adjustment_evidence_id'),
      taxType: taxTypeValue(payload, 'tax_type'),
      sourceId: taxUuid(payload, 'source_id'),
      loanId: taxUuid(payload, 'loan_id'),
      clientId: taxUuid(payload, 'client_id'),
      creditAmount: taxPositiveMoney(payload, 'credit_amount'),
      targetTaxReturnId: taxUuid(payload, 'target_tax_return_id'),
      targetPeriodStart: taxDate(payload, 'target_return_period_start'),
      targetPeriodEnd: taxDate(payload, 'target_return_period_end'),
      targetFilingDate: taxDate(payload, 'target_filing_date'),
      targetDeclaredTaxDue: taxPositiveMoney(
        payload,
        'target_declared_tax_due',
      ),
      targetReturnReference: taxText(payload, 'target_return_reference'),
      targetReturnEvidenceDigest: taxDigest(
        payload,
        'target_return_evidence_digest',
      ),
      minimumApplicationDate: taxDate(payload, 'minimum_application_date'),
      adjustmentEvidenceDigest: taxDigest(
        payload,
        'adjustment_evidence_digest',
      ),
      entryNumber: taxText(payload, 'entry_number'),
      fiscalPeriodId: taxUuid(payload, 'fiscal_period_id'),
    );
    if (result.creditAmount != result.targetDeclaredTaxDue ||
        DateTime.parse(
          result.targetPeriodEnd,
        ).isBefore(DateTime.parse(result.targetPeriodStart)) ||
        DateTime.parse(
          result.minimumApplicationDate,
        ).isBefore(DateTime.parse(result.targetFilingDate))) {
      throw invalidTaxPayload('recoverable credit candidate derivation');
    }
    return result;
  }
}

class TaxRecoverableRefundItem {
  TaxRecoverableRefundItem._({
    required this.refundEvidenceId,
    required this.adjustmentPostingId,
    required this.taxType,
    required this.refundAmount,
    required this.refundDate,
    required this.cashAccountCode,
    required this.refundReference,
    required this.evidenceDigest,
    required this.preparationId,
    required this.journalEntryId,
    required this.journalStatus,
    required this.fiscalPeriodId,
    required this.taxRecoverableAccountCode,
    required this.refundPostingId,
    required this.confirmationDigest,
    required this.refundStatus,
    required this.refundBlocker,
  });
  final String refundEvidenceId;
  final String adjustmentPostingId;
  final String taxType;
  final String refundAmount;
  final String refundDate;
  final String cashAccountCode;
  final String refundReference;
  final String evidenceDigest;
  final String? preparationId;
  final String? journalEntryId;
  final String? journalStatus;
  final String? fiscalPeriodId;
  final String? taxRecoverableAccountCode;
  final String? refundPostingId;
  final String? confirmationDigest;
  final String refundStatus;
  final String? refundBlocker;

  bool get isEvidenceReady => refundStatus == 'refund_evidence_ready';
  bool get isPrepared => refundStatus == 'refund_prepared';
  bool get isRealized => refundStatus == 'refund_realized';

  factory TaxRecoverableRefundItem.fromPayload(Map<String, dynamic> payload) {
    _requireRefundItemPolicy(payload);
    final result = TaxRecoverableRefundItem._(
      refundEvidenceId: taxUuid(payload, 'refund_evidence_id'),
      adjustmentPostingId: taxUuid(payload, 'adjustment_posting_id'),
      taxType: taxTypeValue(payload, 'tax_type'),
      refundAmount: taxPositiveMoney(payload, 'refund_amount'),
      refundDate: taxDate(payload, 'refund_date'),
      cashAccountCode: taxEnum(payload, 'cash_account_code', const <String>{
        '1010',
        '1030',
      }),
      refundReference: taxText(payload, 'refund_reference'),
      evidenceDigest: taxDigest(payload, 'evidence_digest'),
      preparationId: taxOptionalUuid(payload, 'preparation_id'),
      journalEntryId: taxOptionalUuid(payload, 'journal_entry_id'),
      journalStatus: _journalStatus(payload),
      fiscalPeriodId: taxOptionalUuid(payload, 'fiscal_period_id'),
      taxRecoverableAccountCode: taxOptionalText(
        payload,
        'tax_recoverable_account_code',
      ),
      refundPostingId: taxOptionalUuid(payload, 'refund_posting_id'),
      confirmationDigest: taxOptionalDigest(payload, 'confirmation_digest'),
      refundStatus: taxEnum(payload, 'refund_status', refundStatuses),
      refundBlocker: taxOptionalText(payload, 'refund_blocker'),
    );
    result._validate();
    return result;
  }

  void requirePrepare() {
    if (!isEvidenceReady || preparationId != null || refundPostingId != null) {
      throw ArgumentError('Exact refund evidence-ready item is required.');
    }
  }

  void requirePost() {
    if (!isPrepared ||
        preparationId == null ||
        journalEntryId == null ||
        journalStatus != 'draft' ||
        fiscalPeriodId == null ||
        taxRecoverableAccountCode != '1130' ||
        refundPostingId != null) {
      throw ArgumentError('Exact prepared refund coordinates are required.');
    }
  }

  void _validate() {
    try {
      if (isEvidenceReady) requirePrepare();
      if (isPrepared) requirePost();
    } on ArgumentError {
      throw invalidTaxPayload('recoverable refund lifecycle');
    }
    if (isRealized &&
        (preparationId == null ||
            journalEntryId == null ||
            journalStatus != 'posted' ||
            fiscalPeriodId == null ||
            taxRecoverableAccountCode != '1130' ||
            refundPostingId == null ||
            confirmationDigest == null)) {
      throw invalidTaxPayload('realized recoverable refund state');
    }
  }
}

class TaxRecoverableCreditItem {
  TaxRecoverableCreditItem._({
    required this.creditEvidenceId,
    required this.adjustmentPostingId,
    required this.taxType,
    required this.targetTaxReturnId,
    required this.targetDeclaredTaxDue,
    required this.creditAmount,
    required this.applicationDate,
    required this.applicationReference,
    required this.evidenceDigest,
    required this.preparationId,
    required this.journalEntryId,
    required this.journalStatus,
    required this.fiscalPeriodId,
    required this.taxPayableAccountCode,
    required this.taxRecoverableAccountCode,
    required this.creditPostingId,
    required this.confirmationDigest,
    required this.creditStatus,
    required this.creditBlocker,
  });
  final String creditEvidenceId;
  final String adjustmentPostingId;
  final String taxType;
  final String targetTaxReturnId;
  final String targetDeclaredTaxDue;
  final String creditAmount;
  final String applicationDate;
  final String applicationReference;
  final String evidenceDigest;
  final String? preparationId;
  final String? journalEntryId;
  final String? journalStatus;
  final String? fiscalPeriodId;
  final String? taxPayableAccountCode;
  final String? taxRecoverableAccountCode;
  final String? creditPostingId;
  final String? confirmationDigest;
  final String creditStatus;
  final String? creditBlocker;

  bool get isEvidenceReady => creditStatus == 'credit_evidence_ready';
  bool get isPrepared => creditStatus == 'credit_prepared';
  bool get isApplied => creditStatus == 'credit_applied';

  factory TaxRecoverableCreditItem.fromPayload(Map<String, dynamic> payload) {
    _requirePolicy(payload);
    final result = TaxRecoverableCreditItem._(
      creditEvidenceId: taxUuid(payload, 'credit_evidence_id'),
      adjustmentPostingId: taxUuid(payload, 'adjustment_posting_id'),
      taxType: taxTypeValue(payload, 'tax_type'),
      targetTaxReturnId: taxUuid(payload, 'target_tax_return_id'),
      targetDeclaredTaxDue: taxPositiveMoney(
        payload,
        'target_declared_tax_due',
      ),
      creditAmount: taxPositiveMoney(payload, 'credit_amount'),
      applicationDate: taxDate(payload, 'application_date'),
      applicationReference: taxText(payload, 'application_reference'),
      evidenceDigest: taxDigest(payload, 'evidence_digest'),
      preparationId: taxOptionalUuid(payload, 'preparation_id'),
      journalEntryId: taxOptionalUuid(payload, 'journal_entry_id'),
      journalStatus: _journalStatus(payload),
      fiscalPeriodId: taxOptionalUuid(payload, 'fiscal_period_id'),
      taxPayableAccountCode: taxOptionalText(
        payload,
        'tax_payable_account_code',
      ),
      taxRecoverableAccountCode: taxOptionalText(
        payload,
        'tax_recoverable_account_code',
      ),
      creditPostingId: taxOptionalUuid(payload, 'credit_posting_id'),
      confirmationDigest: taxOptionalDigest(payload, 'confirmation_digest'),
      creditStatus: taxEnum(payload, 'credit_status', creditStatuses),
      creditBlocker: taxOptionalText(payload, 'credit_blocker'),
    );
    result._validate();
    return result;
  }

  void requirePrepare() {
    if (!isEvidenceReady || preparationId != null || creditPostingId != null) {
      throw ArgumentError('Exact credit evidence-ready item is required.');
    }
  }

  void requirePost() {
    if (!isPrepared ||
        preparationId == null ||
        journalEntryId == null ||
        journalStatus != 'draft' ||
        fiscalPeriodId == null ||
        taxPayableAccountCode != '2100' ||
        taxRecoverableAccountCode != '1130' ||
        creditPostingId != null) {
      throw ArgumentError('Exact prepared credit coordinates are required.');
    }
  }

  void _validate() {
    if (creditAmount != targetDeclaredTaxDue) {
      throw invalidTaxPayload('recoverable credit amount');
    }
    try {
      if (isEvidenceReady) requirePrepare();
      if (isPrepared) requirePost();
    } on ArgumentError {
      throw invalidTaxPayload('recoverable credit lifecycle');
    }
    if (isApplied &&
        (preparationId == null ||
            journalEntryId == null ||
            journalStatus != 'posted' ||
            fiscalPeriodId == null ||
            taxPayableAccountCode != '2100' ||
            taxRecoverableAccountCode != '1130' ||
            creditPostingId == null ||
            confirmationDigest == null)) {
      throw invalidTaxPayload('applied recoverable credit state');
    }
  }
}

const refundStatusFilters = <String>{
  'all',
  'ready',
  'prepared',
  'realized',
  'blocked',
};
const creditStatusFilters = <String>{
  'all',
  'ready',
  'prepared',
  'applied',
  'blocked',
};
const refundStatuses = <String>{
  'refund_evidence_ready',
  'refund_prepared',
  'refund_realized',
  'blocked_competing_credit_evidence',
  'blocked_recoverable_not_current',
  'blocked_cash_account',
  'blocked_untracked_refund_journal_state',
  'blocked_no_open_refund_period',
};
const creditStatuses = <String>{
  'credit_evidence_ready',
  'credit_prepared',
  'credit_applied',
  'blocked_recoverable_not_current',
  'blocked_competing_refund_evidence',
  'blocked_target_cash_settlement',
  'blocked_target_amendment',
  'blocked_target_return_changed',
  'blocked_tax_payable_account',
  'blocked_tax_recoverable_account',
  'blocked_untracked_credit_journal_state',
  'blocked_no_open_application_period',
};

void _requirePolicy(Map<String, dynamic> payload) {
  if (!taxBool(payload, 'tax_recoverable_refund_realization_enabled') ||
      !taxBool(payload, 'tax_recoverable_credit_application_enabled') ||
      taxBool(payload, 'partial_tax_recoverable_realization_enabled') ||
      taxBool(payload, 'automatic_source_posting')) {
    throw invalidTaxPayload('recoverable realization policy');
  }
}

void _requireRefundItemPolicy(Map<String, dynamic> payload) {
  if (!taxBool(payload, 'tax_recoverable_refund_realization_enabled') ||
      !taxBool(payload, 'tax_recoverable_credit_application_enabled') ||
      taxBool(payload, 'automatic_source_posting')) {
    throw invalidTaxPayload('recoverable refund policy');
  }
}

String? _journalStatus(Map<String, dynamic> payload) {
  if (payload['journal_status'] == null) return null;
  return taxEnum(payload, 'journal_status', const <String>{'draft', 'posted'});
}
