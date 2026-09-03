import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/management_administration.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class ManagementAdministrationRepository {
  Future<ManagementStaffPage> loadStaff(
    UserSession session, {
    required String deviceId,
    String? query,
    String? role,
    String? status,
    int limit = 50,
    int offset = 0,
  });

  Future<ManagementStaffAccount> inviteStaff(
    UserSession session, {
    required String deviceId,
    required String username,
    required String email,
    required String fullName,
    required String role,
  });

  Future<ManagementStaffAccount> setRole(
    UserSession session, {
    required String deviceId,
    required String userId,
    required String role,
  });

  Future<ManagementStaffAccount> setAccountStatus(
    UserSession session, {
    required String deviceId,
    required String userId,
    required String status,
  });

  Future<List<ManagementDevice>> loadDevices(
    UserSession session, {
    required String deviceId,
    required String userId,
  });

  Future<ManagementDevice> setDeviceStatus(
    UserSession session, {
    required String deviceId,
    required String userId,
    required String managedDeviceId,
    required String status,
  });
}

class SpinaManagementAdministrationRepository
    implements ManagementAdministrationRepository {
  SpinaManagementAdministrationRepository({http.Client? client})
    : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<ManagementStaffPage> loadStaff(
    UserSession session, {
    required String deviceId,
    String? query,
    String? role,
    String? status,
    int limit = 50,
    int offset = 0,
  }) async {
    if (limit < 1 || offset < 0) {
      throw ArgumentError('Pagination values are invalid.');
    }
    final normalizedRole = _optionalAllowed(role, managementStaffRoles, 'role');
    final normalizedStatus = _optionalAllowed(
      status,
      managementAccountStatuses,
      'status',
    );
    final data = await _requestData(
      session,
      deviceId: deviceId,
      method: 'GET',
      uri: ApiConfig.managementStaffAccountsEndpoint(
        query: query,
        role: normalizedRole,
        status: normalizedStatus,
        limit: limit,
        offset: offset,
      ),
    );
    final values = data['accounts'];
    if (values is! List) {
      throw _invalidResponse();
    }
    final items = _parseCollection(values, ManagementStaffAccount.fromPayload);
    return ManagementStaffPage(
      items: items,
      nextOffset: offset + items.length,
      hasMore: items.length == limit,
    );
  }

  @override
  Future<ManagementStaffAccount> inviteStaff(
    UserSession session, {
    required String deviceId,
    required String username,
    required String email,
    required String fullName,
    required String role,
  }) async {
    final normalizedRole = _requiredAllowed(role, managementStaffRoles, 'role');
    final data = await _requestData(
      session,
      deviceId: deviceId,
      method: 'POST',
      uri: ApiConfig.managementInviteStaffEndpoint,
      body: <String, Object?>{
        'username': _requiredInput(username, 'username'),
        'email': _requiredInput(email, 'email').toLowerCase(),
        'full_name': _requiredInput(fullName, 'fullName'),
        'role': normalizedRole,
      },
    );
    return _parseItem(data['account'], ManagementStaffAccount.fromPayload);
  }

  @override
  Future<ManagementStaffAccount> setRole(
    UserSession session, {
    required String deviceId,
    required String userId,
    required String role,
  }) async {
    final normalizedRole = _requiredAllowed(role, managementStaffRoles, 'role');
    final data = await _requestData(
      session,
      deviceId: deviceId,
      method: 'PATCH',
      uri: ApiConfig.managementStaffRoleEndpoint(
        _requiredUuid(userId, 'userId'),
      ),
      body: <String, Object?>{'role': normalizedRole},
    );
    return _parseItem(data['account'], ManagementStaffAccount.fromPayload);
  }

  @override
  Future<ManagementStaffAccount> setAccountStatus(
    UserSession session, {
    required String deviceId,
    required String userId,
    required String status,
  }) async {
    final normalizedStatus = _requiredAllowed(
      status,
      managementAccountStatuses,
      'status',
    );
    final data = await _requestData(
      session,
      deviceId: deviceId,
      method: 'PATCH',
      uri: ApiConfig.managementStaffStatusEndpoint(
        _requiredUuid(userId, 'userId'),
      ),
      body: <String, Object?>{'status': normalizedStatus},
    );
    return _parseItem(data['account'], ManagementStaffAccount.fromPayload);
  }

  @override
  Future<List<ManagementDevice>> loadDevices(
    UserSession session, {
    required String deviceId,
    required String userId,
  }) async {
    final data = await _requestData(
      session,
      deviceId: deviceId,
      method: 'GET',
      uri: ApiConfig.managementStaffDevicesEndpoint(
        _requiredUuid(userId, 'userId'),
      ),
    );
    final values = data['devices'];
    if (values is! List) {
      throw _invalidResponse();
    }
    return _parseCollection(values, ManagementDevice.fromPayload);
  }

  @override
  Future<ManagementDevice> setDeviceStatus(
    UserSession session, {
    required String deviceId,
    required String userId,
    required String managedDeviceId,
    required String status,
  }) async {
    _requiredUuid(userId, 'userId');
    final normalizedStatus = _requiredAllowed(
      status,
      managementDeviceStatuses,
      'status',
    );
    final data = await _requestData(
      session,
      deviceId: deviceId,
      method: 'PATCH',
      uri: ApiConfig.managementDeviceStatusEndpoint(
        _requiredUuid(managedDeviceId, 'managedDeviceId'),
      ),
      body: <String, Object?>{'status': normalizedStatus},
    );
    return _parseItem(data['device'], ManagementDevice.fromPayload);
  }

  Future<Map<String, Object?>> _requestData(
    UserSession session, {
    required String deviceId,
    required String method,
    required Uri uri,
    Map<String, Object?>? body,
  }) async {
    final payload = await _request(
      session,
      deviceId: deviceId,
      method: method,
      uri: uri,
      body: body,
    );
    if (payload is! Map) {
      throw _invalidResponse();
    }
    return payload.map((key, value) => MapEntry(key.toString(), value));
  }

  Future<Object?> _request(
    UserSession session, {
    required String deviceId,
    required String method,
    required Uri uri,
    Map<String, Object?>? body,
  }) async {
    final headers = <String, String>{
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ${session.accessToken}',
      'X-Device-Id': deviceId,
    };
    late final http.Response response;
    try {
      response = switch (method) {
        'GET' => await _client.get(uri, headers: headers),
        'POST' => await _client.post(
          uri,
          headers: headers,
          body: jsonEncode(body ?? const <String, Object?>{}),
        ),
        'PATCH' => await _client.patch(
          uri,
          headers: headers,
          body: jsonEncode(body ?? const <String, Object?>{}),
        ),
        _ => throw ArgumentError.value(method, 'method'),
      };
    } on ArgumentError {
      rethrow;
    } on Exception {
      throw const SpinaApiException(
        'Staff administration could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }

    Map<String, dynamic> decoded;
    try {
      decoded = decodeJsonObject(response.body);
    } on Object {
      throw _invalidResponse(statusCode: response.statusCode);
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      try {
        return unwrapSpinaData(decoded, statusCode: response.statusCode);
      } on SpinaApiException {
        rethrow;
      } on Object {
        throw _invalidResponse(statusCode: response.statusCode);
      }
    }

    throw SpinaApiException(
      apiErrorMessage(decoded, statusCode: response.statusCode),
      statusCode: response.statusCode,
      code: firstNonEmptyString(<Object?>[
        stringMap(decoded['error'])['code'],
        decoded['code'],
      ]),
    );
  }
}

T _parseItem<T>(Object? value, T Function(Object?) parser) {
  try {
    return parser(value);
  } on Object {
    throw _invalidResponse();
  }
}

List<T> _parseCollection<T>(List<Object?> values, T Function(Object?) parser) {
  try {
    return List<T>.unmodifiable(values.map(parser));
  } on Object {
    throw _invalidResponse();
  }
}

SpinaApiException _invalidResponse({int? statusCode}) => SpinaApiException(
  'The SPINA server returned invalid staff administration data.',
  statusCode: statusCode,
  code: 'invalid_server_response',
);

String _requiredInput(String value, String name) {
  final normalized = value.trim();
  if (normalized.isEmpty) {
    throw ArgumentError.value(value, name, 'must not be empty');
  }
  return normalized;
}

String _requiredAllowed(String value, Set<String> allowed, String name) {
  final normalized = _requiredInput(value, name).toLowerCase();
  if (!allowed.contains(normalized)) {
    throw ArgumentError.value(value, name, 'is not supported');
  }
  return normalized;
}

String? _optionalAllowed(String? value, Set<String> allowed, String name) {
  if (value == null) {
    return null;
  }
  return _requiredAllowed(value, allowed, name);
}

final _uuidPattern = RegExp(
  r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$',
);

String _requiredUuid(String value, String name) {
  final normalized = _requiredInput(value, name);
  if (!_uuidPattern.hasMatch(normalized)) {
    throw ArgumentError.value(value, name, 'must be a UUID');
  }
  return normalized;
}
