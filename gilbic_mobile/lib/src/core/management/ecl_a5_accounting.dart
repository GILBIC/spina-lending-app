import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class EclA5Overview {
  const EclA5Overview({
    required this.summary,
    required this.items,
    required this.permissions,
    required this.notice,
    required this.filter,
    required this.limit,
    required this.offset,
  });

  final EclA5Summary summary;
  final List<EclA5ActionItem> items;
  final EclA5Permissions permissions;
  final String notice;
  final String filter;
  final int limit;
  final int offset;

  factory EclA5Overview.fromPayload(Map<String, dynamic> payload) {
    final rawItems = payload['items'];
    if (rawItems is! List) throw _invalid('queue items');
    return EclA5Overview(
      summary: EclA5Summary.fromPayload(stringMap(payload['summary'])),
      items: rawItems
          .map((item) => EclA5ActionItem.fromPayload(stringMap(item)))
          .toList(growable: false),
      permissions: EclA5Permissions.fromPayload(
        stringMap(payload['permissions']),
      ),
      notice: _text(payload, 'notice'),
      filter: _enumText(payload, 'filter', eclA5Filters),
      limit: _nonNegativeInt(payload, 'limit'),
      offset: _nonNegativeInt(payload, 'offset'),
    );
  }
}

class EclA5Summary {
  const EclA5Summary({
    required this.loanCount,
    required this.remeasurementRequiredCount,
    required this.allowanceCurrentCount,
    required this.writeoffReadyCount,
    required this.writtenOffCount,
    required this.recoveryReviewRequiredCount,
    required this.recoveryReadyCount,
    required this.blockedCount,
    required this.remeasurementPostingCount,
    required this.writeoffPostingCount,
    required this.postWriteoffRecoveryCount,
    required this.protectedA5AccountingEnabled,
    required this.automaticSourcePosting,
  });

  final int loanCount;
  final int remeasurementRequiredCount;
  final int allowanceCurrentCount;
  final int writeoffReadyCount;
  final int writtenOffCount;
  final int recoveryReviewRequiredCount;
  final int recoveryReadyCount;
  final int blockedCount;
  final int remeasurementPostingCount;
  final int writeoffPostingCount;
  final int postWriteoffRecoveryCount;
  final bool protectedA5AccountingEnabled;
  final bool automaticSourcePosting;

  factory EclA5Summary.fromPayload(
    Map<String, dynamic> payload,
  ) => EclA5Summary(
    loanCount: _nonNegativeInt(payload, 'loan_count'),
    remeasurementRequiredCount: _nonNegativeInt(
      payload,
      'remeasurement_required_count',
    ),
    allowanceCurrentCount: _nonNegativeInt(payload, 'allowance_current_count'),
    writeoffReadyCount: _nonNegativeInt(payload, 'writeoff_ready_count'),
    writtenOffCount: _nonNegativeInt(payload, 'written_off_count'),
    recoveryReviewRequiredCount: _nonNegativeInt(
      payload,
      'recovery_review_required_count',
    ),
    recoveryReadyCount: _nonNegativeInt(payload, 'recovery_ready_count'),
    blockedCount: _nonNegativeInt(payload, 'blocked_count'),
    remeasurementPostingCount: _nonNegativeInt(
      payload,
      'remeasurement_posting_count',
    ),
    writeoffPostingCount: _nonNegativeInt(payload, 'writeoff_posting_count'),
    postWriteoffRecoveryCount: _nonNegativeInt(
      payload,
      'post_writeoff_recovery_count',
    ),
    protectedA5AccountingEnabled: _bool(
      payload,
      'protected_a5_accounting_enabled',
    ),
    automaticSourcePosting: _bool(payload, 'automatic_source_posting'),
  );
}

class EclA5Permissions {
  const EclA5Permissions({
    required this.remeasurementPost,
    required this.writeoffPost,
    required this.recoveryReview,
    required this.recoveryPost,
  });

  final bool remeasurementPost;
  final bool writeoffPost;
  final bool recoveryReview;
  final bool recoveryPost;

  factory EclA5Permissions.fromPayload(Map<String, dynamic> payload) =>
      EclA5Permissions(
        remeasurementPost: _bool(payload, 'remeasurement_post'),
        writeoffPost: _bool(payload, 'writeoff_post'),
        recoveryReview: _bool(payload, 'recovery_review'),
        recoveryPost: _bool(payload, 'recovery_post'),
      );
}

