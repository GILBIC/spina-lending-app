import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/management_alerts_audit.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class ManagementAlertsAuditRepository {
  Future<ManagementAlertsAuditSnapshot> loadSnapshot(
    UserSession session, {
    required String deviceId,
    int windowDays = 30,
    int limit = 100,
  });
}

class SpinaManagementAlertsAuditRepository
    implements ManagementAlertsAuditRepository {
  SpinaManagementAlertsAuditRepository({http.Client? client})
    : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<ManagementAlertsAuditSnapshot> loadSnapshot(
    UserSession session, {
    required String deviceId,
    int windowDays = 30,
    int limit = 100,
  }) async {
    final endpoint =
        ApiConfig.endpoint('/api/mobile/v1/management/alerts-audit').replace(
          queryParameters: <String, String>{
            'window_days': '$windowDays',
            'limit': '$limit',
          },
        );
    late final http.Response response;
    try {
      response = await _client.get(
        endpoint,
        headers: <String, String>{
          'Accept': 'application/json',
          'Authorization': 'Bearer ${session.accessToken}',
          'X-Device-Id': deviceId,
        },
      );
    } on Exception {
      throw const SpinaApiException(
        'Management alerts and audit could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }

    late final Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned an unreadable alerts and audit response.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = payload['detail'];
      final detailMap = stringMap(detail);
      throw SpinaApiException(
        firstNonEmptyString(<Object?>[
              detailMap['message'],
              detail is String ? detail : null,
              payload['message'],
            ]) ??
            apiErrorMessage(payload, statusCode: response.statusCode),
        statusCode: response.statusCode,
        code: firstNonEmptyString(<Object?>[
          detailMap['code'],
          stringMap(payload['error'])['code'],
          payload['code'],
        ]),
      );
    }
    try {
      return ManagementAlertsAuditSnapshot.fromPayload(
        stringMap(unwrapSpinaData(payload, statusCode: response.statusCode)),
      );
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned invalid Management alerts and audit data.',
        statusCode: response.statusCode,
        code: 'invalid_management_alerts_audit',
      );
    }
  }
}
