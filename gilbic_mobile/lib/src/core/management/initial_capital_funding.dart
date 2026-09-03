import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class InitialCapitalFundingOverview {
  const InitialCapitalFundingOverview({
    required this.items,
    required this.summary,
    required this.cashAccounts,
    required this.permissions,
    required this.limit,
    required this.offset,
    required this.protectedInitialCapitalFundingEnabled,
    required this.syntheticOpeningBalanceRequired,
    required this.automaticSourcePosting,
    required this.notice,
  });

  final List<InitialCapitalFundingItem> items;
  final InitialCapitalFundingSummary summary;
  final List<InitialCapitalCashAccount> cashAccounts;
  final InitialCapitalFundingPermissions permissions;
  final int limit;
  final int offset;
  final bool protectedInitialCapitalFundingEnabled;
  final bool syntheticOpeningBalanceRequired;
  final bool automaticSourcePosting;
  final String notice;

  factory InitialCapitalFundingOverview.fromPayload(
    Map<String, dynamic> payload,
  ) {
    final rawItems = payload['items'];
    final rawAccounts = payload['cash_accounts'];
    if (rawItems is! List || rawAccounts is! List) {
      throw _invalid('queue collections');
    }
    final overview = InitialCapitalFundingOverview(
      items: rawItems
          .map((item) => InitialCapitalFundingItem.fromPayload(stringMap(item)))
          .toList(growable: false),
      summary: InitialCapitalFundingSummary.fromPayload(
        stringMap(payload['summary']),
      ),
      cashAccounts: rawAccounts
          .map(
            (account) =>
                InitialCapitalCashAccount.fromPayload(stringMap(account)),
          )
          .toList(growable: false),
      permissions: InitialCapitalFundingPermissions.fromPayload(
        stringMap(payload['permissions']),
      ),
      limit: _nonNegativeInt(payload, 'limit'),
      offset: _nonNegativeInt(payload, 'offset'),
      protectedInitialCapitalFundingEnabled: _bool(
        payload,
        'protected_initial_capital_funding_enabled',
      ),
      syntheticOpeningBalanceRequired: _bool(
        payload,
        'synthetic_opening_balance_required',
      ),
      automaticSourcePosting: _bool(payload, 'automatic_source_posting'),
      notice: _text(payload, 'notice'),
    );
    if (!overview.protectedInitialCapitalFundingEnabled ||
        overview.syntheticOpeningBalanceRequired ||
        overview.automaticSourcePosting ||
        overview.limit < 1 ||
        overview.limit > 200) {
      throw _invalid('protected accounting policy');
    }
    final codes = <String>{};
    for (final account in overview.cashAccounts) {
      if (!codes.add(account.code)) throw _invalid('cash-account choices');
    }
    return overview;
  }
}

class InitialCapitalFundingSummary {
  const InitialCapitalFundingSummary({
    required this.evidenceCount,
    required this.evidenceReadyCount,
    required this.preparedNotPostedCount,
    required this.postedCount,
    required this.blockedNoOpenPeriodCount,
    required this.totalAmount,
    required this.postedAmount,
  });

  final int evidenceCount;
  final int evidenceReadyCount;
  final int preparedNotPostedCount;
  final int postedCount;
  final int blockedNoOpenPeriodCount;
  final String totalAmount;
  final String postedAmount;

  factory InitialCapitalFundingSummary.fromPayload(
    Map<String, dynamic> payload,
  ) => InitialCapitalFundingSummary(
    evidenceCount: _nonNegativeInt(payload, 'evidence_count'),
    evidenceReadyCount: _nonNegativeInt(payload, 'evidence_ready_count'),
    preparedNotPostedCount: _nonNegativeInt(
      payload,
      'prepared_not_posted_count',
    ),
    postedCount: _nonNegativeInt(payload, 'posted_count'),
    blockedNoOpenPeriodCount: _nonNegativeInt(
      payload,
      'blocked_no_open_period_count',
    ),
    totalAmount: _money(payload, 'total_amount'),
    postedAmount: _money(payload, 'posted_amount'),
  );
}

class InitialCapitalFundingPermissions {
  const InitialCapitalFundingPermissions({
    required this.evidenceRecord,
    required this.prepare,
    required this.post,
  });

  final bool evidenceRecord;
  final bool prepare;
  final bool post;

  factory InitialCapitalFundingPermissions.fromPayload(
    Map<String, dynamic> payload,
  ) => InitialCapitalFundingPermissions(
    evidenceRecord: _bool(payload, 'evidence_record'),
    prepare: _bool(payload, 'prepare'),
    post: _bool(payload, 'post'),
  );
}

class InitialCapitalCashAccount {
  const InitialCapitalCashAccount({required this.code, required this.name});

  final String code;
  final String name;

  factory InitialCapitalCashAccount.fromPayload(Map<String, dynamic> payload) =>
      InitialCapitalCashAccount(
        code: _text(payload, 'code'),
        name: _text(payload, 'name'),
      );
}

