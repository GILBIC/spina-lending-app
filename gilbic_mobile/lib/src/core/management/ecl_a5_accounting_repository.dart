import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/ecl_a5_accounting.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class EclA5AccountingRepository {
  Future<EclA5Overview> load(
    UserSession session, {
    required String deviceId,
    String status = 'all',
    int limit = 100,
    int offset = 0,
  });

  Future<EclA5ActionReceipt> postRemeasurement(
    UserSession session, {
    required String deviceId,
    required EclA5ActionItem item,
    required String reviewToken,
  });

  Future<EclA5ActionReceipt> postFullWriteoff(
    UserSession session, {
    required String deviceId,
    required EclA5ActionItem item,
    required String reviewToken,
  });

  Future<EclA5ActionReceipt> reviewRecovery(
    UserSession session, {
    required String deviceId,
    required EclA5ActionItem item,
    required String reviewToken,
    required String evidenceReference,
    required String reviewNote,
  });

  Future<EclA5ActionReceipt> postRecovery(
    UserSession session, {
    required String deviceId,
    required EclA5ActionItem item,
    required String reviewToken,
  });
}

class SpinaEclA5AccountingRepository implements EclA5AccountingRepository {
  SpinaEclA5AccountingRepository({http.Client? client})
    : _client = client ?? http.Client();

  final http.Client _client;
  static final _tokenPattern = RegExp(r'^[0-9a-f]{64}$');

  @override
  Future<EclA5Overview> load(
    UserSession session, {
    required String deviceId,
    String status = 'all',
    int limit = 100,
    int offset = 0,
  }) async {
    if (!eclA5Filters.contains(status)) {
      throw ArgumentError.value(status, 'status', 'Unsupported A5 status.');
    }
    if (limit < 1 || limit > 200 || offset < 0) {
      throw ArgumentError('Invalid A5 queue page coordinates.');
    }
    final endpoint =
        ApiConfig.endpoint(
          '/api/mobile/v1/management/financial-accounting/ecl-a5',
        ).replace(
          queryParameters: <String, String>{
            if (status != 'all') 'status': status,
            'limit': '$limit',
            'offset': '$offset',
          },
        );
    return EclA5Overview.fromPayload(
      await _request(
        () => _client.get(endpoint, headers: _headers(session, deviceId)),
      ),
    );
  }

  @override
  Future<EclA5ActionReceipt> postRemeasurement(
    UserSession session, {
    required String deviceId,
    required EclA5ActionItem item,
    required String reviewToken,
  }) async {
    item.requireRemeasurementCoordinates();
    _requireToken(reviewToken);
    final data = await _post(
      session,
      deviceId,
      '/api/mobile/v1/management/financial-accounting/ecl-a5/'
      'measurements/${Uri.encodeComponent(item.measurementId!)}/remeasure',
      <String, Object>{
        'review_token': reviewToken,
        'expected_calculation_digest': item.calculationDigest!,
        'expected_prior_allowance': item.currentAllowanceBalance,
        'expected_target_allowance': item.authoritativeEclAmount!,
        'expected_posting_date': eclA5DateText(item.postingDate!),
        'expected_fiscal_period_id': item.fiscalPeriodId!,
        'expected_credit_loss_expense_account_id':
            item.creditLossExpenseAccountId!,
        'expected_allowance_account_id': item.allowanceAccountId!,
      },
    );
    return EclA5ActionReceipt.fromPayload(data, 'remeasurement_id');
  }