class EclA5ActionItem {
  const EclA5ActionItem({
    required this.loanId,
    required this.loanNumber,
    required this.loanStatus,
    required this.calculationMode,
    required this.creditRiskReviewId,
    required this.stageLabel,
    required this.defaultLabel,
    required this.writeOffLabel,
    required this.recoveryLabel,
    required this.measurementId,
    required this.measurementVersion,
    required this.measurementDate,
    required this.calculationDigest,
    required this.measurementStatus,
    required this.authoritativeEclAmount,
    required this.currentAllowanceBalance,
    required this.loanReceivableAccountId,
    required this.loanReceivableSystemKey,
    required this.accruedInterestAccountId,
    required this.loanComponent,
    required this.accruedInterestComponent,
    required this.grossCarryingAmount,
    required this.writeoffId,
    required this.recoveryTransactionId,
    required this.recoveryAmount,
    required this.recoveryCandidateTransactionId,
    required this.recoveryCandidateAmount,
    required this.recoveryCandidateCollectionDate,
    required this.postingDate,
    required this.fiscalPeriodId,
    required this.creditLossExpenseAccountId,
    required this.allowanceAccountId,
    required this.cashAccountId,
    required this.a5Status,
    required this.protectedA5AccountingEnabled,
    required this.automaticSourcePosting,
  });

  final String loanId;
  final String loanNumber;
  final String loanStatus;
  final String calculationMode;
  final int? creditRiskReviewId;
  final String? stageLabel;
  final bool? defaultLabel;
  final String? writeOffLabel;
  final String? recoveryLabel;
  final String? measurementId;
  final int? measurementVersion;
  final DateTime? measurementDate;
  final String? calculationDigest;
  final String? measurementStatus;
  final String? authoritativeEclAmount;
  final String currentAllowanceBalance;
  final String? loanReceivableAccountId;
  final String? loanReceivableSystemKey;
  final String? accruedInterestAccountId;
  final String? loanComponent;
  final String? accruedInterestComponent;
  final String? grossCarryingAmount;
  final String? writeoffId;
  final String? recoveryTransactionId;
  final String? recoveryAmount;
  final String? recoveryCandidateTransactionId;
  final String? recoveryCandidateAmount;
  final DateTime? recoveryCandidateCollectionDate;
  final DateTime? postingDate;
  final String? fiscalPeriodId;
  final String? creditLossExpenseAccountId;
  final String? allowanceAccountId;
  final String? cashAccountId;
  final String a5Status;
  final bool protectedA5AccountingEnabled;
  final bool automaticSourcePosting;

  bool get isRemeasurementRequired => a5Status == 'remeasurement_required';
  bool get isWriteoffReady => a5Status == 'writeoff_ready';
  bool get isRecoveryReviewRequired => a5Status == 'recovery_review_required';
  bool get isRecoveryReady => a5Status == 'post_writeoff_recovery_ready';

