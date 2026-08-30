import 'package:gilbic_mobile/src/core/management/tax_value.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class AdditionalTaxOverview {
  const AdditionalTaxOverview({
    required this.summary,
    required this.items,
    required this.candidates,
    required this.permissions,
    required this.amendmentStatus,
    required this.limit,
    required this.offset,
    required this.notice,
  });
  final AdditionalTaxSummary summary;
  final List<AdditionalTaxItem> items;
  final List<AdditionalTaxCandidate> candidates;
  final AdditionalTaxPermissions permissions;
  final String amendmentStatus;
  final int limit;
  final int offset;
  final String notice;

  factory AdditionalTaxOverview.fromPayload(Map<String, dynamic> payload) {
    _requirePolicy(payload);
    final rawItems = payload['items'];
    final rawCandidates = payload['amendment_candidates'];
    if (rawItems is! List || rawCandidates is! List) {
      throw invalidTaxPayload('additional-tax collections');
    }
    final value = AdditionalTaxOverview(
      summary: AdditionalTaxSummary.fromPayload(stringMap(payload['summary'])),
      items: rawItems
          .map((item) => AdditionalTaxItem.fromPayload(stringMap(item)))
          .toList(growable: false),
      candidates: rawCandidates
          .map((item) => AdditionalTaxCandidate.fromPayload(stringMap(item)))
          .toList(growable: false),
      permissions: AdditionalTaxPermissions.fromPayload(
        stringMap(payload['permissions']),
      ),
      amendmentStatus: taxEnum(
        payload,
        'amendment_status',
        additionalTaxFilters,
      ),
      limit: taxPositiveInt(payload, 'limit'),
      offset: taxNonNegativeInt(payload, 'offset'),
      notice: taxText(payload, 'notice'),
    );
    if (value.limit > 200) throw invalidTaxPayload('additional-tax limit');
    return value;
  }
}

class AdditionalTaxSummary {
  const AdditionalTaxSummary({
    required this.amendmentEvidenceCount,
    required this.amendmentReadyCount,
    required this.liabilityPreparedCount,
    required this.awaitingPaymentCount,
    required this.paymentReadyCount,
    required this.settlementPreparedCount,
    required this.settledCount,
    required this.reviewCount,
    required this.blockedCount,
    required this.recognizedAdditionalTaxTotal,
    required this.settledPaymentTotal,
  });
  final int amendmentEvidenceCount;
  final int amendmentReadyCount;
  final int liabilityPreparedCount;
  final int awaitingPaymentCount;
  final int paymentReadyCount;
  final int settlementPreparedCount;
  final int settledCount;
  final int reviewCount;
  final int blockedCount;
  final String recognizedAdditionalTaxTotal;
  final String settledPaymentTotal;

  factory AdditionalTaxSummary.fromPayload(Map<String, dynamic> payload) {
    _requirePolicy(payload);
    return AdditionalTaxSummary(
      amendmentEvidenceCount: taxNonNegativeInt(
        payload,
        'amendment_evidence_count',
      ),
      amendmentReadyCount: taxNonNegativeInt(payload, 'amendment_ready_count'),
      liabilityPreparedCount: taxNonNegativeInt(
        payload,
        'liability_prepared_count',
      ),
      awaitingPaymentCount: taxNonNegativeInt(
        payload,
        'awaiting_payment_count',
      ),
      paymentReadyCount: taxNonNegativeInt(payload, 'payment_ready_count'),
      settlementPreparedCount: taxNonNegativeInt(
        payload,
        'settlement_prepared_count',
      ),
      settledCount: taxNonNegativeInt(payload, 'settled_count'),
      reviewCount: taxNonNegativeInt(payload, 'review_count'),
      blockedCount: taxNonNegativeInt(payload, 'blocked_count'),
      recognizedAdditionalTaxTotal: taxMoney(
        payload,
        'recognized_additional_tax_total',
      ),
      settledPaymentTotal: taxMoney(payload, 'settled_payment_total'),
    );
  }
}

