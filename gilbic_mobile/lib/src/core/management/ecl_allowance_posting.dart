import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class EclAllowancePostingOverview {
  const EclAllowancePostingOverview({
    required this.summary,
    required this.items,
    required this.permissions,
    required this.notice,
    required this.filter,
    required this.limit,
    required this.offset,
  });

  final EclAllowancePostingSummary summary;
  final List<EclAllowancePostingItem> items;
  final EclAllowancePostingPermissions permissions;
  final String notice;
  final String filter;
  final int limit;
  final int offset;

  factory EclAllowancePostingOverview.fromPayload(
    Map<String, dynamic> payload,
  ) {
    final rawItems = payload['items'];
    if (rawItems is! List) throw _invalid('queue items');
    return EclAllowancePostingOverview(
      summary: EclAllowancePostingSummary.fromPayload(
        stringMap(payload['summary']),
      ),
      items: rawItems
          .map((item) => EclAllowancePostingItem.fromPayload(stringMap(item)))
          .toList(growable: false),
      permissions: EclAllowancePostingPermissions(
        prepare: _bool(payload, 'prepare_permission'),
        post: _bool(payload, 'post_permission'),
      ),
      notice: _text(payload, 'notice'),
      filter: _text(payload, 'filter'),
      limit: _nonNegativeInt(payload, 'limit'),
      offset: _nonNegativeInt(payload, 'offset'),
    );
  }
}

class EclAllowancePostingSummary {
  const EclAllowancePostingSummary({
    required this.loanCount,
    required this.measurementNotAuthoritativeCount,
    required this.noAllowanceRequiredCount,
    required this.preparationRequiredCount,
    required this.postingReadyCount,
    required this.postedCurrentCount,
    required this.a5RemeasurementRequiredCount,
    required this.postingAuditIncompleteCount,
    required this.protectedAllowanceBalanceTotal,
    required this.account1190PostingEnabled,
    required this.automaticSourcePosting,
  });

  final int loanCount;
  final int measurementNotAuthoritativeCount;
  final int noAllowanceRequiredCount;
  final int preparationRequiredCount;
  final int postingReadyCount;
  final int postedCurrentCount;
  final int a5RemeasurementRequiredCount;
  final int postingAuditIncompleteCount;
  final String protectedAllowanceBalanceTotal;
  final bool account1190PostingEnabled;
  final bool automaticSourcePosting;

  factory EclAllowancePostingSummary.fromPayload(Map<String, dynamic> payload) {
    return EclAllowancePostingSummary(
      loanCount: _nonNegativeInt(payload, 'loan_count'),
      measurementNotAuthoritativeCount: _nonNegativeInt(
        payload,
        'measurement_not_authoritative_count',
      ),
      noAllowanceRequiredCount: _nonNegativeInt(
        payload,
        'no_allowance_required_count',
      ),
      preparationRequiredCount: _nonNegativeInt(
        payload,
        'preparation_required_count',
      ),
      postingReadyCount: _nonNegativeInt(payload, 'posting_ready_count'),
      postedCurrentCount: _nonNegativeInt(payload, 'posted_current_count'),
      a5RemeasurementRequiredCount: _nonNegativeInt(
        payload,
        'a5_remeasurement_required_count',
      ),
      postingAuditIncompleteCount: _nonNegativeInt(
        payload,
        'posting_audit_incomplete_count',
      ),
      protectedAllowanceBalanceTotal: _money(
        payload,
        'protected_allowance_balance_total',
      ),
      account1190PostingEnabled: _bool(payload, 'account_1190_posting_enabled'),
      automaticSourcePosting: _bool(payload, 'automatic_source_posting'),
    );
  }
}

class EclAllowancePostingPermissions {
  const EclAllowancePostingPermissions({
    required this.prepare,
    required this.post,
  });

  final bool prepare;
  final bool post;
}

class EclAllowancePostingItem {
  const EclAllowancePostingItem({
    required this.loanId,
    required this.loanNumber,
    required this.loanStatus,
    required this.loanTypeCode,
    required this.loanTypeName,
    required this.calculationMode,
    required this.measurementId,
    required this.measurementVersion,
    required this.measurementDate,
    required this.lossHorizon,
    required this.calculationDigest,
    required this.measurementStatus,
    required this.authoritativeEclAmount,
    required this.preparationId,
    required this.journalEntryId,
    required this.sourceEventKey,
    required this.postingDate,
    required this.fiscalPeriodId,
    required this.creditLossExpenseAccountId,
    required this.allowanceAccountId,
    required this.allowanceAmount,
    required this.priorAllowanceBalance,
    required this.preparationReviewToken,
    required this.preparationDigest,
    required this.draftPolicyVersion,
    required this.journalStatus,
    required this.entryNumber,
    required this.postingId,
    required this.postingReviewToken,
    required this.postingPolicyVersion,
    required this.currentAllowanceBalance,
    required this.allowancePostingStatus,
    required this.protectedAllowanceActionReady,
    required this.account1190PostingEnabled,
    required this.automaticSourcePosting,
  });