  factory EclA5ActionItem.fromPayload(Map<String, dynamic> payload) {
    final item = EclA5ActionItem(
      loanId: _uuid(payload, 'loan_id'),
      loanNumber: _text(payload, 'loan_number'),
      loanStatus: _text(payload, 'loan_status'),
      calculationMode: _text(payload, 'calculation_mode'),
      creditRiskReviewId: _optionalPositiveInt(
        payload,
        'credit_risk_review_id',
      ),
      stageLabel: _optionalText(payload, 'stage_label'),
      defaultLabel: _optionalBool(payload, 'default_label'),
      writeOffLabel: _optionalText(payload, 'write_off_label'),
      recoveryLabel: _optionalText(payload, 'recovery_label'),
      measurementId: _optionalUuid(payload, 'measurement_id'),
      measurementVersion: _optionalPositiveInt(payload, 'measurement_version'),
      measurementDate: _optionalDate(payload, 'measurement_date'),
      calculationDigest: _optionalDigest(payload, 'calculation_digest'),
      measurementStatus: _optionalText(payload, 'measurement_status'),
      authoritativeEclAmount: _optionalMoney(
        payload,
        'authoritative_ecl_amount',
      ),
      currentAllowanceBalance: _money(payload, 'current_allowance_balance'),
      loanReceivableAccountId: _optionalUuid(
        payload,
        'loan_receivable_account_id',
      ),
      loanReceivableSystemKey: _optionalText(
        payload,
        'loan_receivable_system_key',
      ),
      accruedInterestAccountId: _optionalUuid(
        payload,
        'accrued_interest_account_id',
      ),
      loanComponent: _optionalMoney(payload, 'loan_component'),
      accruedInterestComponent: _optionalMoney(
        payload,
        'accrued_interest_component',
      ),
      grossCarryingAmount: _optionalMoney(payload, 'gross_carrying_amount'),
      writeoffId: _optionalUuid(payload, 'writeoff_id'),
      recoveryTransactionId: _optionalUuid(payload, 'recovery_transaction_id'),
      recoveryAmount: _optionalMoney(payload, 'recovery_amount'),
      recoveryCandidateTransactionId: _optionalUuid(
        payload,
        'recovery_candidate_transaction_id',
      ),
      recoveryCandidateAmount: _optionalMoney(
        payload,
        'recovery_candidate_amount',
      ),
      recoveryCandidateCollectionDate: _optionalDate(
        payload,
        'recovery_candidate_collection_date',
      ),
      postingDate: _optionalDate(payload, 'posting_date'),
      fiscalPeriodId: _optionalUuid(payload, 'fiscal_period_id'),
      creditLossExpenseAccountId: _optionalUuid(
        payload,
        'credit_loss_expense_account_id',
      ),
      allowanceAccountId: _optionalUuid(payload, 'allowance_account_id'),
      cashAccountId: _optionalUuid(payload, 'cash_account_id'),
      a5Status: _enumText(payload, 'a5_status', _eclA5ItemStatuses),
      protectedA5AccountingEnabled: _bool(
        payload,
        'protected_a5_accounting_enabled',
      ),
      automaticSourcePosting: _bool(payload, 'automatic_source_posting'),
    );
    try {
      if (item.isRemeasurementRequired) item.requireRemeasurementCoordinates();
      if (item.isWriteoffReady) item.requireWriteoffCoordinates();
      if (item.isRecoveryReviewRequired) {
        item.requireRecoveryReviewCoordinates();
      }
      if (item.isRecoveryReady) item.requireRecoveryPostingCoordinates();
    } on ArgumentError {
      throw _invalid('protected action coordinates');
    }
    return item;
  }

  void _requireProtected() {
    if (!protectedA5AccountingEnabled || automaticSourcePosting) {
      throw ArgumentError('The protected manual A5 boundary is required.');
    }
  }

  void requireRemeasurementCoordinates() {
    _requireProtected();
    if (!isRemeasurementRequired ||
        measurementId == null ||
        measurementVersion == null ||
        measurementDate == null ||
        calculationDigest == null ||
        authoritativeEclAmount == null ||
        postingDate == null ||
        postingDate != measurementDate ||
        fiscalPeriodId == null ||
        creditLossExpenseAccountId == null ||
        allowanceAccountId == null ||
        _cents(currentAllowanceBalance) <= 0 ||
        authoritativeEclAmount == currentAllowanceBalance) {
      throw ArgumentError('A complete current A5 remeasurement is required.');
    }
  }

  void requireWriteoffCoordinates() {
    _requireProtected();
    final loan = _optionalCents(loanComponent);
    final accrued = _optionalCents(accruedInterestComponent);
    final gross = _optionalCents(grossCarryingAmount);
    if (!isWriteoffReady ||
        creditRiskReviewId == null ||
        measurementId == null ||
        calculationDigest == null ||
        authoritativeEclAmount == null ||
        loanReceivableAccountId == null ||
        accruedInterestAccountId == null ||
        allowanceAccountId == null ||
        postingDate == null ||
        fiscalPeriodId == null ||
        loan == null ||
        accrued == null ||
        gross == null ||
        gross <= 0 ||
        loan + accrued != gross ||
        _cents(authoritativeEclAmount!) != gross ||
        _cents(currentAllowanceBalance) != gross) {
      throw ArgumentError('A complete fully covered A5 write-off is required.');
    }
  }

  void requireRecoveryReviewCoordinates() {
    _requireProtected();
    if (!isRecoveryReviewRequired ||
        writeoffId == null ||
        recoveryCandidateTransactionId == null ||
        recoveryCandidateAmount == null ||
        _cents(recoveryCandidateAmount!) <= 0 ||
        recoveryCandidateCollectionDate == null) {
      throw ArgumentError(
        'Exact protected recovery cash evidence is required.',
      );
    }
  }

  void requireRecoveryPostingCoordinates() {
    _requireProtected();
    if (!isRecoveryReady ||
        writeoffId == null ||
        creditRiskReviewId == null ||
        recoveryTransactionId == null ||
        recoveryAmount == null ||
        _cents(recoveryAmount!) <= 0 ||
        postingDate == null ||
        fiscalPeriodId == null ||
        cashAccountId == null ||
        creditLossExpenseAccountId == null) {
      throw ArgumentError('A complete reviewed A5 cash recovery is required.');
    }
  }
}