class AdditionalTaxPermissions {
  const AdditionalTaxPermissions({
    required this.amendmentEvidenceRecord,
    required this.liabilityPrepare,
    required this.liabilityPost,
    required this.paymentEvidenceRecord,
    required this.settlementPrepare,
    required this.settlementPost,
  });
  final bool amendmentEvidenceRecord;
  final bool liabilityPrepare;
  final bool liabilityPost;
  final bool paymentEvidenceRecord;
  final bool settlementPrepare;
  final bool settlementPost;
  factory AdditionalTaxPermissions.fromPayload(Map<String, dynamic> payload) =>
      AdditionalTaxPermissions(
        amendmentEvidenceRecord: taxBool(payload, 'amendment_evidence_record'),
        liabilityPrepare: taxBool(payload, 'additional_liability_prepare'),
        liabilityPost: taxBool(payload, 'additional_liability_post'),
        paymentEvidenceRecord: taxBool(
          payload,
          'additional_payment_evidence_record',
        ),
        settlementPrepare: taxBool(payload, 'additional_settlement_prepare'),
        settlementPost: taxBool(payload, 'additional_settlement_post'),
      );
}

class AdditionalTaxCandidate {
  const AdditionalTaxCandidate({
    required this.taxType,
    required this.taxReturnId,
    required this.taxLiabilityPostingId,
    required this.originalEvidenceId,
    required this.originalEvidenceVersion,
    required this.replacementEvidenceId,
    required this.replacementEvidenceVersion,
    required this.sourceId,
    required this.loanId,
    required this.clientId,
    required this.originalDeclaredTaxDue,
    required this.revisedDeclaredTaxDue,
    required this.originalItemTaxDue,
    required this.replacementItemTaxDue,
    required this.additionalTaxDue,
    required this.paymentBasis,
    required this.paymentRequiredAmount,
    required this.filingDate,
    required this.recognitionDate,
    required this.originalEvidenceDigest,
    required this.replacementEvidenceDigest,
    required this.originalFiscalPeriodId,
    required this.originalFiscalPeriodStart,
    required this.originalFiscalPeriodEnd,
    required this.originalSettlementPostingId,
  });
  final String taxType;
  final String taxReturnId;
  final String taxLiabilityPostingId;
  final String originalEvidenceId;
  final int originalEvidenceVersion;
  final String replacementEvidenceId;
  final int replacementEvidenceVersion;
  final String sourceId;
  final String loanId;
  final String clientId;
  final String originalDeclaredTaxDue;
  final String revisedDeclaredTaxDue;
  final String originalItemTaxDue;
  final String replacementItemTaxDue;
  final String additionalTaxDue;
  final String paymentBasis;
  final String paymentRequiredAmount;
  final String filingDate;
  final String recognitionDate;
  final String originalEvidenceDigest;
  final String replacementEvidenceDigest;
  final String originalFiscalPeriodId;
  final String originalFiscalPeriodStart;
  final String originalFiscalPeriodEnd;
  final String? originalSettlementPostingId;

  factory AdditionalTaxCandidate.fromPayload(Map<String, dynamic> payload) {
    final value = AdditionalTaxCandidate(
      taxType: taxTypeValue(payload, 'tax_type'),
      taxReturnId: taxUuid(payload, 'tax_return_id'),
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
      originalDeclaredTaxDue: taxPositiveMoney(
        payload,
        'original_declared_tax_due',
      ),
      revisedDeclaredTaxDue: taxPositiveMoney(
        payload,
        'revised_declared_tax_due',
      ),
      originalItemTaxDue: taxPositiveMoney(payload, 'original_item_tax_due'),
      replacementItemTaxDue: taxPositiveMoney(
        payload,
        'replacement_item_tax_due',
      ),
      additionalTaxDue: taxPositiveMoney(payload, 'additional_tax_due'),
      paymentBasis: taxEnum(payload, 'payment_basis', paymentBasisValues),
      paymentRequiredAmount: taxPositiveMoney(
        payload,
        'payment_required_amount',
      ),
      filingDate: taxDate(payload, 'filing_date'),
      recognitionDate: taxDate(payload, 'recognition_date'),
      originalEvidenceDigest: taxDigest(payload, 'original_evidence_digest'),
      replacementEvidenceDigest: taxDigest(
        payload,
        'replacement_evidence_digest',
      ),
      originalFiscalPeriodId: taxUuid(payload, 'original_fiscal_period_id'),
      originalFiscalPeriodStart: taxDate(
        payload,
        'original_fiscal_period_start',
      ),
      originalFiscalPeriodEnd: taxDate(payload, 'original_fiscal_period_end'),
      originalSettlementPostingId: taxOptionalUuid(
        payload,
        'original_settlement_posting_id',
      ),
    );
    value._validate();
    return value;
  }