  final String loanId;
  final String loanNumber;
  final String loanStatus;
  final String loanTypeCode;
  final String loanTypeName;
  final String calculationMode;
  final String? measurementId;
  final int? measurementVersion;
  final DateTime? measurementDate;
  final String? lossHorizon;
  final String? calculationDigest;
  final String measurementStatus;
  final String? authoritativeEclAmount;
  final String? preparationId;
  final String? journalEntryId;
  final String? sourceEventKey;
  final DateTime? postingDate;
  final String? fiscalPeriodId;
  final String? creditLossExpenseAccountId;
  final String? allowanceAccountId;
  final String? allowanceAmount;
  final String? priorAllowanceBalance;
  final String? preparationReviewToken;
  final String? preparationDigest;
  final String? draftPolicyVersion;
  final String? journalStatus;
  final String? entryNumber;
  final String? postingId;
  final String? postingReviewToken;
  final String? postingPolicyVersion;
  final String currentAllowanceBalance;
  final String allowancePostingStatus;
  final bool protectedAllowanceActionReady;
  final bool account1190PostingEnabled;
  final bool automaticSourcePosting;

  bool get isPreparationRequired =>
      allowancePostingStatus == 'preparation_required';
  bool get isPostingReady => allowancePostingStatus == 'posting_ready';
  bool get isPostedCurrent => allowancePostingStatus == 'posted_current';

  factory EclAllowancePostingItem.fromPayload(Map<String, dynamic> payload) {
    final status = _enumText(
      payload,
      'allowance_posting_status',
      _allowanceStatuses,
    );
    final item = EclAllowancePostingItem(
      loanId: _uuid(payload, 'loan_id'),
      loanNumber: _text(payload, 'loan_number'),
      loanStatus: _text(payload, 'loan_status'),
      loanTypeCode: _text(payload, 'loan_type_code'),
      loanTypeName: _text(payload, 'loan_type_name'),
      calculationMode: _text(payload, 'calculation_mode'),
      measurementId: _optionalUuid(payload, 'measurement_id'),
      measurementVersion: _optionalNonNegativeInt(
        payload,
        'measurement_version',
      ),
      measurementDate: _optionalDate(payload, 'measurement_date'),
      lossHorizon: _optionalText(payload, 'loss_horizon'),
      calculationDigest: _optionalDigest(payload, 'calculation_digest'),
      measurementStatus: _text(payload, 'measurement_status'),
      authoritativeEclAmount: _optionalMoney(
        payload,
        'authoritative_ecl_amount',
      ),
      preparationId: _optionalUuid(payload, 'preparation_id'),
      journalEntryId: _optionalUuid(payload, 'journal_entry_id'),
      sourceEventKey: _optionalText(payload, 'source_event_key'),
      postingDate: _optionalDate(payload, 'posting_date'),
      fiscalPeriodId: _optionalUuid(payload, 'fiscal_period_id'),
      creditLossExpenseAccountId: _optionalUuid(
        payload,
        'credit_loss_expense_account_id',
      ),
      allowanceAccountId: _optionalUuid(payload, 'allowance_account_id'),
      allowanceAmount: _optionalMoney(payload, 'allowance_amount'),
      priorAllowanceBalance: _optionalMoney(payload, 'prior_allowance_balance'),
      preparationReviewToken: _optionalDigest(
        payload,
        'preparation_review_token',
      ),
      preparationDigest: _optionalDigest(payload, 'preparation_digest'),
      draftPolicyVersion: _optionalText(payload, 'draft_policy_version'),
      journalStatus: _optionalText(payload, 'journal_status'),
      entryNumber: _optionalText(payload, 'entry_number'),
      postingId: _optionalUuid(payload, 'posting_id'),
      postingReviewToken: _optionalDigest(payload, 'posting_review_token'),
      postingPolicyVersion: _optionalText(payload, 'posting_policy_version'),
      currentAllowanceBalance: _money(payload, 'current_allowance_balance'),
      allowancePostingStatus: status,
      protectedAllowanceActionReady: _bool(
        payload,
        'protected_allowance_action_ready',
      ),
      account1190PostingEnabled: _bool(payload, 'account_1190_posting_enabled'),
      automaticSourcePosting: _bool(payload, 'automatic_source_posting'),
    );
    try {
      if (item.isPreparationRequired) item.requirePreparationCoordinates();
      if (item.isPostingReady) item.requirePostingCoordinates();
    } on ArgumentError {
      throw _invalid('protected action coordinates');
    }
    if (item.isPostedCurrent &&
        (item.postingId == null ||
            item.entryNumber == null ||
            item.postingPolicyVersion == null)) {
      throw _invalid('protected posting evidence');
    }
    return item;
  }

