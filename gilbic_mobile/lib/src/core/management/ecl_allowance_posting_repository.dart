import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/ecl_allowance_posting.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class EclAllowancePostingRepository {
  Future<EclAllowancePostingOverview> load(
    UserSession session, {
    required String deviceId,
    String status = 'all',
    int limit = 100,
    int offset = 0,
  });

  Future<EclAllowanceActionReceipt> prepare(
    UserSession session, {
    required String deviceId,
    required EclAllowancePostingItem item,
    required String reviewToken,
  });

  Future<EclAllowanceActionReceipt> post(
    UserSession session, {
    required String deviceId,
    required EclAllowancePostingItem item,
    required String reviewToken,
  });
}

class SpinaEclAllowancePostingRepository
    implements EclAllowancePostingRepository {
  SpinaEclAllowancePostingRepository({http.Client? client})
    : _client = client ?? http.Client();

  final http.Client _client;

  static const _statuses = <String>{
    'all',
    'measurement_not_authoritative',
    'no_allowance_required',
    'preparation_required',
    'posting_ready',
    'posted_current',
    'a5_remeasurement_required',
    'posting_audit_incomplete',
    'ready',
  };
  static final _tokenPattern = RegExp(r'^[0-9a-f]{64}$');

  @override
  Future<EclAllowancePostingOverview> load(
    UserSession session, {
    required String deviceId,
    String status = 'all',
    int limit = 100,
    int offset = 0,
  }) async {
    if (!_statuses.contains(status)) {
      throw ArgumentError.value(
        status,
        'status',
        'Unsupported allowance status.',
      );
    }
    if (limit < 1 || limit > 200 || offset < 0) {
      throw ArgumentError('Invalid allowance queue page coordinates.');
    }
    final endpoint =
        ApiConfig.endpoint(
          '/api/mobile/v1/management/financial-accounting/ecl-allowance-posting',
        ).replace(
          queryParameters: <String, String>{
            if (status != 'all') 'status': status,
            'limit': '$limit',
            'offset': '$offset',
          },
        );
    final data = await _request(
      () => _client.get(endpoint, headers: _headers(session, deviceId)),
    );
    return EclAllowancePostingOverview.fromPayload(data);
  }

  @override
  Future<EclAllowanceActionReceipt> prepare(
    UserSession session, {
    required String deviceId,
    required EclAllowancePostingItem item,
    required String reviewToken,
  }) async {
    item.requirePreparationCoordinates();
    _requireToken(reviewToken);
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting/ecl-allowance-posting/'
      '${Uri.encodeComponent(item.measurementId!)}/prepare',
    );
    final data = await _request(
      () => _client.post(
        endpoint,
        headers: _headers(session, deviceId, jsonBody: true),
        body: jsonEncode(<String, Object>{
          'preparation_review_token': reviewToken,
          'expected_calculation_digest': item.calculationDigest!,
          'expected_ecl_amount': item.authoritativeEclAmount!,
          'expected_posting_date': eclAllowanceDateText(item.postingDate!),
          'expected_fiscal_period_id': item.fiscalPeriodId!,
          'expected_credit_loss_expense_account_id':
              item.creditLossExpenseAccountId!,
          'expected_allowance_account_id': item.allowanceAccountId!,
          'expected_prior_allowance_balance': item.priorAllowanceBalance!,
        }),
      ),
    );
    return EclAllowanceActionReceipt.fromPayload(data);
  }

  @override
  Future<EclAllowanceActionReceipt> post(
    UserSession session, {
    required String deviceId,
    required EclAllowancePostingItem item,
    required String reviewToken,
  }) async {
    item.requirePostingCoordinates();
    _requireToken(reviewToken);
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting/ecl-allowance-posting/'
      'preparations/${Uri.encodeComponent(item.preparationId!)}/post',
    );
    final data = await _request(
      () => _client.post(
        endpoint,
        headers: _headers(session, deviceId, jsonBody: true),
        body: jsonEncode(<String, Object>{
          'posting_review_token': reviewToken,
          'expected_measurement_id': item.measurementId!,
          'expected_calculation_digest': item.calculationDigest!,
          'expected_journal_entry_id': item.journalEntryId!,
          'expected_source_event_key': item.sourceEventKey!,
          'expected_preparation_digest': item.preparationDigest!,
          'expected_posting_date': eclAllowanceDateText(item.postingDate!),
          'expected_fiscal_period_id': item.fiscalPeriodId!,
          'expected_credit_loss_expense_account_id':
              item.creditLossExpenseAccountId!,
          'expected_allowance_account_id': item.allowanceAccountId!,
          'expected_allowance_amount': item.allowanceAmount!,
          'expected_prior_allowance_balance': item.priorAllowanceBalance!,
        }),
      ),
    );
    return EclAllowanceActionReceipt.fromPayload(data);
  }

  void _requireToken(String token) {
    if (!_tokenPattern.hasMatch(token)) {
      throw ArgumentError.value(
        token,
        'reviewToken',
        'Expected 64 lowercase hexadecimal characters.',
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
        'The protected ECL allowance server could not be reached.',
        code: 'network_unavailable',
      );
    }

    late final Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable ECL allowance data.',
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