  void _validate() {
    final additional =
        taxCents(replacementItemTaxDue) - taxCents(originalItemTaxDue);
    if (replacementEvidenceVersion <= originalEvidenceVersion ||
        additional <= 0 ||
        taxCents(additionalTaxDue) != additional ||
        taxCents(revisedDeclaredTaxDue) !=
            taxCents(originalDeclaredTaxDue) + additional ||
        taxCents(paymentRequiredAmount) !=
            (paymentBasis == 'full_revised_return_unpaid'
                ? taxCents(revisedDeclaredTaxDue)
                : additional) ||
        DateTime.parse(
          recognitionDate,
        ).isBefore(DateTime.parse(originalFiscalPeriodStart)) ||
        DateTime.parse(
          recognitionDate,
        ).isAfter(DateTime.parse(originalFiscalPeriodEnd)) ||
        (paymentBasis == 'additional_due_after_settlement' &&
            originalSettlementPostingId == null) ||
        (paymentBasis == 'full_revised_return_unpaid' &&
            originalSettlementPostingId != null)) {
      throw invalidTaxPayload('additional-tax candidate derivation');
    }
  }
}

class AdditionalTaxItem {
  AdditionalTaxItem._({
    required this.candidate,
    required this.amendmentEvidenceId,
    required this.amendmentBasis,
    required this.amendmentDate,
    required this.amendmentReference,
    required this.evidenceReference,
    required this.evidenceDigest,
    required this.liabilityPreparationId,
    required this.liabilityJournalEntryId,
    required this.liabilityJournalStatus,
    required this.liabilityFiscalPeriodId,
    required this.expenseAccountCode,
    required this.taxPayableAccountCode,
    required this.additionalLiabilityPostingId,
    required this.liabilityConfirmationDigest,
    required this.additionalPaymentEvidenceId,
    required this.paymentDate,
    required this.paymentAmount,
    required this.cashAccountSystemKey,
    required this.paymentCashAccountCode,
    required this.paymentEvidenceDigest,
    required this.settlementPreparationId,
    required this.settlementJournalEntryId,
    required this.settlementJournalStatus,
    required this.settlementFiscalPeriodId,
    required this.additionalSettlementPostingId,
    required this.amendmentStatus,
    required this.amendmentBlocker,
  });
  final AdditionalTaxCandidate candidate;
  final String amendmentEvidenceId;
  final String amendmentBasis;
  final String amendmentDate;
  final String amendmentReference;
  final String evidenceReference;
  final String evidenceDigest;
  final String? liabilityPreparationId;
  final String? liabilityJournalEntryId;
  final String? liabilityJournalStatus;
  final String? liabilityFiscalPeriodId;
  final String? expenseAccountCode;
  final String? taxPayableAccountCode;
  final String? additionalLiabilityPostingId;
  final String? liabilityConfirmationDigest;
  final String? additionalPaymentEvidenceId;
  final String? paymentDate;
  final String? paymentAmount;
  final String? cashAccountSystemKey;
  final String? paymentCashAccountCode;
  final String? paymentEvidenceDigest;
  final String? settlementPreparationId;
  final String? settlementJournalEntryId;
  final String? settlementJournalStatus;
  final String? settlementFiscalPeriodId;
  final String? additionalSettlementPostingId;
  final String amendmentStatus;
  final String? amendmentBlocker;

  String get taxType => candidate.taxType;
  String get taxReturnId => candidate.taxReturnId;
  String get taxLiabilityPostingId => candidate.taxLiabilityPostingId;
  String get originalEvidenceId => candidate.originalEvidenceId;
  String get replacementEvidenceId => candidate.replacementEvidenceId;
  String get sourceId => candidate.sourceId;
  String get loanId => candidate.loanId;
  String get clientId => candidate.clientId;
  String get originalDeclaredTaxDue => candidate.originalDeclaredTaxDue;
  String get revisedDeclaredTaxDue => candidate.revisedDeclaredTaxDue;
  String get originalItemTaxDue => candidate.originalItemTaxDue;
  String get replacementItemTaxDue => candidate.replacementItemTaxDue;
  String get additionalTaxDue => candidate.additionalTaxDue;
  String get paymentBasis => candidate.paymentBasis;
  String get paymentRequiredAmount => candidate.paymentRequiredAmount;
  String get recognitionDate => candidate.recognitionDate;

