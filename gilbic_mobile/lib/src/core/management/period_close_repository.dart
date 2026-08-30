import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/period_close.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class PeriodCloseRepository {
  Future<PeriodCloseOverview> load(
    UserSession session, {
    required String deviceId,
    String status = 'all',
  });

  Future<PeriodCloseItem> prepare(
    UserSession session, {
    required String deviceId,
    required String fiscalPeriodId,
  });

  Future<PeriodCloseItem> post(
    UserSession session, {
    required String deviceId,
    required PeriodCloseItem item,
    required String confirmationToken,
  });
}

class SpinaPeriodCloseRepository implements PeriodCloseRepository {
  SpinaPeriodCloseRepository({http.Client? client})
    : _client = client ?? http.Client();

  final http.Client _client;

  static const _statuses = <String>{
    'all',
    'ready_for_review',
    'ready_to_prepare',
    'prepared',
    'closed',
    'blocked',
  };
  static final _tokenPattern = RegExp(r'^[0-9a-f]{64}$');

  @override
  Future<PeriodCloseOverview> load(
    UserSession session, {
    required String deviceId,
    String status = 'all',
  }) async {
    if (!_statuses.contains(status)) {
      throw ArgumentError.value(status, 'status', 'Unsupported close status.');
    }
    final endpoint =
        ApiConfig.endpoint(
          '/api/mobile/v1/management/financial-accounting/period-close',
        ).replace(
          queryParameters: status == 'all'
              ? const <String, String>{}
              : <String, String>{'close_status': status},
        );
    final data = await _request(
      () => _client.get(endpoint, headers: _headers(session, deviceId)),
    );
    try {
      return PeriodCloseOverview.fromPayload(data);
    } on SpinaApiException {
      rethrow;
    } on Object {
      throw const SpinaApiException(
        'The SPINA server returned invalid period-close data.',
        code: 'invalid_period_close_payload',
      );
    }
  }

  @override
  Future<PeriodCloseItem> prepare(
    UserSession session, {
    required String deviceId,
    required String fiscalPeriodId,
  }) async {
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting/period-close/'
      '${Uri.encodeComponent(fiscalPeriodId)}/prepare',
    );
    final data = await _request(
      () => _client.post(
        endpoint,
        headers: _headers(session, deviceId, jsonBody: true),
        body: jsonEncode(const <String, Object>{'confirm': true}),
      ),
    );
    return _item(data);
  }

  @override
  Future<PeriodCloseItem> post(
    UserSession session, {
    required String deviceId,
    required PeriodCloseItem item,
    required String confirmationToken,
  }) async {
    item.requirePostCoordinates();
    if (!_tokenPattern.hasMatch(confirmationToken)) {
      throw ArgumentError.value(
        confirmationToken,
        'confirmationToken',
        'Expected 64 lowercase hexadecimal characters.',
      );
    }
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting/period-close/'
      '${Uri.encodeComponent(item.fiscalPeriodId)}/post',
    );
    final data = await _request(
      () => _client.post(
        endpoint,
        headers: _headers(session, deviceId, jsonBody: true),
        body: jsonEncode(<String, Object>{
          'confirm': true,
          'confirmation_token': confirmationToken,
          'expected_close_digest': item.closeDigest!,
          'expected_net_income': item.netIncome!,
          'expected_retained_earnings_account_code': '3100',
          'expected_period_end_date': periodCloseDateText(item.endDate),
        }),
      ),
    );
    return _item(data);
  }

  PeriodCloseItem _item(Map<String, dynamic> data) {
    try {
      return PeriodCloseItem.fromPayload(stringMap(data['item']));
    } on SpinaApiException {
      rethrow;
    } on Object {
      throw const SpinaApiException(
        'The SPINA server returned invalid period-close evidence.',
        code: 'invalid_period_close_payload',
      );
    }
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
      'X-Device-Id': deviceId,
    };
  }

  Future<Map<String, dynamic>> _request(
    Future<http.Response> Function() request,
  ) async {
    late final http.Response response;
    try {
      response = await request();
    } on Exception {
      throw const SpinaApiException(
        'The protected period-close server could not be reached.',
        code: 'network_unavailable',
      );
    }

    late final Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable period-close data.',
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
