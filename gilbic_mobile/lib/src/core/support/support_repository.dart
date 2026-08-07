import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/support/support_request.dart';
import 'package:http/http.dart' as http;

abstract interface class ClientSupportRepository {
  Future<ClientSupportPortal> loadPortal(
    UserSession session, {
    required String deviceId,
  });

  Future<SupportRequestItem> submit(
    UserSession session, {
    required String deviceId,
    required String category,
    required String subject,
    required String message,
    required String referenceText,
  });

  Future<SupportRequestItem> cancel(
    UserSession session, {
    required String deviceId,
    required String requestId,
  });
}

abstract interface class ManagementSupportRepository {
  Future<List<SupportRequestItem>> loadRequests(
    UserSession session, {
    required String deviceId,
    required String status,
  });

  Future<SupportRequestItem> review(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required String action,
    required String response,
  });
}

class SpinaSupportRepository
    implements ClientSupportRepository, ManagementSupportRepository {
  SpinaSupportRepository({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<ClientSupportPortal> loadPortal(
    UserSession session, {
    required String deviceId,
  }) async {
    final payload = await _send(
      session,
      deviceId: deviceId,
      method: 'GET',
      path: '/api/mobile/v1/client/support',
    );
    return ClientSupportPortal.fromPayload(stringMap(payload));
  }

  @override
  Future<SupportRequestItem> submit(
    UserSession session, {
    required String deviceId,
    required String category,
    required String subject,
    required String message,
    required String referenceText,
  }) async {
    final payload = await _send(
      session,
      deviceId: deviceId,
      method: 'POST',
      path: '/api/mobile/v1/client/support',
      body: <String, Object?>{
        'category': category,
        'subject': subject,
        'message': message,
        'reference_text': referenceText,
      },
    );
    return SupportRequestItem.fromPayload(
      stringMap(stringMap(payload)['request']),
    );
  }

  @override
  Future<SupportRequestItem> cancel(
    UserSession session, {
    required String deviceId,
    required String requestId,
  }) async {
    final payload = await _send(
      session,
      deviceId: deviceId,
      method: 'POST',
      path: '/api/mobile/v1/client/support/$requestId/cancel',
    );
    return SupportRequestItem.fromPayload(
      stringMap(stringMap(payload)['request']),
    );
  }

  @override
  Future<List<SupportRequestItem>> loadRequests(
    UserSession session, {
    required String deviceId,
    required String status,
  }) async {
    final payload = await _send(
      session,
      deviceId: deviceId,
      method: 'GET',
      path: '/api/mobile/v1/management/support?status=$status',
    );
    final raw = stringMap(payload)['requests'];
    if (raw is! List) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete support requests.',
        code: 'invalid_support_payload',
      );
    }
    return raw
        .map((item) => SupportRequestItem.fromPayload(stringMap(item)))
        .toList(growable: false);
  }

  @override
  Future<SupportRequestItem> review(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required String action,
    required String response,
  }) async {
    final payload = await _send(
      session,
      deviceId: deviceId,
      method: 'POST',
      path: '/api/mobile/v1/management/support/$requestId/review',
      body: <String, Object?>{
        'action': action,
        'response': response,
      },
    );
    return SupportRequestItem.fromPayload(
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
        'Support could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }

    late final Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable support data.',
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