  bool get isEvidenceReady => amendmentStatus == 'amendment_evidence_ready';
  bool get isLiabilityPrepared =>
      amendmentStatus == 'additional_liability_prepared';
  bool get isAwaitingPayment =>
      amendmentStatus == 'additional_liability_posted_awaiting_payment';
  bool get isPaymentReady =>
      amendmentStatus == 'additional_payment_evidence_ready';
  bool get isSettlementPrepared =>
      amendmentStatus == 'additional_settlement_prepared';
  bool get isSettled => amendmentStatus == 'additional_tax_settled';

  factory AdditionalTaxItem.fromPayload(Map<String, dynamic> payload) {
    _requirePolicy(payload);
    final candidatePayload = Map<String, dynamic>.from(payload)
      ..putIfAbsent('original_evidence_version', () => 1)
      ..putIfAbsent('replacement_evidence_version', () => 2)
      ..putIfAbsent('filing_date', () => payload['amendment_date'])
      ..putIfAbsent(
        'original_evidence_digest',
        () => payload['evidence_digest'],
      )
      ..putIfAbsent(
        'replacement_evidence_digest',
        () => payload['evidence_digest'],
      )
      ..putIfAbsent(
        'original_fiscal_period_id',
        () => payload['liability_fiscal_period_id'] ?? payload['tax_return_id'],
      )
      ..putIfAbsent(
        'original_fiscal_period_start',
        () => payload['recognition_date'],
      )
      ..putIfAbsent(
        'original_fiscal_period_end',
        () => payload['recognition_date'],
      );
    final value = AdditionalTaxItem._(
      candidate: AdditionalTaxCandidate.fromPayload(candidatePayload),
      amendmentEvidenceId: taxUuid(payload, 'amendment_evidence_id'),
      amendmentBasis: taxEnum(payload, 'amendment_basis', amendmentBasisValues),
      amendmentDate: taxDate(payload, 'amendment_date'),
      amendmentReference: taxText(payload, 'amendment_reference'),
      evidenceReference: taxText(payload, 'evidence_reference'),
      evidenceDigest: taxDigest(payload, 'evidence_digest'),
      liabilityPreparationId: taxOptionalUuid(
        payload,
        'liability_preparation_id',
      ),
      liabilityJournalEntryId: taxOptionalUuid(
        payload,
        'liability_journal_entry_id',
      ),
      liabilityJournalStatus: _journalStatus(
        payload,
        'liability_journal_status',
      ),
      liabilityFiscalPeriodId: taxOptionalUuid(
        payload,
        'liability_fiscal_period_id',
      ),
      expenseAccountCode: taxOptionalText(payload, 'expense_account_code'),
      taxPayableAccountCode: taxOptionalText(
        payload,
        'tax_payable_account_code',
      ),
      additionalLiabilityPostingId: taxOptionalUuid(
        payload,
        'additional_liability_posting_id',
      ),
      liabilityConfirmationDigest: taxOptionalDigest(
        payload,
        'liability_confirmation_digest',
      ),
      additionalPaymentEvidenceId: taxOptionalUuid(
        payload,
        'additional_payment_evidence_id',
      ),
      paymentDate: taxOptionalDate(payload, 'payment_date'),
      paymentAmount: taxOptionalMoney(payload, 'payment_amount'),
      cashAccountSystemKey: _cashKey(payload),
      paymentCashAccountCode: taxOptionalText(
        payload,
        'payment_cash_account_code',
      ),
      paymentEvidenceDigest: taxOptionalDigest(
        payload,
        'payment_evidence_digest',
      ),
      settlementPreparationId: taxOptionalUuid(
        payload,
        'settlement_preparation_id',
      ),
      settlementJournalEntryId: taxOptionalUuid(
        payload,
        'settlement_journal_entry_id',
      ),
      settlementJournalStatus: _journalStatus(
        payload,
        'settlement_journal_status',
      ),
      settlementFiscalPeriodId: taxOptionalUuid(
        payload,
        'settlement_fiscal_period_id',
      ),
      additionalSettlementPostingId: taxOptionalUuid(
        payload,
        'additional_settlement_posting_id',
      ),
      amendmentStatus: taxEnum(
        payload,
        'amendment_status',
        additionalTaxStatuses,
      ),
      amendmentBlocker: taxOptionalText(payload, 'amendment_blocker'),
    );
    value._validateState();
    return value;
  }

  void requirePrepareLiability() {
    if (!isEvidenceReady || liabilityPreparationId != null) {
      throw ArgumentError('Exact amendment evidence-ready item is required.');
    }
  }

