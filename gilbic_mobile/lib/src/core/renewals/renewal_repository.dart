import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/renewals/renewal_request.dart';
import 'package:http/http.dart' as http;

abstract interface class ClientRenewalRepository {
  Future<ClientRenewalPortal> loadPortal(
    UserSession session, {
    required String deviceId,
  });

  Future<RenewalRequestItem> submit(
    UserSession session, {
    required String deviceId,
    required String loanId,
    required double requestedAmount,
    required String message,
  });

  Future<RenewalRequestItem> cancel(
    UserSession session, {
    required String deviceId,
    required String requestId,
  });
}

abstract interface class ManagementRenewalRepository {
  Future<List<RenewalRequestItem>> loadRequests(
    UserSession session, {
    required String deviceId,
    required String status,
  });

  Future<RenewalRequestItem> review(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required String decision,
    required String reviewNote,
  });
}

class SpinaRenewalRepository
    implements ClientRenewalRepository, ManagementRenewalRepository {
  SpinaRenewalRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<ClientRenewalPortal> loadPortal(
    UserSession session, {
    required String deviceId,
  }) async {
    final payload = await _send(
      session,
      deviceId: deviceId,
      method: 'GET',
      path: '/api/mobile/v1/client/renewals',
    );
    return ClientRenewalPortal.fromPayload(stringMap(payload));
  }

  @override
  Future<RenewalRequestItem> submit(
    UserSession session, {
    required String deviceId,
    required String loanId,
    required double requestedAmount,
    required String message,
  }) async {
    final payload = await _send(
      session,
      deviceId: deviceId,
      method: 'POST',
      path: '/api/mobile/v1/client/renewals',
      body: <String, Object?>{
        'loan_id': loanId,
        'requested_amount': requestedAmount.toStringAsFixed(2),
        'message': message,
      },
    );
    return RenewalRequestItem.fromPayload(
      stringMap(stringMap(payload)['request']),
    );
  }

  @override
  Future<RenewalRequestItem> cancel(
    UserSession session, {
    required String deviceId,
    required String requestId,
  }) async {
    final payload = await _send(
      session,
      deviceId: deviceId,
      method: 'POST',
      path: '/api/mobile/v1/client/renewals/$requestId/cancel',
    );
    return RenewalRequestItem.fromPayload(
      stringMap(stringMap(payload)['request']),
    );
  }

  @override
  Future<List<RenewalRequestItem>> loadRequests(
    UserSession session, {
    required String deviceId,
    required String status,
  }) async {
    final payload = await _send(
      session,
      deviceId: deviceId,
      method: 'GET',
      path: '/api/mobile/v1/management/renewals?status=$status',
    );
    final raw = stringMap(payload)['requests'];
    if (raw is! List) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete renewal requests.',
        code: 'invalid_renewal_payload',
      );
    }
    return raw
        .map((item) => RenewalRequestItem.fromPayload(stringMap(item)))
        .toList(growable: false);
  }

  @override
  Future<RenewalRequestItem> review(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required String decision,
    required String reviewNote,
  }) async {
    final payload = await _send(
      session,
      deviceId: deviceId,
      method: 'POST',
      path: '/api/mobile/v1/management/renewals/$requestId/review',
      body: <String, Object?>{
        'decision': decision,
        'review_note': reviewNote,
      },
    );
    return RenewalRequestItem.fromPayload(
      stringMap(stringMap(payload)['request']),
    );
  }

  Future<Object?> _send(
    UserSession session, {
    required String deviceId,
    required String method,
    required String path,
    Map<String, Object?>? body,
  }) async {
    final endpoint = ApiConfig.endpoint(path);
    final headers = <String, String>{
      'Accept': 'application/json',
      'Authorization': 'Bearer ${session.accessToken}',
      'X-Session-Id': session.accessToken,
      'X-Device-Id': deviceId,
      if (body != null) 'Content-Type': 'application/json',
    };
    late final http.Response response;
    try {
      response = method == 'GET'
          ? await _client.get(endpoint, headers: headers)
          : await _client.post(
              endpoint,
              headers: headers,
              body: body == null ? null : jsonEncode(body),
            );
    } on Exception {
      throw const SpinaApiException(
        'Renewal could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }

    late final Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable renewal data.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return unwrapSpinaData(payload, statusCode: response.statusCode);
    }

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
}
