import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow.dart';
import 'package:gilbic_mobile/src/core/renewals/management_renewal_workflow.dart';
import 'package:http/http.dart' as http;

abstract interface class ManagementRenewalWorkflowRepository {
  Future<List<ManagementRenewalWorkflowItem>> list(
    UserSession session, {
    required String deviceId,
    required String status,
  });

  Future<CollectorRenewalRequest> submitTerms(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required ManagementRenewalTermsDraft draft,
  });

  Future<CollectorRenewalRequest> releaseToCollector(
    UserSession session, {
    required String deviceId,
    required String requestId,
  });

  Future<CollectorRenewalRequest> reviewProof(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required String decision,
    required String note,
  });

  Future<CollectorRenewalRequest> activate(
    UserSession session, {
    required String deviceId,
    required String requestId,
  });
}

class SpinaManagementRenewalWorkflowRepository
    implements ManagementRenewalWorkflowRepository {
  SpinaManagementRenewalWorkflowRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<List<ManagementRenewalWorkflowItem>> list(
    UserSession session, {
    required String deviceId,
    required String status,
  }) async {
    final uri = ApiConfig.endpoint(
      '/api/mobile/v1/management/renewal-workflow?status=${Uri.encodeQueryComponent(status)}',
    );
    final payload = await _request(
      session,
      deviceId: deviceId,
      method: 'GET',
      uri: uri,
    );
    final data = stringMap(unwrapSpinaData(payload));
    final raw = data['requests'];
    if (raw is! List) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete Management renewal data.',
        code: 'invalid_management_renewal_payload',
      );
    }
    return raw
        .map((item) => ManagementRenewalWorkflowItem.fromPayload(stringMap(item)))
        .toList(growable: false);
  }

  @override
  Future<CollectorRenewalRequest> submitTerms(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required ManagementRenewalTermsDraft draft,
  }) {
    return _requestItem(
      session,
      deviceId: deviceId,
      uri: ApiConfig.endpoint(
        '/api/mobile/v1/management/renewals/${Uri.encodeComponent(requestId)}/terms',
      ),
      body: draft.toJson(),
    );
  }

  @override
  Future<CollectorRenewalRequest> releaseToCollector(
    UserSession session, {
    required String deviceId,
    required String requestId,
  }) {
    return _requestItem(
      session,
      deviceId: deviceId,
      uri: ApiConfig.endpoint(
        '/api/mobile/v1/management/renewals/${Uri.encodeComponent(requestId)}/release-to-collector',
      ),
      body: const <String, Object?>{},
    );
  }

  @override
  Future<CollectorRenewalRequest> reviewProof(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required String decision,
    required String note,
  }) {
    return _requestItem(
      session,
      deviceId: deviceId,
      uri: ApiConfig.endpoint(
        '/api/mobile/v1/management/renewals/${Uri.encodeComponent(requestId)}/proof-review',
      ),
      body: <String, Object?>{
        'decision': decision,
        'note': note,
      },
    );
  }

  @override
  Future<CollectorRenewalRequest> activate(
    UserSession session, {
    required String deviceId,
    required String requestId,
  }) {
    return _requestItem(
      session,
      deviceId: deviceId,
      uri: ApiConfig.endpoint(
        '/api/mobile/v1/management/renewals/${Uri.encodeComponent(requestId)}/activate',
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
        code: 'invalid_management_renewal_payload',
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
        'Management renewal workflow could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }
    final payload = _decode(response);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw _apiException(payload, response.statusCode);
    }
    return payload;
  }

  Map<String, dynamic> _decode(http.Response response) {
    try {
      return decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable Management renewal data.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }
  }

  SpinaApiException _apiException(
    Map<String, dynamic> payload,
    int statusCode,
  ) {
    final detail = stringMap(payload['detail']);
    return SpinaApiException(
      firstNonEmptyString(<Object?>[
            detail['message'],
            payload['message'],
          ]) ??
          apiErrorMessage(payload, statusCode: statusCode),
      statusCode: statusCode,
      code: firstNonEmptyString(<Object?>[
        detail['code'],
        payload['code'],
      ]),
    );
  }
}
