import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/initial_capital_funding.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class InitialCapitalFundingRepository {
  Future<InitialCapitalFundingOverview> load(
    UserSession session, {
    required String deviceId,
    int limit = 100,
    int offset = 0,
  });

  Future<InitialCapitalFundingItem> recordEvidence(
    UserSession session, {
    required String deviceId,
    required InitialCapitalEvidenceDraft draft,
    required String idempotencyKey,
  });

  Future<InitialCapitalFundingItem> prepare(
    UserSession session, {
    required String deviceId,
    required InitialCapitalFundingItem item,
  });

  Future<InitialCapitalFundingItem> post(
    UserSession session, {
    required String deviceId,
    required InitialCapitalFundingItem item,
    required String confirmationToken,
  });
}

class SpinaInitialCapitalFundingRepository
    implements InitialCapitalFundingRepository {
  SpinaInitialCapitalFundingRepository({http.Client? client})
    : _client = client ?? http.Client();

  final http.Client _client;
  static final _uuidPattern = RegExp(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$',
  );
  static final _tokenPattern = RegExp(r'^[0-9a-f]{64}$');

  @override
  Future<InitialCapitalFundingOverview> load(
    UserSession session, {
    required String deviceId,
    int limit = 100,
    int offset = 0,
  }) async {
    if (limit < 1 || limit > 200 || offset < 0) {
      throw ArgumentError('Invalid initial-capital queue page coordinates.');
    }
    final endpoint =
        ApiConfig.endpoint(
          '/api/mobile/v1/management/financial-accounting/initial-capital-funding',
        ).replace(
          queryParameters: <String, String>{
            'limit': '$limit',
            'offset': '$offset',
          },
        );
    final data = await _request(
      () => _client.get(endpoint, headers: _headers(session, deviceId)),
    );
    return InitialCapitalFundingOverview.fromPayload(data);
  }

  @override
  Future<InitialCapitalFundingItem> recordEvidence(
    UserSession session, {
    required String deviceId,
    required InitialCapitalEvidenceDraft draft,
    required String idempotencyKey,
  }) async {
    draft.validate();
    if (!_uuidPattern.hasMatch(idempotencyKey)) {
      throw ArgumentError.value(
        idempotencyKey,
        'idempotencyKey',
        'Expected an RFC 4122 UUID.',
      );
    }
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting/initial-capital-funding/evidence',
    );
    final data = await _request(
      () => _client.post(
        endpoint,
        headers: _headers(session, deviceId, jsonBody: true),
        body: jsonEncode(draft.toPayload(idempotencyKey.toLowerCase())),
      ),
    );
    return _item(data);
  }

  @override
  Future<InitialCapitalFundingItem> prepare(
    UserSession session, {
    required String deviceId,
    required InitialCapitalFundingItem item,
  }) async {
    item.requirePrepareCoordinates();
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting/initial-capital-funding/'
      '${Uri.encodeComponent(item.evidenceId)}/prepare',
    );
    final data = await _request(
      () => _client.post(
        endpoint,
        headers: _headers(session, deviceId, jsonBody: true),
        body: jsonEncode(<String, Object>{'confirm': true}),
      ),
    );
    return _item(data);
  }

  @override
  Future<InitialCapitalFundingItem> post(
    UserSession session, {
    required String deviceId,
    required InitialCapitalFundingItem item,
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
      '/api/mobile/v1/management/financial-accounting/initial-capital-funding/'
      '${Uri.encodeComponent(item.evidenceId)}/post',
    );
    final data = await _request(
      () => _client.post(
        endpoint,
        headers: _headers(session, deviceId, jsonBody: true),
        body: jsonEncode(<String, Object>{
          'confirm': true,
          'confirmation_token': confirmationToken,
          'expected_evidence_digest': item.evidenceDigest,
          'expected_amount': item.amount,
          'expected_cash_account_code': item.cashAccountCode,
          'expected_posting_date': item.fundingDate,
          'expected_fiscal_period_id': item.fiscalPeriodId!,
        }),
      ),
    );
    return _item(data);
  }

  InitialCapitalFundingItem _item(Map<String, dynamic> data) =>
      InitialCapitalFundingItem.fromPayload(stringMap(data['item']));

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
        'The protected initial-capital server could not be reached.',
        code: 'network_unavailable',
      );
    }

    late final Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable initial-capital data.',
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