class InitialCapitalFundingItem {
  const InitialCapitalFundingItem({
    required this.evidenceId,
    required this.fundingDate,
    required this.amount,
    required this.cashAccountCode,
    required this.cashAccountName,
    required this.capitalAccountCode,
    required this.evidenceSource,
    required this.evidenceReference,
    required this.evidenceDigest,
    required this.evidenceNote,
    required this.recordedByUserId,
    required this.recordedAt,
    required this.journalEntryId,
    required this.journalStatus,
    required this.entryNumber,
    required this.fiscalPeriodId,
    required this.preparedByUserId,
    required this.preparedAt,
    required this.confirmationDigest,
    required this.postedByUserId,
    required this.postedAt,
    required this.accountingStatus,
    required this.accountingBlocker,
    required this.protectedInitialCapitalFundingEnabled,
    required this.syntheticOpeningBalanceRequired,
    required this.automaticSourcePosting,
  });

  final String evidenceId;
  final String fundingDate;
  final String amount;
  final String cashAccountCode;
  final String cashAccountName;
  final String capitalAccountCode;
  final String evidenceSource;
  final String evidenceReference;
  final String evidenceDigest;
  final String evidenceNote;
  final String recordedByUserId;
  final DateTime recordedAt;
  final String? journalEntryId;
  final String? journalStatus;
  final String? entryNumber;
  final String? fiscalPeriodId;
  final String? preparedByUserId;
  final DateTime? preparedAt;
  final String? confirmationDigest;
  final String? postedByUserId;
  final DateTime? postedAt;
  final String accountingStatus;
  final String? accountingBlocker;
  final bool protectedInitialCapitalFundingEnabled;
  final bool syntheticOpeningBalanceRequired;
  final bool automaticSourcePosting;

  bool get isEvidenceReady => accountingStatus == 'evidence_ready';
  bool get isPrepared => accountingStatus == 'prepared_not_posted';
  bool get isPosted => accountingStatus == 'posted';

  factory InitialCapitalFundingItem.fromPayload(Map<String, dynamic> payload) {
    final item = InitialCapitalFundingItem(
      evidenceId: _uuid(payload, 'evidence_id'),
      fundingDate: _date(payload, 'funding_date'),
      amount: _positiveMoney(payload, 'amount'),
      cashAccountCode: _text(payload, 'cash_account_code'),
      cashAccountName: _text(payload, 'cash_account_name'),
      capitalAccountCode: _text(payload, 'capital_account_code'),
      evidenceSource: _text(payload, 'evidence_source'),
      evidenceReference: _text(payload, 'evidence_reference'),
      evidenceDigest: _digest(payload, 'evidence_digest'),
      evidenceNote: _text(payload, 'evidence_note'),
      recordedByUserId: _uuid(payload, 'recorded_by_user_id'),
      recordedAt: _dateTime(payload, 'recorded_at'),
      journalEntryId: _optionalUuid(payload, 'journal_entry_id'),
      journalStatus: _optionalEnum(payload, 'journal_status', const <String>{
        'draft',
        'posted',
      }),
      entryNumber: _optionalText(payload, 'entry_number'),
      fiscalPeriodId: _optionalUuid(payload, 'fiscal_period_id'),
      preparedByUserId: _optionalUuid(payload, 'prepared_by_user_id'),
      preparedAt: _optionalDateTime(payload, 'prepared_at'),
      confirmationDigest: _optionalDigest(payload, 'confirmation_digest'),
      postedByUserId: _optionalUuid(payload, 'posted_by_user_id'),
      postedAt: _optionalDateTime(payload, 'posted_at'),
      accountingStatus: _enum(
        payload,
        'accounting_status',
        _accountingStatuses,
      ),
      accountingBlocker: _optionalText(payload, 'accounting_blocker'),
      protectedInitialCapitalFundingEnabled: _bool(
        payload,
        'protected_initial_capital_funding_enabled',
      ),
      syntheticOpeningBalanceRequired: _bool(
        payload,
        'synthetic_opening_balance_required',
      ),
      automaticSourcePosting: _bool(payload, 'automatic_source_posting'),
    );
    item._validateState();
    return item;
  }

  void requirePrepareCoordinates() {
    if (!isEvidenceReady ||
        journalEntryId != null ||
        fiscalPeriodId != null ||
        accountingBlocker != null) {
      throw ArgumentError('Exact evidence-ready coordinates are required.');
    }
  }

  void requirePostCoordinates() {
    if (!isPrepared ||
        journalEntryId == null ||
        journalStatus != 'draft' ||
        fiscalPeriodId == null ||
        preparedByUserId == null ||
        preparedAt == null) {
      throw ArgumentError(
        'Exact prepared initial-capital coordinates are required.',
      );
    }
  }

