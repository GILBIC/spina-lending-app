import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow.dart';
import 'package:http/http.dart' as http;

abstract interface class CollectorRenewalWorkflowRepository {
  Future<List<CollectorRenewalRequest>> list(
    UserSession session, {
    required String deviceId,
  });

  Future<CollectorRenewalRequest> recommend(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required String recommendation,
    required String reasonCode,
    required String comment,
  });

  Future<CollectorRenewalRequest> confirmCashReceived(
    UserSession session, {
    required String deviceId,
    required String requestId,
  });

  Future<CollectorRenewalRequest> confirmCashGiven(
    UserSession session, {
    required String deviceId,
    required String requestId,
  });

  Future<String> uploadHandoverPhoto(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required RenewalHandoverPhotoDraft draft,
  });
}

class SpinaCollectorRenewalWorkflowRepository
    implements CollectorRenewalWorkflowRepository {
  SpinaCollectorRenewalWorkflowRepository({http.Client? client})
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
      uri: ApiConfig.collectorRenewalsEndpoint,
    );
    final data = stringMap(unwrapSpinaData(payload));
    final raw = data['requests'];
    if (raw is! List) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete renewal requests.',
        code: 'invalid_collector_renewal_payload',
      );
    }
    return raw
        .map((item) => CollectorRenewalRequest.fromPayload(stringMap(item)))
        .toList(growable: false);
  }

  @override
  Future<CollectorRenewalRequest> recommend(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required String recommendation,
    required String reasonCode,
    required String comment,
  }) async {
    return _requestItem(
      session,
      deviceId: deviceId,
      uri: ApiConfig.collectorRenewalActionEndpoint(
        requestId,
        'recommendation',
      ),
      body: <String, Object?>{
        'recommendation': recommendation,
        'reason_code': reasonCode,
        'comment': comment,
      },
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
      uri: ApiConfig.collectorRenewalActionEndpoint(requestId, 'cash-received'),
      body: const <String, Object?>{},
    );
  }

  @override
  Future<CollectorRenewalRequest> confirmCashGiven(
    UserSession session, {
    required String deviceId,
    required String requestId,
  }) {
    return _requestItem(
      session,
      deviceId: deviceId,
      uri: ApiConfig.collectorRenewalActionEndpoint(requestId, 'cash-given'),
      body: const <String, Object?>{},
    );
  }

  @override
  Future<String> uploadHandoverPhoto(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required RenewalHandoverPhotoDraft draft,
  }) async {
    final validation = draft.validate();
    if (validation != null) {
      throw SpinaApiException(validation, code: 'renewal_proof_invalid');
    }
    late final http.Response response;
    try {
      response = await _client.post(
        ApiConfig.collectorRenewalActionEndpoint(requestId, 'handover-photo'),
        headers: <String, String>{
          'Accept': 'application/json',
          'Authorization': 'Bearer ${session.accessToken}',
          'X-Session-Id': session.accessToken,
          'X-Device-Id': deviceId,
          'X-File-Name': draft.filename,
          'Content-Type': draft.contentType,
        },
        body: draft.bytes,
      );
    } on Exception {
      throw const SpinaApiException(
        'The renewal handover photo could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }
    final payload = _decode(response);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw _apiException(payload, response.statusCode);
    }
    final data = stringMap(unwrapSpinaData(payload, statusCode: response.statusCode));
    return firstNonEmptyString(<Object?>[data['status']]) ?? 'under_review';
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
        'The SPINA server returned incomplete renewal data.',
        code: 'invalid_collector_renewal_payload',
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
      throw _apiException(payload, response.statusCode);
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
