import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/management_no_collection.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class ManagementNoCollectionRepository {
  Future<ManagementNoCollectionLoanState> loadLoanState(
    UserSession session, {
    required String deviceId,
    required String loanId,
  });

  Future<ManagementNoCollectionAdjustmentResult> declare(
    UserSession session, {
    required String deviceId,
    required String loanId,
    required int expectedOperationalVersion,
    required DateTime noCollectionDate,
    required String reason,
  });

  Future<ManagementNoCollectionAdjustmentResult> reverse(
    UserSession session, {
    required String deviceId,
    required String adjustmentId,
    required int expectedOperationalVersion,
    required String reason,
  });
}

class SpinaManagementNoCollectionRepository
    implements ManagementNoCollectionRepository {
  SpinaManagementNoCollectionRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<ManagementNoCollectionLoanState> loadLoanState(
    UserSession session, {
    required String deviceId,
    required String loanId,
  }) async {
    final response = await _send(
      session,
      deviceId: deviceId,
      method: 'GET',
      endpoint: ApiConfig.endpoint(
        '/api/mobile/v1/management/no-collection/loans/$loanId',
      ),
    );
    return ManagementNoCollectionLoanState.fromPayload(
      unwrapSpinaData(response.payload, statusCode: response.statusCode),
    );
  }

  @override
  Future<ManagementNoCollectionAdjustmentResult> declare(
    UserSession session, {
    required String deviceId,
    required String loanId,
    required int expectedOperationalVersion,
    required DateTime noCollectionDate,
    required String reason,
  }) async {
    final response = await _send(
      session,
      deviceId: deviceId,
      method: 'POST',
      endpoint: ApiConfig.endpoint('/api/mobile/v1/management/no-collection'),
      body: <String, Object?>{
        'no_collection_date': _date(noCollectionDate),
        'reason': reason.trim(),
        'loans': <Object?>[
          <String, Object?>{
            'loan_id': loanId,
            'expected_operational_version': expectedOperationalVersion,
          },
        ],
      },
    );
    final data = stringMap(
      unwrapSpinaData(response.payload, statusCode: response.statusCode),
    );
    final rawLoans = data['loans'];
    if (rawLoans is! List || rawLoans.length != 1) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete No Collection result data.',
        code: 'invalid_no_collection_result',
      );
    }
    return ManagementNoCollectionAdjustmentResult.fromPayload(rawLoans.single);
  }

  @override
  Future<ManagementNoCollectionAdjustmentResult> reverse(
    UserSession session, {
    required String deviceId,
    required String adjustmentId,
    required int expectedOperationalVersion,
    required String reason,
  }) async {
    final response = await _send(
      session,
      deviceId: deviceId,
      method: 'POST',
      endpoint: ApiConfig.endpoint(
        '/api/mobile/v1/management/no-collection/$adjustmentId/reverse',
      ),
      body: <String, Object?>{
        'expected_operational_version': expectedOperationalVersion,
        'reason': reason.trim(),
      },
    );
    return ManagementNoCollectionAdjustmentResult.fromPayload(
      unwrapSpinaData(response.payload, statusCode: response.statusCode),
    );
  }

  Future<_ResponsePayload> _send(
    UserSession session, {
    required String deviceId,
    required String method,
    required Uri endpoint,
    Map<String, Object?>? body,
  }) async {
    late final http.Response response;
    final headers = <String, String>{
      'Accept': 'application/json',
      'Authorization': 'Bearer ${session.accessToken}',
      'X-Session-Id': session.accessToken,
      'X-Device-Id': deviceId,
      if (body != null) 'Content-Type': 'application/json',
    };
    try {
      response = switch (method) {
        'GET' => await _client.get(endpoint, headers: headers),
        'POST' => await _client.post(
            endpoint,
            headers: headers,
            body: body == null ? null : jsonEncode(body),
          ),
        _ => throw StateError('Unsupported request method: $method'),
      };
    } on SpinaApiException {
      rethrow;
    } on Exception {
      throw const SpinaApiException(
        'No Collection could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }

    late final Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable No Collection data.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
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

    return _ResponsePayload(response.statusCode, payload);
  }
}

class _ResponsePayload {
  const _ResponsePayload(this.statusCode, this.payload);

  final int statusCode;
  final Map<String, dynamic> payload;
}

String _date(DateTime value) {
  final local = DateTime(value.year, value.month, value.day);
  return '${local.year.toString().padLeft(4, '0')}-'
      '${local.month.toString().padLeft(2, '0')}-'
      '${local.day.toString().padLeft(2, '0')}';
}
