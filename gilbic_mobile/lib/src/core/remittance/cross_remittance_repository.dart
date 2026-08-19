import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/remittance/cross_remittance.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance.dart';
import 'package:http/http.dart' as http;

abstract interface class CrossRemittanceRepository {
  Future<List<CrossCollectionStatus>> loadCollectionHistory(
    UserSession session, {
    required String deviceId,
    DateTime? collectionDate,
  });

  Future<List<CrossRemittanceTarget>> loadTargets(
    UserSession session, {
    required String deviceId,
    required DateTime collectionDate,
  });

  Future<RemittanceSummary> loadPreview(
    UserSession session, {
    required String deviceId,
    required String recipientUserId,
    CrossRemittanceRecipientCapacity recipientCapacity =
        CrossRemittanceRecipientCapacity.assignedCollector,
    required DateTime collectionDate,
  });

  Future<RemittanceRecord> submit(
    UserSession session, {
    required String deviceId,
    required String recipientUserId,
    CrossRemittanceRecipientCapacity recipientCapacity =
        CrossRemittanceRecipientCapacity.assignedCollector,
    required DateTime collectionDate,
    String note,
  });
}

class SpinaCrossRemittanceRepository implements CrossRemittanceRepository {
  SpinaCrossRemittanceRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<List<CrossCollectionStatus>> loadCollectionHistory(
    UserSession session, {
    required String deviceId,
    DateTime? collectionDate,
  }) async {
    final base = ApiConfig.endpoint(
      '/api/mobile/v1/collector/cross-remittances/history',
    );
    final data = await _request(
      session,
      deviceId: deviceId,
      method: 'GET',
      uri: base.replace(
        queryParameters: <String, String>{
          'limit': '500',
          if (collectionDate != null) 'collection_date': _date(collectionDate),
        },
      ),
    );
    if (data is! Iterable) {
      return const <CrossCollectionStatus>[];
    }
    return data
        .map(CrossCollectionStatus.fromPayload)
        .whereType<CrossCollectionStatus>()
        .toList(growable: false);
  }

  @override
  Future<List<CrossRemittanceTarget>> loadTargets(
    UserSession session, {
    required String deviceId,
    required DateTime collectionDate,
  }) async {
    final base = ApiConfig.endpoint(
      '/api/mobile/v1/collector/cross-remittances/targets',
    );
    final data = await _request(
      session,
      deviceId: deviceId,
      method: 'GET',
      uri: base.replace(
        queryParameters: <String, String>{
          'collection_date': _date(collectionDate),
        },
      ),
    );
    if (data is! Iterable) {
      return const <CrossRemittanceTarget>[];
    }
    return data
        .map(CrossRemittanceTarget.fromPayload)
        .whereType<CrossRemittanceTarget>()
        .toList(growable: false);
  }

  @override
  Future<RemittanceSummary> loadPreview(
    UserSession session, {
    required String deviceId,
    required String recipientUserId,
    CrossRemittanceRecipientCapacity recipientCapacity =
        CrossRemittanceRecipientCapacity.assignedCollector,
    required DateTime collectionDate,
  }) async {
    final base = ApiConfig.endpoint(
      '/api/mobile/v1/collector/cross-remittances/preview',
    );
    final data = await _request(
      session,
      deviceId: deviceId,
      method: 'GET',
      uri: base.replace(
        queryParameters: <String, String>{
          'recipient_user_id': recipientUserId,
          'recipient_capacity': recipientCapacity.apiValue,
          'collection_date': _date(collectionDate),
        },
      ),
    );
    return RemittanceSummary.fromPayload(data);
  }

  @override
  Future<RemittanceRecord> submit(
    UserSession session, {
    required String deviceId,
    required String recipientUserId,
    CrossRemittanceRecipientCapacity recipientCapacity =
        CrossRemittanceRecipientCapacity.assignedCollector,
    required DateTime collectionDate,
    String note = '',
  }) async {
    final data = await _request(
      session,
      deviceId: deviceId,
      method: 'POST',
      uri: ApiConfig.endpoint(
        '/api/mobile/v1/collector/cross-remittances',
      ),
      body: <String, Object?>{
        'recipient_user_id': recipientUserId,
        'recipient_capacity': recipientCapacity.apiValue,
        'collection_date': _date(collectionDate),
        'note': note.trim(),
      },
    );
    final record = RemittanceRecord.fromPayload(data);
    if (record == null) {
      throw const SpinaApiException(
        'The SPINA server returned an incomplete other-area remittance.',
        code: 'invalid_cross_remittance_response',
      );
    }
    return record;
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
        'The other-area remittance could not reach SPINA.',
        code: 'network_unavailable',
      );
    }

    Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable other-area remittance data.',
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

String _date(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}