  void requirePreparationCoordinates() {
    if (!isPreparationRequired ||
        !protectedAllowanceActionReady ||
        !account1190PostingEnabled ||
        automaticSourcePosting ||
        measurementId == null ||
        measurementVersion == null ||
        measurementDate == null ||
        calculationDigest == null ||
        authoritativeEclAmount == null ||
        authoritativeEclAmount == '0.00' ||
        postingDate == null ||
        fiscalPeriodId == null ||
        creditLossExpenseAccountId == null ||
        allowanceAccountId == null ||
        allowanceAmount != authoritativeEclAmount ||
        priorAllowanceBalance != '0.00') {
      throw ArgumentError(
        'A complete current initial ECL allowance snapshot is required.',
      );
    }
  }

  void requirePostingCoordinates() {
    if (!isPostingReady ||
        !protectedAllowanceActionReady ||
        !account1190PostingEnabled ||
        automaticSourcePosting ||
        measurementId == null ||
        calculationDigest == null ||
        preparationId == null ||
        journalEntryId == null ||
        sourceEventKey == null ||
        postingDate == null ||
        fiscalPeriodId == null ||
        creditLossExpenseAccountId == null ||
        allowanceAccountId == null ||
        allowanceAmount == null ||
        priorAllowanceBalance != '0.00' ||
        preparationDigest == null ||
        journalStatus != 'draft') {
      throw ArgumentError(
        'A complete current protected ECL allowance preparation is required.',
      );
    }
  }
}

class EclAllowanceActionReceipt {
  const EclAllowanceActionReceipt({
    required this.id,
    required this.automaticSourcePosting,
  });

  final String id;
  final bool automaticSourcePosting;

  factory EclAllowanceActionReceipt.fromPayload(Map<String, dynamic> payload) {
    final receipt = EclAllowanceActionReceipt(
      id: _uuid(payload, 'id'),
      automaticSourcePosting: _bool(payload, 'automatic_source_posting'),
    );
    if (receipt.automaticSourcePosting) {
      throw _invalid('automatic posting policy');
    }
    return receipt;
  }
}

const _allowanceStatuses = <String>{
  'measurement_not_authoritative',
  'no_allowance_required',
  'preparation_required',
  'posting_ready',
  'posted_current',
  'a5_remeasurement_required',
  'posting_audit_incomplete',
  'preparation_blocked',
};

final _uuidPattern = RegExp(
  r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$',
);
final _moneyPattern = RegExp(r'^(0|[1-9][0-9]*)\.[0-9]{2}$');
final _digestPattern = RegExp(r'^[0-9a-fA-F]{64}$');
final _datePattern = RegExp(r'^\d{4}-\d{2}-\d{2}$');

SpinaApiException _invalid(String field) => SpinaApiException(
  'The SPINA server returned incomplete ECL allowance $field.',
  code: 'invalid_ecl_allowance_payload',
);

String _text(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value is! String || value.trim().isEmpty) throw _invalid(key);
  return value.trim();
}

String? _optionalText(Map<String, dynamic> payload, String key) {
  if (payload[key] == null) return null;
  return _text(payload, key);
}

String _uuid(Map<String, dynamic> payload, String key) {
  final value = _text(payload, key);
  if (!_uuidPattern.hasMatch(value)) throw _invalid(key);
  return value.toLowerCase();
}

String? _optionalUuid(Map<String, dynamic> payload, String key) {
  if (payload[key] == null) return null;
  return _uuid(payload, key);
}

String _money(Map<String, dynamic> payload, String key) {
  final value = _text(payload, key);
  if (!_moneyPattern.hasMatch(value)) throw _invalid(key);
  return value;
}

String? _optionalMoney(Map<String, dynamic> payload, String key) {
  if (payload[key] == null) return null;
  return _money(payload, key);
}

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

int? _optionalNonNegativeInt(Map<String, dynamic> payload, String key) {
  if (payload[key] == null) return null;
  return _nonNegativeInt(payload, key);
}

bool _bool(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value is! bool) throw _invalid(key);
  return value;
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
      eclAllowanceDateText(parsed) != value) {
    throw _invalid(key);
  }
  return DateTime(parsed.year, parsed.month, parsed.day);
}

String eclAllowanceDateText(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}