class EclA5ActionReceipt {
  const EclA5ActionReceipt({
    required this.id,
    required this.automaticSourcePosting,
  });

  final String id;
  final bool automaticSourcePosting;

  factory EclA5ActionReceipt.fromPayload(
    Map<String, dynamic> payload,
    String idKey, {
    bool integerId = false,
  }) {
    final rawId = payload[idKey];
    final id = integerId
        ? (rawId is int && rawId > 0 ? '$rawId' : null)
        : (rawId is String && _uuidPattern.hasMatch(rawId)
              ? rawId.toLowerCase()
              : null);
    final automatic = _bool(payload, 'automatic_source_posting');
    if (id == null || automatic) throw _invalid('action receipt');
    return EclA5ActionReceipt(id: id, automaticSourcePosting: automatic);
  }
}

const eclA5Filters = <String>{
  'all',
  'remeasurement_required',
  'allowance_current',
  'writeoff_ready',
  'written_off',
  'recovery_review_required',
  'post_writeoff_recovery_ready',
  'blocked',
};

const _eclA5ItemStatuses = <String>{
  'remeasurement_required',
  'allowance_current',
  'writeoff_ready',
  'written_off',
  'recovery_review_required',
  'post_writeoff_recovery_ready',
  'blocked',
};

final _uuidPattern = RegExp(
  r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$',
);
final _moneyPattern = RegExp(r'^(0|[1-9][0-9]*)\.[0-9]{2}$');
final _digestPattern = RegExp(r'^[0-9a-fA-F]{64}$');
final _datePattern = RegExp(r'^\d{4}-\d{2}-\d{2}$');

SpinaApiException _invalid(String field) => SpinaApiException(
  'The SPINA server returned incomplete A5 ECL accounting $field.',
  code: 'invalid_ecl_a5_payload',
);

String _text(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value is! String || value.trim().isEmpty) throw _invalid(key);
  return value.trim();
}

String? _optionalText(Map<String, dynamic> payload, String key) =>
    payload[key] == null ? null : _text(payload, key);

String _uuid(Map<String, dynamic> payload, String key) {
  final value = _text(payload, key);
  if (!_uuidPattern.hasMatch(value)) throw _invalid(key);
  return value.toLowerCase();
}

String? _optionalUuid(Map<String, dynamic> payload, String key) =>
    payload[key] == null ? null : _uuid(payload, key);

String _money(Map<String, dynamic> payload, String key) {
  final value = _text(payload, key);
  if (!_moneyPattern.hasMatch(value)) throw _invalid(key);
  return value;
}

String? _optionalMoney(Map<String, dynamic> payload, String key) =>
    payload[key] == null ? null : _money(payload, key);

String? _optionalDigest(Map<String, dynamic> payload, String key) {
  if (payload[key] == null) return null;
  final value = _text(payload, key).toLowerCase();
  if (!_digestPattern.hasMatch(value)) throw _invalid(key);
  return value;
}

int _nonNegativeInt(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value is! int || value < 0) throw _invalid(key);
  return value;
}

int? _optionalPositiveInt(Map<String, dynamic> payload, String key) {
  if (payload[key] == null) return null;
  final value = payload[key];
  if (value is! int || value < 1) throw _invalid(key);
  return value;
}

bool _bool(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value is! bool) throw _invalid(key);
  return value;
}

bool? _optionalBool(Map<String, dynamic> payload, String key) {
  if (payload[key] == null) return null;
  return _bool(payload, key);
}

String _enumText(
  Map<String, dynamic> payload,
  String key,
  Set<String> allowed,
) {
  final value = _text(payload, key);
  if (!allowed.contains(value)) throw _invalid(key);
  return value;
}

DateTime? _optionalDate(Map<String, dynamic> payload, String key) {
  if (payload[key] == null) return null;
  final value = _text(payload, key);
  final parsed = DateTime.tryParse(value);
  if (!_datePattern.hasMatch(value) ||
      parsed == null ||
      eclA5DateText(parsed) != value) {
    throw _invalid(key);
  }
  return DateTime(parsed.year, parsed.month, parsed.day);
}

int _cents(String value) {
  final parts = value.split('.');
  return int.parse(parts.first) * 100 + int.parse(parts.last);
}

int? _optionalCents(String? value) => value == null ? null : _cents(value);

String eclA5DateText(DateTime value) =>
    '${value.year.toString().padLeft(4, '0')}-'
    '${value.month.toString().padLeft(2, '0')}-'
    '${value.day.toString().padLeft(2, '0')}';
