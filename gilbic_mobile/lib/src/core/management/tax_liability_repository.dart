import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/tax_liability.dart';
import 'package:gilbic_mobile/src/core/management/tax_value.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class TaxLiabilityRepository {
  Future<TaxLiabilityOverview> load(
    UserSession session, {
    required String deviceId,
    String accountingStatus = 'all',
    int limit = 100,
    int offset = 0,
  });
  Future<TaxLiabilityItem> prepare(
    UserSession session, {
    required String deviceId,
    required TaxLiabilityItem item,
  });
  Future<TaxLiabilityItem> post(
    UserSession session, {
    required String deviceId,
    required TaxLiabilityItem item,
    required String confirmationToken,
  });
}

class SpinaTaxLiabilityRepository implements TaxLiabilityRepository {
  SpinaTaxLiabilityRepository({http.Client? client})
    : _client = client ?? http.Client();
  final http.Client _client;

  @override
  Future<TaxLiabilityOverview> load(
    UserSession session, {
    required String deviceId,
    String accountingStatus = 'all',
    int limit = 100,
    int offset = 0,
  }) async {
    if (!taxLiabilityFilters.contains(accountingStatus) ||
        limit < 1 ||
        limit > 200 ||
        offset < 0) {
      throw ArgumentError('Invalid tax-liability page coordinates.');
    }
    final endpoint =
        ApiConfig.endpoint(
          '/api/mobile/v1/management/financial-accounting/tax/liabilities',
        ).replace(
          queryParameters: <String, String>{
            'accounting_status': accountingStatus,
            'limit': '$limit',
            'offset': '$offset',
          },
        );
    return TaxLiabilityOverview.fromPayload(
      await _request(
        () => _client.get(endpoint, headers: _headers(session, deviceId)),
      ),
    );
  }

  @override
  Future<TaxLiabilityItem> prepare(
    UserSession session, {
    required String deviceId,
    required TaxLiabilityItem item,
  }) async {
    item.requirePrepareCoordinates();
    return _write(session, deviceId, item, 'prepare', <String, Object>{
      'confirm': true,
    });
  }

  @override
  Future<TaxLiabilityItem> post(
    UserSession session, {
    required String deviceId,
    required TaxLiabilityItem item,
    required String confirmationToken,
  }) async {
    item.requirePostCoordinates();
    if (!taxDigestPattern.hasMatch(confirmationToken)) {
      throw ArgumentError.value(
        confirmationToken,
        'confirmationToken',
        'Expected 64 lowercase hexadecimal characters.',
      );
    }
    return _write(session, deviceId, item, 'post', <String, Object>{
      'confirm': true,
      'confirmation_token': confirmationToken,
      'expected_evidence_digest': item.evidenceDigest,
      'expected_tax_due': item.taxDue,
      'expected_expense_account_code': item.expenseAccountCode!,
      'expected_tax_payable_account_code': item.taxPayableAccountCode!,
      'expected_posting_date': item.recognitionDate,
      'expected_fiscal_period_id': item.fiscalPeriodId!,
    });
  }

  Future<TaxLiabilityItem> _write(
    UserSession session,
    String deviceId,
    TaxLiabilityItem item,
    String action,
    Map<String, Object> body,
  ) async {
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting/tax/liabilities/'
      '${Uri.encodeComponent(item.taxType)}/'
      '${Uri.encodeComponent(item.evidenceId)}/$action',
    );
    final data = await _request(
      () => _client.post(
        endpoint,
        headers: _headers(session, deviceId, jsonBody: true),
        body: jsonEncode(body),
      ),
    );
    return TaxLiabilityItem.fromPayload(stringMap(data['item']));
  }

  Map<String, String> _headers(
    UserSession session,
    String deviceId, {
    bool jsonBody = false,
  }) => <String, String>{
    'Accept': 'application/json',
    if (jsonBody) 'Content-Type': 'application/json',
    'Authorization': 'Bearer ${session.accessToken}',
    'X-Device-Id': deviceId,
  };

  Future<Map<String, dynamic>> _request(
    Future<http.Response> Function() request,
  ) async {
    late final http.Response response;
    try {
      response = await request();
    } on Exception {
      throw const SpinaApiException(
        'The protected tax-liability server could not be reached.',
        code: 'network_unavailable',
      );
    }
    late final Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable protected tax-liability data.',
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
    return stringMap(unwrapSpinaData(payload, statusCode: response.statusCode));
  }
}