  void requirePostLiability() {
    if (!isLiabilityPrepared ||
        liabilityPreparationId == null ||
        liabilityJournalEntryId == null ||
        liabilityJournalStatus != 'draft' ||
        liabilityFiscalPeriodId == null ||
        expenseAccountCode == null ||
        taxPayableAccountCode == null) {
      throw ArgumentError(
        'Exact prepared additional-liability coordinates are required.',
      );
    }
  }

  void requirePayment() {
    if (!isAwaitingPayment ||
        additionalLiabilityPostingId == null ||
        liabilityConfirmationDigest == null ||
        additionalPaymentEvidenceId != null) {
      throw ArgumentError(
        'Exact posted additional liability awaiting payment is required.',
      );
    }
  }

  void requirePrepareSettlement() {
    if (!isPaymentReady || !_hasPayment || settlementPreparationId != null) {
      throw ArgumentError('Exact additional payment-ready item is required.');
    }
  }

  void requirePostSettlement() {
    if (!isSettlementPrepared ||
        !_hasPayment ||
        settlementPreparationId == null ||
        settlementJournalEntryId == null ||
        settlementJournalStatus != 'draft' ||
        settlementFiscalPeriodId == null ||
        taxPayableAccountCode == null) {
      throw ArgumentError(
        'Exact prepared additional-settlement coordinates are required.',
      );
    }
  }

  bool get _hasPayment =>
      additionalPaymentEvidenceId != null &&
      paymentDate != null &&
      paymentAmount == paymentRequiredAmount &&
      cashAccountSystemKey != null &&
      paymentCashAccountCode != null &&
      paymentEvidenceDigest != null;

  void _validateState() {
    try {
      if (isEvidenceReady) requirePrepareLiability();
      if (isLiabilityPrepared) requirePostLiability();
      if (isAwaitingPayment) requirePayment();
      if (isPaymentReady) requirePrepareSettlement();
      if (isSettlementPrepared) requirePostSettlement();
    } on ArgumentError {
      throw invalidTaxPayload('additional-tax lifecycle state');
    }
    if (isSettled &&
        (!_hasPayment ||
            additionalLiabilityPostingId == null ||
            liabilityConfirmationDigest == null ||
            settlementPreparationId == null ||
            settlementJournalEntryId == null ||
            settlementJournalStatus != 'posted' ||
            settlementFiscalPeriodId == null ||
            additionalSettlementPostingId == null)) {
      throw invalidTaxPayload('settled additional-tax state');
    }
  }
}

const amendmentBasisValues = <String>{
  'amended_return',
  'additional_assessment',
};
const paymentBasisValues = <String>{
  'full_revised_return_unpaid',
  'additional_due_after_settlement',
};
const additionalTaxFilters = <String>{
  'all',
  'ready',
  'liability_prepared',
  'awaiting_payment',
  'payment_ready',
  'settlement_prepared',
  'settled',
  'review',
  'blocked',
};
const additionalTaxStatuses = <String>{
  'amendment_evidence_ready',
  'additional_liability_prepared',
  'additional_liability_posted_awaiting_payment',
  'additional_payment_evidence_ready',
  'additional_settlement_prepared',
  'additional_tax_settled',
  'additional_liability_posted_review_required',
  'additional_tax_settled_review_required',
  'blocked_untracked_additional_liability_journal_state',
  'blocked_original_liability_not_stale',
  'blocked_replacement_evidence_changed',
  'blocked_original_period_not_open',
  'blocked_untracked_additional_settlement_journal_state',
  'blocked_additional_liability_not_current',
  'blocked_no_open_payment_period',
};

void _requirePolicy(Map<String, dynamic> payload) {
  if (!taxBool(payload, 'tax_additional_amendment_enabled') ||
      !taxBool(payload, 'tax_additional_settlement_enabled') ||
      taxBool(payload, 'tax_refund_credit_realization_enabled') ||
      taxBool(payload, 'automatic_source_posting')) {
    throw invalidTaxPayload('additional-tax policy');
  }
}

String? _journalStatus(Map<String, dynamic> payload, String key) {
  if (payload[key] == null) return null;
  return taxEnum(payload, key, const <String>{'draft', 'posted'});
}

String? _cashKey(Map<String, dynamic> payload) {
  if (payload['cash_account_system_key'] == null) return null;
  return taxEnum(payload, 'cash_account_system_key', const <String>{
    'cash_office',
    'cash_bank_gcash',
  });
}
