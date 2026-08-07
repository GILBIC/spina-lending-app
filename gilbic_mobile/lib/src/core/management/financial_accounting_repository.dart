import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/financial_accounting.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class FinancialAccountingRepository {
  Future<FinancialAccountingOverview> loadOverview(
    UserSession session, {
    required String deviceId,
  });

  Future<AccountingFiscalPeriod> createFiscalPeriod(
    UserSession session, {
    required String deviceId,
    required String label,
    required DateTime startDate,
    required DateTime endDate,
  });

  Future<AccountingFiscalPeriod> changeFiscalPeriodStatus(
    UserSession session, {
    required String deviceId,
    required String periodId,
    required String status,
    bool confirmClose = false,
  });
}

class SpinaFinancialAccountingRepository
    implements FinancialAccountingRepository {
  SpinaFinancialAccountingRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<FinancialAccountingOverview> loadOverview(
    UserSession session, {
    required String deviceId,
  }) async {
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting',
    );
    final payload = await _request(
      () => _client.get(endpoint, headers: _headers(session, deviceId)),
    );
    return FinancialAccountingOverview.fromPayload(
      stringMap(unwrapSpinaData(payload.data, statusCode: payload.statusCode)),
    );
  }

  @override
  Future<AccountingFiscalPeriod> createFiscalPeriod(
    UserSession session, {
    required String deviceId,
    required String label,
    required DateTime startDate,
    required DateTime endDate,
  }) async {
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting/fiscal-periods',
    );
    final payload = await _request(
      () => _client.post(
        endpoint,
        headers: _headers(session, deviceId, jsonBody: true),
        body: jsonEncode(<String, Object>{
          'label': label,
          'start_date': _dateText(startDate),
          'end_date': _dateText(endDate),
        }),
      ),
    );
    final data = stringMap(
      unwrapSpinaData(payload.data, statusCode: payload.statusCode),
    );
    return AccountingFiscalPeriod.fromPayload(stringMap(data['period']));
  }

  @override
  Future<AccountingFiscalPeriod> changeFiscalPeriodStatus(
    UserSession session, {
    required String deviceId,
    required String periodId,
    required String status,
    bool confirmClose = false,
  }) async {
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting/fiscal-periods/$periodId/status',
    );
    final payload = await _request(
      () => _client.post(
        endpoint,
        headers: _headers(session, deviceId, jsonBody: true),
        body: jsonEncode(<String, Object>{
          'status': status,
          'confirm_close': confirmClose,
        }),
      ),
    );
    final data = stringMap(
      unwrapSpinaData(payload.data, statusCode: payload.statusCode),
    );
    return AccountingFiscalPeriod.fromPayload(stringMap(data['period']));
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

  Future<_AccountingResponse> _request(
    Future<http.Response> Function() request,
  ) async {
    late final http.Response response;
    try {
      response = await request();
    } on Exception {
      throw const SpinaApiException(
        'Financial Accounting could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }

    late final Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable Financial Accounting data.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return _AccountingResponse(response.statusCode, payload);
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

class _AccountingResponse {
  const _AccountingResponse(this.statusCode, this.data);

  final int statusCode;
  final Map<String, dynamic> data;
}

String _dateText(DateTime value) {
  final month = value.month.toString().padLeft(2, '0');
  final day = value.day.toString().padLeft(2, '0');
  return '${value.year}-$month-$day';
}
