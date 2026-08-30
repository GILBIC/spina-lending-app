import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class PeriodCloseOverview {
  const PeriodCloseOverview({
    required this.summary,
    required this.items,
    required this.permissions,
    required this.notice,
  });

  final PeriodCloseSummary summary;
  final List<PeriodCloseItem> items;
  final PeriodClosePermissions permissions;
  final String notice;

  factory PeriodCloseOverview.fromPayload(Map<String, dynamic> payload) {
    final rawItems = payload['items'];
    if (rawItems is! List) {
      throw const SpinaApiException(
        'The SPINA server returned an incomplete period-close queue.',
        code: 'invalid_period_close_payload',
      );
    }
    return PeriodCloseOverview(
      summary: PeriodCloseSummary.fromPayload(stringMap(payload['summary'])),
      items: rawItems
          .map((item) => PeriodCloseItem.fromPayload(stringMap(item)))
          .toList(growable: false),
      permissions: PeriodClosePermissions.fromPayload(
        stringMap(payload['permissions']),
      ),
      notice: _requiredString(payload, 'notice'),
    );
  }
}

class PeriodCloseSummary {
  const PeriodCloseSummary({
    required this.periodCount,
    required this.readyForReviewCount,
    required this.readyToPrepareCount,
    required this.preparedCount,
    required this.protectedClosedCount,
    required this.blockedCount,
    required this.closedNetIncomeTotal,
    required this.protectedPeriodCloseEnabled,
    required this.retainedEarningsCloseEnabled,
    required this.closedPeriodPostingProtectionEnabled,
    required this.periodReopenEnabled,
    required this.automaticSourcePosting,
  });

  final int periodCount;
  final int readyForReviewCount;
  final int readyToPrepareCount;
  final int preparedCount;
  final int protectedClosedCount;
  final int blockedCount;
  final String closedNetIncomeTotal;
  final bool protectedPeriodCloseEnabled;
  final bool retainedEarningsCloseEnabled;
  final bool closedPeriodPostingProtectionEnabled;
  final bool periodReopenEnabled;
  final bool automaticSourcePosting;

  factory PeriodCloseSummary.fromPayload(Map<String, dynamic> payload) {
    return PeriodCloseSummary(
      periodCount: _requiredNonNegativeInt(payload, 'period_count'),
      readyForReviewCount: _requiredNonNegativeInt(
        payload,
        'ready_for_review_count',
      ),
      readyToPrepareCount: _requiredNonNegativeInt(
        payload,
        'ready_to_prepare_count',
      ),
      preparedCount: _requiredNonNegativeInt(payload, 'prepared_count'),
      protectedClosedCount: _requiredNonNegativeInt(
        payload,
        'protected_closed_count',
      ),
      blockedCount: _requiredNonNegativeInt(payload, 'blocked_count'),
      closedNetIncomeTotal: _requiredMoney(payload, 'closed_net_income_total'),
      protectedPeriodCloseEnabled: _requiredBool(
        payload,
        'protected_period_close_enabled',
      ),
      retainedEarningsCloseEnabled: _requiredBool(
        payload,
        'retained_earnings_close_enabled',
      ),
      closedPeriodPostingProtectionEnabled: _requiredBool(
        payload,
        'closed_period_posting_protection_enabled',
      ),
      periodReopenEnabled: _requiredBool(payload, 'period_reopen_enabled'),
      automaticSourcePosting: _requiredBool(
        payload,
        'automatic_source_posting',
      ),
    );
  }
}

class PeriodClosePermissions {
  const PeriodClosePermissions({
    required this.closePrepare,
    required this.closePost,
  });

  final bool closePrepare;
  final bool closePost;

  factory PeriodClosePermissions.fromPayload(Map<String, dynamic> payload) {
    return PeriodClosePermissions(
      closePrepare: _requiredBool(payload, 'close_prepare'),
      closePost: _requiredBool(payload, 'close_post'),
    );
  }
}

class PeriodCloseItem {
  const PeriodCloseItem({
    required this.fiscalPeriodId,
    required this.label,
    required this.startDate,
    required this.endDate,
    required this.fiscalPeriodStatus,
    required this.closedByUserId,
    required this.closedAt,
    required this.preparationId,
    required this.journalEntryId,
    required this.temporaryAccountCount,
    required this.netIncome,
    required this.retainedEarningsBalanceBefore,
    required this.closeDigest,
    required this.closePostingId,
    required this.closingEntryNumber,
    required this.retainedEarningsBalanceAfter,
    required this.closeStatus,
    required this.closeBlocker,
    required this.protectedPeriodCloseEnabled,
    required this.retainedEarningsCloseEnabled,
    required this.closedPeriodPostingProtectionEnabled,
    required this.periodReopenEnabled,
    required this.automaticSourcePosting,
  });

