import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/collection_void.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class ManagementCollectionVoidRepository {
  Future<ManagementCollectionVoidCandidate> findByReceipt(
    UserSession session, {
    required String deviceId,
    required String receiptNumber,
  });

  Future<ManagementCollectionVoidResult> voidCollection(
    UserSession session, {
    required String deviceId,
    required String transactionId,
    required String reason,
  });
}

class SpinaManagementCollectionVoidRepository
    implements ManagementCollectionVoidRepository {
  SpinaManagementCollectionVoidRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<ManagementCollectionVoidCandidate> findByReceipt(
    UserSession session, {
    required String deviceId,
    required String receiptNumber,
  }) async {
    final normalized = receiptNumber.trim().toUpperCase();
    if (normalized.isEmpty) {
      throw const SpinaApiException(
        'Enter a receipt number.',
        code: 'missing_receipt_number',
      );
    }
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/management/collections/by-receipt/'
      '${Uri.encodeComponent(normalized)}',
    );
    late final http.Response response;
    try {
      response = await _client.get(
        endpoint,
        headers: _headers(session, deviceId: deviceId),
      );
    } on Exception {
      throw const SpinaApiException(
        'The receipt search could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }
    final payload = _decode(response);
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return ManagementCollectionVoidCandidate.fromPayload(
        unwrapSpinaData(payload, statusCode: response.statusCode),
      );
    }
    throw _error(response, payload);
  }

  @override
  Future<ManagementCollectionVoidResult> voidCollection(
    UserSession session, {
    required String deviceId,
    required String transactionId,
    required String reason,
  }) async {
    final normalizedReason = reason.trim();
    if (normalizedReason.length < 3) {
      throw const SpinaApiException(
        'Enter a clear reason for voiding the collection.',
        code: 'missing_void_reason',
      );
    }
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/management/collections/'
      '${Uri.encodeComponent(transactionId)}/void',
    );
    late final http.Response response;
    try {
      response = await _client.post(
        endpoint,
        headers: <String, String>{
          ..._headers(session, deviceId: deviceId),
          'Content-Type': 'application/json',
        },
        body: jsonEncode(<String, Object?>{'reason': normalizedReason}),
      );
    } on Exception {
      throw const SpinaApiException(
        'The collection void could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }
    final payload = _decode(response);
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return ManagementCollectionVoidResult.fromPayload(
        unwrapSpinaData(payload, statusCode: response.statusCode),
      );
    }
    throw _error(response, payload);
  }

  Map<String, String> _headers(
    UserSession session, {
    required String deviceId,
  }) {
    return <String, String>{
      'Accept': 'application/json',
      'Authorization': 'Bearer ${session.accessToken}',
      'X-Session-Id': session.accessToken,
      'X-Device-Id': deviceId,
    };
  }

  Map<String, dynamic> _decode(http.Response response) {
    try {
      return decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable collection data.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }
  }

  SpinaApiException _error(
    http.Response response,
    Map<String, dynamic> payload,
  ) {
    final detail = payload['detail'];
    final detailMap = stringMap(detail);
    return SpinaApiException(
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