  void _validateState() {
    if (!protectedInitialCapitalFundingEnabled ||
        syntheticOpeningBalanceRequired ||
        automaticSourcePosting ||
        capitalAccountCode != '3000') {
      throw _invalid('protected item policy');
    }
    try {
      if (isEvidenceReady) requirePrepareCoordinates();
      if (isPrepared) requirePostCoordinates();
    } on ArgumentError {
      throw _invalid('protected action coordinates');
    }
    if (accountingStatus == 'blocked_no_open_period' &&
        (accountingBlocker == null || journalEntryId != null)) {
      throw _invalid('blocked evidence state');
    }
    if (isPosted &&
        (journalEntryId == null ||
            journalStatus != 'posted' ||
            entryNumber == null ||
            fiscalPeriodId == null ||
            confirmationDigest == null ||
            postedByUserId == null ||
            postedAt == null)) {
      throw _invalid('posted evidence state');
    }
  }
}

class InitialCapitalEvidenceDraft {
  const InitialCapitalEvidenceDraft({
    required this.fundingDate,
    required this.amount,
    required this.cashAccountCode,
    required this.evidenceSource,
    required this.evidenceReference,
    required this.evidenceDigest,
    required this.evidenceNote,
  });

  final String fundingDate;
  final String amount;
  final String cashAccountCode;
  final String evidenceSource;
  final String evidenceReference;
  final String evidenceDigest;
  final String evidenceNote;

  void validate() {
    final payload = <String, dynamic>{
      'funding_date': fundingDate,
      'amount': amount,
      'cash_account_code': cashAccountCode,
      'evidence_source': evidenceSource,
      'evidence_reference': evidenceReference,
      'evidence_digest': evidenceDigest,
      'evidence_note': evidenceNote,
    };
    _date(payload, 'funding_date');
    _positiveMoney(payload, 'amount');
    _text(payload, 'cash_account_code');
    _text(payload, 'evidence_source');
    _text(payload, 'evidence_reference');
    _digest(payload, 'evidence_digest');
    if (_text(payload, 'evidence_note').length < 20) {
      throw ArgumentError('A meaningful retained-evidence note is required.');
    }
  }

  Map<String, Object> toPayload(String idempotencyKey) => <String, Object>{
    'idempotency_key': idempotencyKey,
    'funding_date': fundingDate,
    'amount': amount,
    'cash_account_code': cashAccountCode,
    'evidence_source': evidenceSource.trim(),
    'evidence_reference': evidenceReference.trim(),
    'evidence_digest': evidenceDigest,
    'evidence_note': evidenceNote.trim(),
  };
}

const _accountingStatuses = <String>{
  'evidence_ready',
  'prepared_not_posted',
  'posted',
  'blocked_no_open_period',
};
final _uuidPattern = RegExp(
  r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$',
);
final _moneyPattern = RegExp(r'^(0|[1-9][0-9]*)\.[0-9]{2}$');
final _digestPattern = RegExp(r'^[0-9a-f]{64}$');
final _datePattern = RegExp(r'^\d{4}-\d{2}-\d{2}$');

SpinaApiException _invalid(String field) => SpinaApiException(
  'The SPINA server returned incomplete initial-capital $field.',
  code: 'invalid_initial_capital_payload',
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

String _positiveMoney(Map<String, dynamic> payload, String key) {
  final value = _money(payload, key);
  if (value == '0.00') throw _invalid(key);
  return value;
}

String _digest(Map<String, dynamic> payload, String key) {
  final value = _text(payload, key);
  if (!_digestPattern.hasMatch(value)) throw _invalid(key);
  return value;
}

String? _optionalDigest(Map<String, dynamic> payload, String key) {
  if (payload[key] == null) return null;
  return _digest(payload, key);
}

String _date(Map<String, dynamic> payload, String key) {
  final value = _text(payload, key);
  final parsed = DateTime.tryParse(value);
  if (!_datePattern.hasMatch(value) ||
      parsed == null ||
      initialCapitalDateText(parsed) != value) {
    throw _invalid(key);
  }
  return value;
}

DateTime _dateTime(Map<String, dynamic> payload, String key) {
  final value = _text(payload, key);
  final parsed = DateTime.tryParse(value);
  if (parsed == null) throw _invalid(key);
  return parsed;
}

DateTime? _optionalDateTime(Map<String, dynamic> payload, String key) {
  if (payload[key] == null) return null;
  return _dateTime(payload, key);
}

int _nonNegativeInt(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value is! int || value < 0) throw _invalid(key);
  return value;
}

bool _bool(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value is! bool) throw _invalid(key);
  return value;
}

String _enum(Map<String, dynamic> payload, String key, Set<String> allowed) {
  final value = _text(payload, key);
  if (!allowed.contains(value)) throw _invalid(key);
  return value;
}

String? _optionalEnum(
  Map<String, dynamic> payload,
  String key,
  Set<String> allowed,
) {
  if (payload[key] == null) return null;
  return _enum(payload, key, allowed);
}

String initialCapitalDateText(DateTime value) =>
    '${value.year.toString().padLeft(4, '0')}-'
    '${value.month.toString().padLeft(2, '0')}-'
    '${value.day.toString().padLeft(2, '0')}';