  @override
  Future<EclA5ActionReceipt> postFullWriteoff(
    UserSession session, {
    required String deviceId,
    required EclA5ActionItem item,
    required String reviewToken,
  }) async {
    item.requireWriteoffCoordinates();
    _requireToken(reviewToken);
    final data = await _post(
      session,
      deviceId,
      '/api/mobile/v1/management/financial-accounting/ecl-a5/'
      'loans/${Uri.encodeComponent(item.loanId)}/writeoff',
      <String, Object>{
        'review_token': reviewToken,
        'expected_credit_risk_review_id': item.creditRiskReviewId!,
        'expected_measurement_id': item.measurementId!,
        'expected_calculation_digest': item.calculationDigest!,
        'expected_loan_component': item.loanComponent!,
        'expected_accrued_interest_component': item.accruedInterestComponent!,
        'expected_gross_carrying_amount': item.grossCarryingAmount!,
        'expected_allowance_balance': item.currentAllowanceBalance,
        'expected_loan_receivable_account_id': item.loanReceivableAccountId!,
        'expected_accrued_interest_account_id': item.accruedInterestAccountId!,
        'expected_allowance_account_id': item.allowanceAccountId!,
        'expected_posting_date': eclA5DateText(item.postingDate!),
        'expected_fiscal_period_id': item.fiscalPeriodId!,
      },
    );
    return EclA5ActionReceipt.fromPayload(data, 'writeoff_id');
  }

  @override
  Future<EclA5ActionReceipt> reviewRecovery(
    UserSession session, {
    required String deviceId,
    required EclA5ActionItem item,
    required String reviewToken,
    required String evidenceReference,
    required String reviewNote,
  }) async {
    item.requireRecoveryReviewCoordinates();
    _requireToken(reviewToken);
    final reference = evidenceReference.trim();
    final note = reviewNote.trim();
    if (reference.isEmpty || reference.length > 500) {
      throw ArgumentError.value(
        evidenceReference,
        'evidenceReference',
        'A retained evidence reference is required.',
      );
    }
    if (note.length < 20 || note.length > 4000) {
      throw ArgumentError.value(
        reviewNote,
        'reviewNote',
        'A substantive Management note is required.',
      );
    }
    final data = await _post(
      session,
      deviceId,
      '/api/mobile/v1/management/financial-accounting/ecl-a5/'
      'loans/${Uri.encodeComponent(item.loanId)}/recovery-review',
      <String, Object>{
        'review_token': reviewToken,
        'expected_recovery_transaction_id':
            item.recoveryCandidateTransactionId!,
        'expected_recovery_amount': item.recoveryCandidateAmount!,
        'evidence_reference': reference,
        'review_note': note,
      },
    );
    if (data['recovery_transaction_id'] !=
        item.recoveryCandidateTransactionId) {
      throw const SpinaApiException(
        'The SPINA server returned a recovery review for different evidence.',
        code: 'invalid_ecl_a5_payload',
      );
    }
    return EclA5ActionReceipt.fromPayload(
      data,
      'credit_risk_review_id',
      integerId: true,
    );
  }

  @override
  Future<EclA5ActionReceipt> postRecovery(
    UserSession session, {
    required String deviceId,
    required EclA5ActionItem item,
    required String reviewToken,
  }) async {
    item.requireRecoveryPostingCoordinates();
    _requireToken(reviewToken);
    final data = await _post(
      session,
      deviceId,
      '/api/mobile/v1/management/financial-accounting/ecl-a5/'
      'reviews/${item.creditRiskReviewId}/recovery',
      <String, Object>{
        'review_token': reviewToken,
        'expected_recovery_transaction_id': item.recoveryTransactionId!,
        'expected_recovery_amount': item.recoveryAmount!,
        'expected_posting_date': eclA5DateText(item.postingDate!),
        'expected_fiscal_period_id': item.fiscalPeriodId!,
        'expected_cash_account_id': item.cashAccountId!,
        'expected_credit_loss_expense_account_id':
            item.creditLossExpenseAccountId!,
      },
    );
    return EclA5ActionReceipt.fromPayload(data, 'recovery_id');
  }

  Future<Map<String, dynamic>> _post(
    UserSession session,
    String deviceId,
    String path,
    Map<String, Object> body,
  ) => _request(
    () => _client.post(
      ApiConfig.endpoint(path),
      headers: _headers(session, deviceId, jsonBody: true),
      body: jsonEncode(body),
    ),
  );

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
        'The protected A5 ECL accounting server could not be reached.',
        code: 'network_unavailable',
      );
    }
    late final Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable A5 ECL accounting data.',
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
