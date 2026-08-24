import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance.dart';
import 'package:http/http.dart' as http;

abstract interface class RemittanceRepository {
  Future<List<RemittanceRecipient>> loadRecipients(
    UserSession session, {
    required String deviceId,
  });

  Future<RemittanceSummary> loadPreview(
    UserSession session, {
    required String deviceId,
    required DateTime collectionDate,
  });

  Future<RemittanceRecord> submit(
    UserSession session, {
    required String deviceId,
    required String recipientUserId,
    required DateTime collectionDate,
    String note,
  });

  Future<List<RemittanceRecord>> loadHistory(
    UserSession session, {
    required String deviceId,
  });

  Future<RemittanceRecord> confirmReceived(
    UserSession session, {
    required String deviceId,
    required String remittanceId,
  });
}

abstract interface class RemittanceRejectionRepository {
  Future<RemittanceRecord> rejectRemittance(
    UserSession session, {
    required String deviceId,
    required String remittanceId,
    required String reason,
  });
}

class SpinaRemittanceRepository
    implements RemittanceRepository, RemittanceRejectionRepository {
  SpinaRemittanceRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<List<RemittanceRecipient>> loadRecipients(
    UserSession session, {
    required String deviceId,
  }) async {
    final data = await _request(
      session,
      deviceId: deviceId,
      method: 'GET',
      uri: ApiConfig.endpoint('/api/mobile/v1/collector/remittances/recipients'),
    );
    if (data is! Iterable) {
      return const <RemittanceRecipient>[];
    }
    return data
        .map(RemittanceRecipient.fromPayload)
        .whereType<RemittanceRecipient>()
        .toList(growable: false);
  }

  @override
  Future<RemittanceSummary> loadPreview(
    UserSession session, {
    required String deviceId,
    required DateTime collectionDate,
  }) async {
    final base = ApiConfig.endpoint('/api/mobile/v1/collector/remittances/preview');
    final uri = base.replace(
      queryParameters: <String, String>{
        'collection_date': _date(collectionDate),
      },
    );
    final data = await _request(
      session,
      deviceId: deviceId,
      method: 'GET',
      uri: uri,
    );
    return RemittanceSummary.fromPayload(data);
  }

  @override
  Future<RemittanceRecord> submit(
    UserSession session, {
    required String deviceId,
    required String recipientUserId,
    required DateTime collectionDate,
    String note = '',
  }) async {
    final data = await _request(
      session,
      deviceId: deviceId,
      method: 'POST',
      uri: ApiConfig.endpoint('/api/mobile/v1/collector/remittances'),
      body: <String, Object?>{
        'recipient_user_id': recipientUserId,
        'collection_date': _date(collectionDate),
        'note': note.trim(),
      },
    );
    return _recordOrThrow(data, 'remittance result');
  }

  @override
  Future<List<RemittanceRecord>> loadHistory(
    UserSession session, {
    required String deviceId,
  }) async {
    final data = await _request(
      session,
      deviceId: deviceId,
      method: 'GET',
      uri: ApiConfig.endpoint('/api/mobile/v1/remittances'),
    );
    if (data is! Iterable) {
      return const <RemittanceRecord>[];
    }
    return data
        .map(RemittanceRecord.fromPayload)
        .whereType<RemittanceRecord>()
        .toList(growable: false);
  }

  @override
  Future<RemittanceRecord> confirmReceived(
    UserSession session, {
    required String deviceId,
    required String remittanceId,
  }) async {
    final data = await _request(
      session,
      deviceId: deviceId,
      method: 'POST',
      uri: ApiConfig.endpoint(
        '/api/mobile/v1/remittances/$remittanceId/receive',
      ),
      body: const <String, Object?>{'review_acknowledged': true},
    );
    return _recordOrThrow(data, 'receipt confirmation');
  }

  @override
  Future<RemittanceRecord> rejectRemittance(
    UserSession session, {
    required String deviceId,
    required String remittanceId,
    required String reason,
  }) async {
    final data = await _request(
      session,
      deviceId: deviceId,
      method: 'POST',
      uri: ApiConfig.endpoint(
        '/api/mobile/v1/remittances/$remittanceId/reject',
      ),
      body: <String, Object?>{
        'review_acknowledged': true,
        'reason': reason.trim(),
      },
    );
    return _recordOrThrow(data, 'rejection confirmation');
  }

  RemittanceRecord _recordOrThrow(Object? data, String label) {
    final record = RemittanceRecord.fromPayload(data);
    if (record == null) {
      throw SpinaApiException(
        'The Gilbic server returned an incomplete $label.',
        code: 'invalid_remittance_response',
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
      response = switch (method) {
        'POST' => await _client.post(
            uri,
            headers: headers,
            body: jsonEncode(body ?? const <String, Object?>{}),
          ),
        _ => await _client.get(uri, headers: headers),
      };
    } on Exception {
      throw const SpinaApiException(
        'The remittance request could not reach the Gilbic server.',
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
        'The Gilbic server returned unreadable remittance data.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }
  }
}

String _date(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}
