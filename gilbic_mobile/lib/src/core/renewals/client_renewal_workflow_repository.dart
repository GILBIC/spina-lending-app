import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow.dart';
import 'package:http/http.dart' as http;

abstract interface class ClientRenewalWorkflowRepository {
  Future<List<CollectorRenewalRequest>> list(
    UserSession session, {
    required String deviceId,
  });

  Future<CollectorRenewalRequest> decide(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required String decision,
  });

  Future<CollectorRenewalRequest> sign(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required String signerId,
  });

  Future<CollectorRenewalRequest> confirmCashReceived(
    UserSession session, {
    required String deviceId,
    required String requestId,
  });
}

class SpinaClientRenewalWorkflowRepository
    implements ClientRenewalWorkflowRepository {
  SpinaClientRenewalWorkflowRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<List<CollectorRenewalRequest>> list(
    UserSession session, {
    required String deviceId,
  }) async {
    final payload = await _request(
      session,
      deviceId: deviceId,
      method: 'GET',
      uri: ApiConfig.endpoint('/api/mobile/v1/client/renewal-workflow'),
    );
    final data = stringMap(unwrapSpinaData(payload));
    final raw = data['requests'];
    if (raw is! List) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete renewal workflow data.',
        code: 'invalid_client_renewal_workflow_payload',
      );
    }
    return raw
        .map((item) => CollectorRenewalRequest.fromPayload(stringMap(item)))
        .toList(growable: false);
  }

  @override
  Future<CollectorRenewalRequest> decide(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required String decision,
  }) {
    return _requestItem(
      session,
      deviceId: deviceId,
      uri: ApiConfig.endpoint(
        '/api/mobile/v1/client/renewals/${Uri.encodeComponent(requestId)}/decision',
      ),
      body: <String, Object?>{'decision': decision},
    );
  }

  @override
  Future<CollectorRenewalRequest> sign(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required String signerId,
  }) {
    return _requestItem(
      session,
      deviceId: deviceId,
      uri: ApiConfig.endpoint(
        '/api/mobile/v1/renewals/${Uri.encodeComponent(requestId)}/signers/${Uri.encodeComponent(signerId)}/sign',
      ),
      body: const <String, Object?>{},
    );
  }

  @override
  Future<CollectorRenewalRequest> confirmCashReceived(
    UserSession session, {
    required String deviceId,
    required String requestId,
  }) {
    return _requestItem(
      session,
      deviceId: deviceId,
      uri: ApiConfig.endpoint(
        '/api/mobile/v1/client/renewals/${Uri.encodeComponent(requestId)}/cash-confirm',
      ),
      body: const <String, Object?>{},
    );
  }

  Future<CollectorRenewalRequest> _requestItem(
    UserSession session, {
    required String deviceId,
    required Uri uri,
    required Map<String, Object?> body,
  }) async {
    final payload = await _request(
      session,
      deviceId: deviceId,
      method: 'POST',
      uri: uri,
      body: body,
    );
    final data = stringMap(unwrapSpinaData(payload));
    final request = stringMap(data['request']);
    if (request.isEmpty) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete renewal workflow data.',
        code: 'invalid_client_renewal_workflow_payload',
      );
    }
    return CollectorRenewalRequest.fromPayload(request);
  }

  Future<Map<String, dynamic>> _request(
    UserSession session, {
    required String deviceId,
    required String method,
    required Uri uri,
    Map<String, Object?>? body,
  }) async {
    late final http.Response response;
    final headers = <String, String>{
      'Accept': 'application/json',
      'Authorization': 'Bearer ${session.accessToken}',
      'X-Session-Id': session.accessToken,
      'X-Device-Id': deviceId,
    };
    try {
      if (method == 'GET') {
        response = await _client.get(uri, headers: headers);
      } else {
        headers['Content-Type'] = 'application/json';
        response = await _client.post(
          uri,
          headers: headers,
          body: jsonEncode(body ?? const <String, Object?>{}),
        );
      }
    } on Exception {
      throw const SpinaApiException(
        'Renewal workflow could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }
    final payload = _decode(response);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = stringMap(payload['detail']);
      throw SpinaApiException(
        firstNonEmptyString(<Object?>[
              detail['message'],
              payload['message'],
            ]) ??
            apiErrorMessage(payload, statusCode: response.statusCode),
        statusCode: response.statusCode,
        code: firstNonEmptyString(<Object?>[
          detail['code'],
          payload['code'],
        ]),
      );
    }
    return payload;
  }

  Map<String, dynamic> _decode(http.Response response) {
    try {
      return decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable renewal data.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }
  }
}
