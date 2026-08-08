import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/opening_balance_workbook.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class OpeningBalanceWorkbookRepository {
  Future<OpeningBalanceWorkbookData> load(
    UserSession session, {
    required String deviceId,
  });

  Future<OpeningBalanceWorkbookData> create(
    UserSession session, {
    required String deviceId,
    required DateTime cutoverDate,
  });

  Future<OpeningBalanceWorkbookData> updateLine(
    UserSession session, {
    required String deviceId,
    required String workbookId,
    required String accountCode,
    required double? debit,
    required double? credit,
    required String verificationStatus,
    required String? evidenceNote,
  });

  Future<OpeningBalanceWorkbookData> updatePolicy(
    UserSession session, {
    required String deviceId,
    required String workbookId,
    required bool confirmed,
    required String? policyNote,
  });

  Future<OpeningBalanceWorkbookData> changeStatus(
    UserSession session, {
    required String deviceId,
    required String workbookId,
    required String status,
  });
}

class SpinaOpeningBalanceWorkbookRepository
    implements OpeningBalanceWorkbookRepository {
  SpinaOpeningBalanceWorkbookRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<OpeningBalanceWorkbookData> load(
    UserSession session, {
    required String deviceId,
  }) async {
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting/opening-balance-workbook',
    );
    return _parse(
      await _request(
        () => _client.get(endpoint, headers: _headers(session, deviceId)),
      ),
    );
  }

  @override
  Future<OpeningBalanceWorkbookData> create(
    UserSession session, {
    required String deviceId,
    required DateTime cutoverDate,
  }) async {
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting/opening-balance-workbook',
    );
    return _parse(
      await _request(
        () => _client.post(
          endpoint,
          headers: _headers(session, deviceId, jsonBody: true),
          body: jsonEncode(<String, Object>{
            'cutover_date': _dateText(cutoverDate),
          }),
        ),
      ),
    );
  }

  @override
  Future<OpeningBalanceWorkbookData> updateLine(
    UserSession session, {
    required String deviceId,
    required String workbookId,
    required String accountCode,
    required double? debit,
    required double? credit,
    required String verificationStatus,
    required String? evidenceNote,
  }) async {
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting/opening-balance-workbook/$workbookId/lines/$accountCode',
    );
    return _parse(
      await _request(
        () => _client.put(
          endpoint,
          headers: _headers(session, deviceId, jsonBody: true),
          body: jsonEncode(<String, Object?>{
            'debit': debit,
            'credit': credit,
            'verification_status': verificationStatus,
            'evidence_note': evidenceNote,
          }),
        ),
      ),
    );
  }

  @override
  Future<OpeningBalanceWorkbookData> updatePolicy(
    UserSession session, {
    required String deviceId,
    required String workbookId,
    required bool confirmed,
    required String? policyNote,
  }) async {
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting/opening-balance-workbook/$workbookId/policy',
    );
    return _parse(
      await _request(
        () => _client.put(
          endpoint,
          headers: _headers(session, deviceId, jsonBody: true),
          body: jsonEncode(<String, Object?>{
            'confirmed': confirmed,
            'policy_note': policyNote,
          }),
        ),
      ),
    );
  }

  @override
  Future<OpeningBalanceWorkbookData> changeStatus(
    UserSession session, {
    required String deviceId,
    required String workbookId,
    required String status,
  }) async {
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting/opening-balance-workbook/$workbookId/status',
    );
    return _parse(
      await _request(
        () => _client.post(
          endpoint,
          headers: _headers(session, deviceId, jsonBody: true),
          body: jsonEncode(<String, Object>{'status': status}),
        ),
      ),
    );
  }

  OpeningBalanceWorkbookData _parse(_WorkbookResponse response) {
    return OpeningBalanceWorkbookData.fromPayload(
      stringMap(
        unwrapSpinaData(response.data, statusCode: response.statusCode),
      ),
    );
  }

  Map<String, String> _headers(
    UserSession session,
    String deviceId, {
    bool jsonBody = false,
  }) {
    return <String, String>{
      'Accept': 'application/json',
      if (jsonBody) 'Content-Type': 'application/json',
      'Authorization': 'Bearer ${session.accessToken}',
      'X-Session-Id': session.accessToken,
      'X-Device-Id': deviceId,
    };
  }

  Future<_WorkbookResponse> _request(
    Future<http.Response> Function() request,
  ) async {
    late final http.Response response;
    try {
      response = await request();
    } on Exception {
      throw const SpinaApiException(
        'Opening Balance Workbook could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }

    late final Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable opening-balance workbook data.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return _WorkbookResponse(response.statusCode, payload);
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

class _WorkbookResponse {
  const _WorkbookResponse(this.statusCode, this.data);

  final int statusCode;
  final Map<String, dynamic> data;
}

String _dateText(DateTime value) {
  final month = value.month.toString().padLeft(2, '0');
  final day = value.day.toString().padLeft(2, '0');
  return '${value.year}-$month-$day';
}
