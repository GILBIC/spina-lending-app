import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

final _recordId = RegExp(
  r'^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$',
  caseSensitive: false,
);
const _bookKinds = <String, String>{
  'owner_operations': 'Owner operations',
  'corporate_legal': 'Corporate legal',
  'synthetic': 'Synthetic',
};

String _requiredText(Map<String, dynamic> payload, String field) {
  final value = payload[field];
  if (value is! String || value.trim().isEmpty) {
    throw FormatException('Missing $field.');
  }
  return value;
}

class AccountingBookIdentity {
  const AccountingBookIdentity._({
    required this.configured,
    this.bookId,
    this.kind,
    this.entityLabel,
  });
  final bool configured;
  final String? bookId;
  final String? kind;
  final String? entityLabel;
  String? get kindLabel => _bookKinds[kind];

  factory AccountingBookIdentity.fromPayload(Map<String, dynamic> payload) {
    if (payload['status'] == 'unconfigured' &&
        payload['book_id'] == null &&
        payload['kind'] == null &&
        payload['entity_label'] == null) {
      return const AccountingBookIdentity._(configured: false);
    }
    final id = _requiredText(payload, 'book_id');
    final kind = _requiredText(payload, 'kind');
    if (payload['status'] != 'configured' ||
        !_recordId.hasMatch(id) ||
        !_bookKinds.containsKey(kind)) {
      throw const FormatException('Invalid book identity.');
    }
    return AccountingBookIdentity._(
      configured: true,
      bookId: id,
      kind: kind,
      entityLabel: _requiredText(payload, 'entity_label'),
    );
  }
}

class AccountingSourceBlocker {
  const AccountingSourceBlocker._({
    required this.sourceType,
    required this.sourceId,
    required this.effectiveDate,
    required this.amount,
    required this.reason,
  });
  final String sourceType;
  final String? sourceId;
  final String? effectiveDate;
  final String? amount;
  final String reason;
  bool get restricted => sourceType == 'restricted_source';

  factory AccountingSourceBlocker.fromPayload(Map<String, dynamic> payload) {
    if (payload['source_type'] == 'restricted_source') {
      if (payload['reason'] != 'treasury_account_access_required' ||
          ['source_id', 'effective_date', 'amount'].any(
            (field) => !payload.containsKey(field) || payload[field] != null,
          )) {
        throw const FormatException('Invalid restricted source.');
      }
      return const AccountingSourceBlocker._(
        sourceType: 'restricted_source',
        sourceId: null,
        effectiveDate: null,
        amount: null,
        reason: 'treasury_account_access_required',
      );
    }
    final amount = payload['amount'];
    if (!payload.containsKey('amount') ||
        (amount != null &&
            (amount is! String ||
                !RegExp(r'^-?\d+\.\d{2}$').hasMatch(amount)))) {
      throw const FormatException('Invalid exact source amount.');
    }
    return AccountingSourceBlocker._(
      sourceType: _requiredText(payload, 'source_type'),
      sourceId: _requiredText(payload, 'source_id'),
      effectiveDate: _requiredText(payload, 'effective_date'),
      amount: amount as String?,
      reason: _requiredText(payload, 'reason'),
    );
  }
}

class AccountingSourceCoverage {
  const AccountingSourceCoverage._({
    required this.sourceFamilies,
    required this.blockers,
    required this.blockerCount,
    required this.offset,
  });
  final List<String> sourceFamilies;
  final List<AccountingSourceBlocker> blockers;
  final int blockerCount;
  final int offset;
  bool get comprehensiveSourceCoverage => false;

  factory AccountingSourceCoverage.fromPayload(Map<String, dynamic> payload) {
    final families = payload['source_families'];
    final blockers = payload['blockers'];
    final count = payload['blocker_count'];
    final offset = payload['offset'];
    final limit = payload['limit'];
    if (payload['comprehensive_source_coverage'] != false ||
        families is! List ||
        families.isEmpty ||
        families.any((value) => value != 'treasury' && value != 'collector') ||
        blockers is! List ||
        count is! int ||
        count < blockers.length ||
        offset is! int ||
        offset < 0 ||
        limit is! int ||
        limit < 1 ||
        blockers.length > limit) {
      throw const FormatException('Invalid source coverage.');
    }
    return AccountingSourceCoverage._(
      blockerCount: count,
      offset: offset,
      sourceFamilies: List<String>.unmodifiable(families.cast<String>()),
      blockers: List<AccountingSourceBlocker>.unmodifiable(
        blockers.map(
          (row) => AccountingSourceBlocker.fromPayload(stringMap(row)),
        ),
      ),
    );
  }
}

abstract interface class AccountingReadinessRepository {
  Future<AccountingBookIdentity> loadBook(
    UserSession session, {
    required String deviceId,
  });
  Future<AccountingSourceCoverage> loadSourceCoverage(
    UserSession session, {
    required String deviceId,
    required String periodId,
  });
}

class SpinaAccountingReadinessRepository
    implements AccountingReadinessRepository {
  SpinaAccountingReadinessRepository({http.Client? client})
    : _client = client ?? http.Client();
  final http.Client _client;
  static const _base = '/api/mobile/v1/management/financial-accounting';

  @override
  Future<AccountingBookIdentity> loadBook(
    UserSession session, {
    required String deviceId,
  }) async {
    final payload = await _get('$_base/book', session, deviceId);
    return AccountingBookIdentity.fromPayload(stringMap(payload['book']));
  }

  @override
  Future<AccountingSourceCoverage> loadSourceCoverage(
    UserSession session, {
    required String deviceId,
    required String periodId,
  }) async {
    if (!_recordId.hasMatch(periodId)) {
      throw const FormatException('Invalid period identity.');
    }
    final payload = await _get(
      '$_base/period-close/${Uri.encodeComponent(periodId)}/source-blockers',
      session,
      deviceId,
    );
    final coverage = stringMap(payload['source_coverage']);
    if (coverage['fiscal_period_id'] != periodId) {
      throw const FormatException(
        'Source coverage does not match the selected period.',
      );
    }
    return AccountingSourceCoverage.fromPayload(coverage);
  }

  Future<Map<String, dynamic>> _get(
    String path,
    UserSession session,
    String deviceId,
  ) async {
    late final http.Response response;
    try {
      response = await _client.get(
        ApiConfig.endpoint(path),
        headers: {
          'Accept': 'application/json',
          'Authorization': 'Bearer ${session.accessToken}',
          'X-Device-Id': deviceId,
        },
      );
    } on Exception {
      throw const SpinaApiException(
        'Accounting readiness could not be reached.',
        code: 'network_unavailable',
      );
    }
    final payload = decodeJsonObject(response.body);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw SpinaApiException(
        apiErrorMessage(payload, statusCode: response.statusCode),
        statusCode: response.statusCode,
      );
    }
    return stringMap(unwrapSpinaData(payload, statusCode: response.statusCode));
  }
}
