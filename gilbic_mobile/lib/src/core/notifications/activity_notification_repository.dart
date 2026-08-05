import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/notifications/activity_notification.dart';
import 'package:http/http.dart' as http;

abstract interface class ActivityNotificationRepository {
  Future<List<ActivityNotification>> load(
    UserSession session, {
    required String deviceId,
  });

  Future<ActivityNotification> markRead(
    UserSession session, {
    required String deviceId,
    required String notificationId,
  });
}

class SpinaActivityNotificationRepository
    implements ActivityNotificationRepository {
  SpinaActivityNotificationRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<List<ActivityNotification>> load(
    UserSession session, {
    required String deviceId,
  }) async {
    final data = await _request(
      session,
      deviceId: deviceId,
      method: 'GET',
      uri: ApiConfig.activityNotificationsEndpoint,
    );
    if (data is! Iterable) {
      return const <ActivityNotification>[];
    }
    return data
        .map(ActivityNotification.fromPayload)
        .whereType<ActivityNotification>()
        .toList(growable: false);
  }

  @override
  Future<ActivityNotification> markRead(
    UserSession session, {
    required String deviceId,
    required String notificationId,
  }) async {
    final data = await _request(
      session,
      deviceId: deviceId,
      method: 'POST',
      uri: ApiConfig.endpoint(
        '/api/mobile/v1/activity-notifications/$notificationId/read',
      ),
    );
    final notification = ActivityNotification.fromPayload(data);
    if (notification == null) {
      throw const SpinaApiException(
        'The SPINA server returned an incomplete payment update.',
        code: 'invalid_activity_notification_response',
      );
    }
    return notification;
  }

  Future<Object?> _request(
    UserSession session, {
    required String deviceId,
    required String method,
    required Uri uri,
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
              body: jsonEncode(const <String, Object?>{}),
            )
          : await _client.get(uri, headers: headers);
    } on Exception {
      throw const SpinaApiException(
        'Payment updates could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }

    Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable payment update data.',
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
