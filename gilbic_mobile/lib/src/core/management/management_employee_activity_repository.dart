import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/management_employee_activity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class ManagementEmployeeActivityRepository {
  Future<ManagementEmployeeActivityPage> listEmployees(
    UserSession session, {
    required String deviceId,
    required DateTime dateFrom,
    required DateTime dateTo,
    String? query,
    ManagementEmployeeActivityDomain? domain,
    ManagementEmployeeActivityStatus? status,
    int limit = 50,
    int offset = 0,
  });

  Future<ManagementEmployeeActivityTimeline> loadTimeline(
    UserSession session, {
    required String deviceId,
    required String employeeUserId,
    required DateTime dateFrom,
    required DateTime dateTo,
    ManagementEmployeeActivityDomain? domain,
    int limit = 100,
    int offset = 0,
  });
}

class SpinaManagementEmployeeActivityRepository
    implements ManagementEmployeeActivityRepository {
  SpinaManagementEmployeeActivityRepository({http.Client? client})
    : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<ManagementEmployeeActivityPage> listEmployees(
    UserSession session, {
    required String deviceId,
    required DateTime dateFrom,
    required DateTime dateTo,
    String? query,
    ManagementEmployeeActivityDomain? domain,
    ManagementEmployeeActivityStatus? status,
    int limit = 50,
    int offset = 0,
  }) async {
    final range = _validatedRange(dateFrom, dateTo);
    _validatePagination(limit, offset);
    final normalizedQuery = _normalizedQuery(query);
    final parameters = <String, String>{
      'date_from': _dateText(range.$1),
      'date_to': _dateText(range.$2),
      if (normalizedQuery != null) 'q': normalizedQuery,
      if (domain != null) 'domain': domain.serverValue,
      if (status != null) 'status': status.serverValue,
      'limit': '$limit',
      'offset': '$offset',
    };
    final payload = await _getData(
      session,
      deviceId: deviceId,
      endpoint: ApiConfig.endpoint(
        '/api/mobile/v1/management/employee-activity',
      ).replace(queryParameters: parameters),
    );
    try {
      return ManagementEmployeeActivityPage.fromPayload(payload);
    } on Object {
      throw _invalidResponse();
    }
  }

  @override
  Future<ManagementEmployeeActivityTimeline> loadTimeline(
    UserSession session, {
    required String deviceId,
    required String employeeUserId,
    required DateTime dateFrom,
    required DateTime dateTo,
    ManagementEmployeeActivityDomain? domain,
    int limit = 100,
    int offset = 0,
  }) async {
    final normalizedEmployeeId = _requiredUuid(
      employeeUserId,
      'employeeUserId',
    );
    final range = _validatedRange(dateFrom, dateTo);
    _validatePagination(limit, offset);
    final parameters = <String, String>{
      'date_from': _dateText(range.$1),
      'date_to': _dateText(range.$2),
      if (domain != null) 'domain': domain.serverValue,
      'limit': '$limit',
      'offset': '$offset',
    };
    final payload = await _getData(
      session,
      deviceId: deviceId,
      endpoint: ApiConfig.endpoint(
        '/api/mobile/v1/management/employee-activity/$normalizedEmployeeId',
      ).replace(queryParameters: parameters),
    );
    try {
      return ManagementEmployeeActivityTimeline.fromPayload(payload);
    } on Object {
      throw _invalidResponse();
    }
  }

  Future<Object?> _getData(
    UserSession session, {
    required String deviceId,
    required Uri endpoint,
  }) async {
    final normalizedDeviceId = deviceId.trim();
    if (normalizedDeviceId.isEmpty) {
      throw ArgumentError.value(deviceId, 'deviceId', 'must not be empty');
    }

    late final http.Response response;
    try {
      response = await _client.get(
        endpoint,
        headers: <String, String>{
          'Accept': 'application/json',
          'Authorization': 'Bearer ${session.accessToken}',
          'X-Device-Id': normalizedDeviceId,
        },
      );
    } on Exception {
      throw const SpinaApiException(
        'Employee Activity could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }

    late final Map<String, dynamic> decoded;
    try {
      decoded = decodeJsonObject(response.body);
    } on Object {
      throw _invalidResponse(statusCode: response.statusCode);
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = decoded['detail'];
      final detailMap = stringMap(detail);
      throw SpinaApiException(
        firstNonEmptyString(<Object?>[
              detailMap['message'],
              detail is String ? detail : null,
              decoded['message'],
            ]) ??
            apiErrorMessage(decoded, statusCode: response.statusCode),
        statusCode: response.statusCode,
        code: firstNonEmptyString(<Object?>[
          detailMap['code'],
          stringMap(decoded['error'])['code'],
          decoded['code'],
        ]),
      );
    }

    try {
      final data = unwrapSpinaData(decoded, statusCode: response.statusCode);
      if (data is! Map || data.keys.any((key) => key is! String)) {
        throw const FormatException('Invalid Employee Activity response.');
      }
      return Map<String, Object?>.from(data);
    } on Object {
      throw _invalidResponse(statusCode: response.statusCode);
    }
  }
}

SpinaApiException _invalidResponse({int? statusCode}) => SpinaApiException(
  'The SPINA server returned invalid Employee Activity data.',
  statusCode: statusCode,
  code: 'invalid_management_employee_activity',
);

(DateTime, DateTime) _validatedRange(DateTime dateFrom, DateTime dateTo) {
  final start = DateTime.utc(dateFrom.year, dateFrom.month, dateFrom.day);
  final end = DateTime.utc(dateTo.year, dateTo.month, dateTo.day);
  final days = end.difference(start).inDays;
  if (days < 0 || days >= 31) {
    throw ArgumentError('Employee Activity date range must be 1 to 31 days.');
  }
  return (start, end);
}

void _validatePagination(int limit, int offset) {
  if (limit < 1 || limit > 100 || offset < 0) {
    throw ArgumentError('Employee Activity pagination is invalid.');
  }
}

String? _normalizedQuery(String? query) {
  final normalized = (query ?? '').split(RegExp(r'\s+')).join(' ').trim();
  if (normalized.isEmpty) return null;
  if (normalized.length > 100) {
    throw ArgumentError.value(query, 'query', 'must not exceed 100 characters');
  }
  return normalized;
}

String _dateText(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}

final _uuidPattern = RegExp(
  r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$',
);

String _requiredUuid(String value, String name) {
  final normalized = value.trim();
  if (!_uuidPattern.hasMatch(normalized)) {
    throw ArgumentError.value(value, name, 'must be a UUID');
  }
  return normalized.toLowerCase();
}
