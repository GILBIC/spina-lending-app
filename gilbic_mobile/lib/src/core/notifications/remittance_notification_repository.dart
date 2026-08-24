import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification.dart';
import 'package:http/http.dart' as http;

abstract interface class RemittanceNotificationRepository {
  Future<List<RemittanceNotification>> loadNotifications(
    UserSession session, {
    required String deviceId,
  });

  Future<RemittanceNotification> markRead(
    UserSession session, {
    required String deviceId,
    required String notificationId,
  });

  Future<RemittanceAcceptanceResult> acceptRemittance(
    UserSession session, {
    required String deviceId,
    required String notificationId,
  });
}

class SpinaRemittanceNotificationRepository
    implements RemittanceNotificationRepository {
  SpinaRemittanceNotificationRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<List<RemittanceNotification>> loadNotifications(
    UserSession session, {
    required String deviceId,
  }) async {
    final data = await _request(
      session,
      deviceId: deviceId,
      method: 'GET',
      uri: ApiConfig.endpoint('/api/mobile/v1/notifications'),
    );
    if (data is! Iterable) {
      return const <RemittanceNotification>[];
    }
    return data
        .map(RemittanceNotification.fromPayload)
        .whereType<RemittanceNotification>()
        .toList(growable: false);
  }

  @override
  Future<RemittanceNotification> markRead(
    UserSession session, {
    required String deviceId,
    required String notificationId,
  }) async {
    final data = await _request(
      session,
      deviceId: deviceId,
      method: 'POST',
      uri: ApiConfig.endpoint(
        '/api/mobile/v1/notifications/$notificationId/read',
      ),
    );
    final notification = RemittanceNotification.fromPayload(data);
    if (notification == null) {
      throw const SpinaApiException(
        'The Gilbic server returned an incomplete notification.',
        code: 'invalid_notification_response',
      );
    }
    return notification;
  }

  @override
  Future<RemittanceAcceptanceResult> acceptRemittance(
    UserSession session, {
    required String deviceId,
    required String notificationId,
  }) async {
    final data = await _request(
      session,
      deviceId: deviceId,
      method: 'POST',
      uri: ApiConfig.endpoint(
        '/api/mobile/v1/notifications/$notificationId/accept-remittance',
      ),
      body: const <String, Object?>{'review_acknowledged': true},
    );
    return RemittanceAcceptanceResult.fromPayload(data);
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
      'X-Session-Id': session.accessToken,
      'X-Device-Id': deviceId,
    };
    late final http.Response response;
    try {
      response = method == 'POST'
          ? await _client.post(
              uri,
              headers: headers,
              body: jsonEncode(body ?? const <String, Object?>{}),
            )
          : await _client.get(uri, headers: headers);
    } on Exception {
      throw const SpinaApiException(
        'The notification request could not reach the Gilbic server.',
        code: 'network_unavailable',
      );
    }

    final payload = _decodeResponse(response);
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

  Map<String, dynamic> _decodeResponse(http.Response response) {
    try {
      return decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The Gilbic server returned unreadable notification data.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }
  }
}