  final String fiscalPeriodId;
  final String label;
  final DateTime startDate;
  final DateTime endDate;
  final String fiscalPeriodStatus;
  final String? closedByUserId;
  final DateTime? closedAt;
  final String? preparationId;
  final String? journalEntryId;
  final int? temporaryAccountCount;
  final String? netIncome;
  final String? retainedEarningsBalanceBefore;
  final String? closeDigest;
  final String? closePostingId;
  final String? closingEntryNumber;
  final String? retainedEarningsBalanceAfter;
  final String closeStatus;
  final String? closeBlocker;
  final bool protectedPeriodCloseEnabled;
  final bool retainedEarningsCloseEnabled;
  final bool closedPeriodPostingProtectionEnabled;
  final bool periodReopenEnabled;
  final bool automaticSourcePosting;

  bool get isPrepared => closeStatus == 'prepared_confirmation_required';

  bool get usesProtectedPolicy =>
      protectedPeriodCloseEnabled &&
      retainedEarningsCloseEnabled &&
      closedPeriodPostingProtectionEnabled &&
      !periodReopenEnabled &&
      !automaticSourcePosting;

  factory PeriodCloseItem.fromPayload(Map<String, dynamic> payload) {
    final fiscalPeriodStatus = _requiredEnum(
      payload,
      'fiscal_period_status',
      const <String>{'open', 'review', 'closed'},
    );
    final closeStatus = _requiredString(payload, 'close_status');
    if (!_validCloseStatus(closeStatus)) {
      throw const SpinaApiException(
        'The SPINA server returned an unsupported period-close status.',
        code: 'invalid_period_close_payload',
      );
    }
    final item = PeriodCloseItem(
      fiscalPeriodId: _requiredUuid(payload, 'fiscal_period_id'),
      label: _requiredString(payload, 'label'),
      startDate: _requiredDate(payload, 'start_date'),
      endDate: _requiredDate(payload, 'end_date'),
      fiscalPeriodStatus: fiscalPeriodStatus,
      closedByUserId: _optionalUuid(payload, 'closed_by_user_id'),
      closedAt: _optionalTimestamp(payload, 'closed_at'),
      preparationId: _optionalUuid(payload, 'preparation_id'),
      journalEntryId: _optionalUuid(payload, 'journal_entry_id'),
      temporaryAccountCount: _optionalNonNegativeInt(
        payload,
        'temporary_account_count',
      ),
      netIncome: _optionalMoney(payload, 'net_income'),
      retainedEarningsBalanceBefore: _optionalMoney(
        payload,
        'retained_earnings_balance_before',
      ),
      closeDigest: _optionalDigest(payload, 'close_digest'),
      closePostingId: _optionalUuid(payload, 'close_posting_id'),
      closingEntryNumber: _optionalString(payload, 'closing_entry_number'),
      retainedEarningsBalanceAfter: _optionalMoney(
        payload,
        'retained_earnings_balance_after',
      ),
      closeStatus: closeStatus,
      closeBlocker: _optionalString(payload, 'close_blocker'),
      protectedPeriodCloseEnabled: _requiredBool(
        payload,
        'protected_period_close_enabled',
      ),
      retainedEarningsCloseEnabled: _requiredBool(
        payload,
        'retained_earnings_close_enabled',
      ),
      closedPeriodPostingProtectionEnabled: _requiredBool(
        payload,
        'closed_period_posting_protection_enabled',
      ),
      periodReopenEnabled: _requiredBool(payload, 'period_reopen_enabled'),
      automaticSourcePosting: _requiredBool(
        payload,
        'automatic_source_posting',
      ),
    );
    if (item.endDate.isBefore(item.startDate)) {
      throw const SpinaApiException(
        'The SPINA server returned invalid period-close dates.',
        code: 'invalid_period_close_payload',
      );
    }
    if ((item.isPrepared || item.closeStatus == 'closed_protected') &&
        !item._hasPostCoordinates) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete period-close coordinates.',
        code: 'invalid_period_close_payload',
      );
    }
    if (item.closeStatus == 'closed_protected' &&
        (item.fiscalPeriodStatus != 'closed' ||
            item.closePostingId == null ||
            item.closingEntryNumber == null ||
            item.retainedEarningsBalanceAfter == null ||
            item.closedByUserId == null ||
            item.closedAt == null)) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete protected-close evidence.',
        code: 'invalid_period_close_payload',
      );
    }
    return item;
  }

  void requirePostCoordinates() {
    if (!isPrepared || !_hasPostCoordinates) {
      throw ArgumentError(
        'A current protected period-close preparation is required before posting.',
      );
    }
  }

  bool get _hasPostCoordinates =>
      preparationId != null &&
      journalEntryId != null &&
      temporaryAccountCount != null &&
      netIncome != null &&
      retainedEarningsBalanceBefore != null &&
      closeDigest != null &&
      usesProtectedPolicy;
}

