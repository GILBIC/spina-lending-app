import 'dart:convert';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

/// Online-only transport for the staff tools. Mutations are never retried here.
class StaffOperationsClient {
  StaffOperationsClient({
    required this.deviceIdentityProvider,
    http.Client? client,
  }) : _client = client ?? http.Client(),
       _ownsClient = client == null;
  final DeviceIdentityProvider deviceIdentityProvider;
  final http.Client _client;
  final bool _ownsClient;

  Future<Map<String, dynamic>> request(
    UserSession session,
    String method,
    String path, {
    Map<String, String>? query,
    Map<String, Object?>? body,
  }) async {
    final identity = await deviceIdentityProvider.load();
    final request = http.Request(
      method,
      ApiConfig.endpoint(path).replace(queryParameters: query),
    );
    request.headers.addAll({
      'Accept': 'application/json',
      'Authorization': 'Bearer ${session.accessToken}',
      'X-Device-Id': identity.installationId,
    });
    if (body != null) {
      request.headers['Content-Type'] = 'application/json';
      request.body = jsonEncode(body);
    }
    final response = await _client
        .send(request)
        .then(http.Response.fromStream)
        .timeout(const Duration(seconds: 35));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      String message = 'The server could not complete this request.';
      try {
        final payload = decodeJsonObject(response.body);
        final detail = payload['detail'];
        message = detail is Map
            ? firstNonEmptyString([detail['message']]) ?? message
            : apiErrorMessage(payload, statusCode: response.statusCode);
      } on Exception {
        // Preserve the HTTP denial even when a gateway returns HTML or text.
      }
      throw SpinaApiException(message, statusCode: response.statusCode);
    }
    final data = unwrapSpinaData(
      decodeJsonObject(response.body),
      statusCode: response.statusCode,
    );
    if (data is! Map) {
      throw const SpinaApiException(
        'The server returned incomplete staff data.',
      );
    }
    return stringMap(data);
  }

  void close() {
    if (_ownsClient) _client.close();
  }
}

void requireStaffPermission(
  UserSession session,
  Iterable<String> permissions, {
  bool managementOnly = false,
}) {
  final roleAllowed =
      session.role == AppRole.management ||
      (!managementOnly && session.hasRole(AppRole.employee));
  if (!roleAllowed || !session.hasAnyPermission(permissions)) {
    throw const SpinaApiException(
      'Your current access does not allow this staff action.',
      statusCode: 403,
    );
  }
}

bool staffAccessRejected(Object error) =>
    error is SpinaApiException &&
    const [401, 403, 426].contains(error.statusCode);

String staffError(Object error) => error is SpinaApiException
    ? error.message
    : 'Connection interrupted. Refresh authoritative records before continuing.';

List<Map<String, dynamic>> staffRecords(Map<String, dynamic> data, String key) {
  final rows = data[key];
  if (rows is! List || rows.any((row) => row is! Map)) {
    throw const SpinaApiException(
      'The server returned incomplete staff records.',
    );
  }
  return rows.map(stringMap).toList(growable: false);
}

String requiredStaffText(Map<String, dynamic> data, String key) {
  final value = data[key];
  if (value is! String || value.trim().isEmpty) {
    throw const SpinaApiException(
      'The server returned incomplete staff records.',
    );
  }
  return value;
}