bool _validCloseStatus(String value) {
  return const <String>{
        'ready_for_review',
        'ready_to_prepare',
        'prepared_confirmation_required',
        'closed_protected',
        'closed_legacy_without_protected_close_audit',
      }.contains(value) ||
      value.startsWith('blocked_');
}

final _uuidPattern = RegExp(
  r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$',
);
final _moneyPattern = RegExp(r'^-?(0|[1-9][0-9]*)\.[0-9]{2}$');
final _digestPattern = RegExp(r'^[0-9a-fA-F]{64}$');
final _datePattern = RegExp(r'^\d{4}-\d{2}-\d{2}$');
final _offsetTimestampPattern = RegExp(r'(Z|[+-]\d{2}:\d{2})$');

String _requiredString(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value is! String || value.trim().isEmpty) {
    throw SpinaApiException(
      'The SPINA server omitted required period-close data.',
      code: 'invalid_period_close_payload',
    );
  }
  return value.trim();
}

String? _optionalString(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value == null) return null;
  if (value is! String || value.trim().isEmpty) {
    throw const SpinaApiException(
      'The SPINA server returned invalid period-close data.',
      code: 'invalid_period_close_payload',
    );
  }
  return value.trim();
}

String _requiredUuid(Map<String, dynamic> payload, String key) {
  final value = _requiredString(payload, key);
  if (!_uuidPattern.hasMatch(value)) {
    throw const SpinaApiException(
      'The SPINA server returned an invalid period-close identifier.',
      code: 'invalid_period_close_payload',
    );
  }
  return value.toLowerCase();
}

String? _optionalUuid(Map<String, dynamic> payload, String key) {
  if (payload[key] == null) return null;
  return _requiredUuid(payload, key);
}

String _requiredMoney(Map<String, dynamic> payload, String key) {
  final value = _requiredString(payload, key);
  if (!_moneyPattern.hasMatch(value)) {
    throw const SpinaApiException(
      'The SPINA server returned an invalid period-close amount.',
      code: 'invalid_period_close_payload',
    );
  }
  return value;
}

String? _optionalMoney(Map<String, dynamic> payload, String key) {
  if (payload[key] == null) return null;
  return _requiredMoney(payload, key);
}

String? _optionalDigest(Map<String, dynamic> payload, String key) {
  if (payload[key] == null) return null;
  final value = _requiredString(payload, key).toLowerCase();
  if (!_digestPattern.hasMatch(value)) {
    throw const SpinaApiException(
      'The SPINA server returned an invalid period-close digest.',
      code: 'invalid_period_close_payload',
    );
  }
  return value;
}

int _requiredNonNegativeInt(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value is! int || value < 0) {
    throw const SpinaApiException(
      'The SPINA server returned an invalid period-close count.',
      code: 'invalid_period_close_payload',
    );
  }
  return value;
}

int? _optionalNonNegativeInt(Map<String, dynamic> payload, String key) {
  if (payload[key] == null) return null;
  return _requiredNonNegativeInt(payload, key);
}

bool _requiredBool(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value is! bool) {
    throw const SpinaApiException(
      'The SPINA server returned an invalid period-close policy flag.',
      code: 'invalid_period_close_payload',
    );
  }
  return value;
}

String _requiredEnum(
  Map<String, dynamic> payload,
  String key,
  Set<String> allowed,
) {
  final value = _requiredString(payload, key);
  if (!allowed.contains(value)) {
    throw const SpinaApiException(
      'The SPINA server returned an unsupported period-close value.',
      code: 'invalid_period_close_payload',
    );
  }
  return value;
}

DateTime _requiredDate(Map<String, dynamic> payload, String key) {
  final value = _requiredString(payload, key);
  final parsed = DateTime.tryParse(value);
  if (!_datePattern.hasMatch(value) ||
      parsed == null ||
      _dateText(parsed) != value) {
    throw const SpinaApiException(
      'The SPINA server returned an invalid period-close date.',
      code: 'invalid_period_close_payload',
    );
  }
  return DateTime(parsed.year, parsed.month, parsed.day);
}

DateTime? _optionalTimestamp(Map<String, dynamic> payload, String key) {
  if (payload[key] == null) return null;
  final value = _requiredString(payload, key);
  final parsed = DateTime.tryParse(value);
  if (parsed == null || !_offsetTimestampPattern.hasMatch(value)) {
    throw const SpinaApiException(
      'The SPINA server returned an invalid period-close timestamp.',
      code: 'invalid_period_close_payload',
    );
  }
  return parsed.toUtc();
}

String periodCloseDateText(DateTime value) => _dateText(value);

String _dateText(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}
