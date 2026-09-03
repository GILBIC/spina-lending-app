import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/tax_recoverable.dart';
import 'package:gilbic_mobile/src/core/management/tax_value.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class TaxRecoverableRepository {
  Future<TaxRecoverableWorkspace> load(
    UserSession session, {
    required String deviceId,
    String refundStatus = 'all',
    String creditStatus = 'all',
    int limit = 100,
    int offset = 0,
  });
  Future<TaxRecoverableRefundItem> recordRefundEvidence(
    UserSession session, {
    required String deviceId,
    required TaxRecoverableRefundCandidate candidate,
    required String idempotencyKey,
    required String refundDate,
    required String cashAccountCode,
    required String refundReference,
    required String authorityReference,
    required String evidenceDigest,
    required String evidenceNote,
  });
  Future<TaxRecoverableRefundItem> prepareRefund(
    UserSession session, {
    required String deviceId,
    required TaxRecoverableRefundItem item,
  });
  Future<TaxRecoverableRefundItem> postRefund(
    UserSession session, {
    required String deviceId,
    required TaxRecoverableRefundItem item,
    required String confirmationToken,
  });
  Future<TaxRecoverableCreditItem> recordCreditEvidence(
    UserSession session, {
    required String deviceId,
    required TaxRecoverableCreditCandidate candidate,
    required String idempotencyKey,
    required String applicationDate,
    required String applicationReference,
    required String authorityReference,
    required String evidenceDigest,
    required String evidenceNote,
  });
  Future<TaxRecoverableCreditItem> prepareCredit(
    UserSession session, {
    required String deviceId,
    required TaxRecoverableCreditItem item,
  });
  Future<TaxRecoverableCreditItem> postCredit(
    UserSession session, {
    required String deviceId,
    required TaxRecoverableCreditItem item,
    required String confirmationToken,
  });
}

class SpinaTaxRecoverableRepository implements TaxRecoverableRepository {
  SpinaTaxRecoverableRepository({http.Client? client})
    : _client = client ?? http.Client();
  final http.Client _client;
  static const _refundBase =
      '/api/mobile/v1/management/financial-accounting/tax/recoverable-refunds';
  static const _creditBase =
      '/api/mobile/v1/management/financial-accounting/tax/recoverable-credits';

  @override
  Future<TaxRecoverableWorkspace> load(
    UserSession session, {
    required String deviceId,
    String refundStatus = 'all',
    String creditStatus = 'all',
    int limit = 100,
    int offset = 0,
  }) async {
    if (!refundStatusFilters.contains(refundStatus) ||
        !creditStatusFilters.contains(creditStatus) ||
        limit < 1 ||
        limit > 200 ||
        offset < 0) {
      throw ArgumentError('Invalid Tax Recoverable page coordinates.');
    }
    final refundPayload = await _get(
      session,
      deviceId,
      _refundBase,
      <String, String>{
        'refund_status': refundStatus,
        'limit': '$limit',
        'offset': '$offset',
      },
    );
    final creditPayload = await _get(
      session,
      deviceId,
      _creditBase,
      <String, String>{
        'credit_status': creditStatus,
        'limit': '$limit',
        'offset': '$offset',
      },
    );
    return TaxRecoverableWorkspace(
      refunds: TaxRecoverableRefundOverview.fromPayload(refundPayload),
      credits: TaxRecoverableCreditOverview.fromPayload(creditPayload),
    );
  }

  @override
  Future<TaxRecoverableRefundItem> recordRefundEvidence(
    UserSession session, {
    required String deviceId,
    required TaxRecoverableRefundCandidate candidate,
    required String idempotencyKey,
    required String refundDate,
    required String cashAccountCode,
    required String refundReference,
    required String authorityReference,
    required String evidenceDigest,
    required String evidenceNote,
  }) {
    _uuid(idempotencyKey, 'idempotencyKey');
    _digest(evidenceDigest, 'evidenceDigest');
    if (!const <String>{'1010', '1030'}.contains(cashAccountCode)) {
      throw ArgumentError.value(cashAccountCode, 'cashAccountCode');
    }
    if (_date(
      refundDate,
      'refundDate',
    ).isBefore(DateTime.parse(candidate.minimumRefundDate))) {
      throw ArgumentError(
        'Refund evidence cannot predate recoverable posting.',
      );
    }
    return _writeRefund(
      session,
      deviceId,
      '$_refundBase/evidence',
      <String, Object>{
        'idempotency_key': idempotencyKey,
        'adjustment_posting_id': candidate.adjustmentPostingId,
        'refund_date': refundDate,
        'cash_account_code': cashAccountCode,
        'refund_reference': _required(refundReference, 'refundReference'),
        'authority_reference': _required(
          authorityReference,
          'authorityReference',
        ),
        'evidence_digest': evidenceDigest,
        'evidence_note': _note(evidenceNote),
      },
    );
  }

  @override
  Future<TaxRecoverableRefundItem> prepareRefund(
    UserSession session, {
    required String deviceId,
    required TaxRecoverableRefundItem item,
  }) {
    item.requirePrepare();
    return _writeRefund(
      session,
      deviceId,
      '$_refundBase/${Uri.encodeComponent(item.refundEvidenceId)}/prepare',
      const <String, Object>{'confirm': true},
    );
  }

  @override
  Future<TaxRecoverableRefundItem> postRefund(
    UserSession session, {
    required String deviceId,
    required TaxRecoverableRefundItem item,
    required String confirmationToken,
  }) {
    item.requirePost();
    _digest(confirmationToken, 'confirmationToken');
    return _writeRefund(
      session,
      deviceId,
      '$_refundBase/${Uri.encodeComponent(item.refundEvidenceId)}/post',
      <String, Object>{
        'confirm': true,
        'confirmation_token': confirmationToken,
        'expected_evidence_digest': item.evidenceDigest,
        'expected_refund_amount': item.refundAmount,
        'expected_cash_account_code': item.cashAccountCode,
        'expected_tax_recoverable_account_code':
            item.taxRecoverableAccountCode!,
        'expected_posting_date': item.refundDate,
        'expected_fiscal_period_id': item.fiscalPeriodId!,
      },
    );
  }

  @override
  Future<TaxRecoverableCreditItem> recordCreditEvidence(
    UserSession session, {
    required String deviceId,
    required TaxRecoverableCreditCandidate candidate,
    required String idempotencyKey,
    required String applicationDate,
    required String applicationReference,
    required String authorityReference,
    required String evidenceDigest,
    required String evidenceNote,
  }) {
    _uuid(idempotencyKey, 'idempotencyKey');
    _digest(evidenceDigest, 'evidenceDigest');
    if (_date(
      applicationDate,
      'applicationDate',
    ).isBefore(DateTime.parse(candidate.minimumApplicationDate))) {
      throw ArgumentError('Credit evidence cannot predate its exact sources.');
    }
    return _writeCredit(
      session,
      deviceId,
      '$_creditBase/evidence',
      <String, Object>{
        'idempotency_key': idempotencyKey,
        'adjustment_posting_id': candidate.adjustmentPostingId,
        'target_tax_return_id': candidate.targetTaxReturnId,
        'application_date': applicationDate,
        'application_reference': _required(
          applicationReference,
          'applicationReference',
        ),
        'authority_reference': _required(
          authorityReference,
          'authorityReference',
        ),
        'evidence_digest': evidenceDigest,
        'evidence_note': _note(evidenceNote),
      },
    );
  }

  @override
  Future<TaxRecoverableCreditItem> prepareCredit(
    UserSession session, {
    required String deviceId,
    required TaxRecoverableCreditItem item,
  }) {
    item.requirePrepare();
    return _writeCredit(
      session,
      deviceId,
      '$_creditBase/${Uri.encodeComponent(item.creditEvidenceId)}/prepare',
      const <String, Object>{'confirm': true},
    );
  }

  @override
  Future<TaxRecoverableCreditItem> postCredit(
    UserSession session, {
    required String deviceId,
    required TaxRecoverableCreditItem item,
    required String confirmationToken,
  }) {
    item.requirePost();
    _digest(confirmationToken, 'confirmationToken');
    return _writeCredit(
      session,
      deviceId,
      '$_creditBase/${Uri.encodeComponent(item.creditEvidenceId)}/post',
      <String, Object>{
        'confirm': true,
        'confirmation_token': confirmationToken,
        'expected_evidence_digest': item.evidenceDigest,
        'expected_credit_amount': item.creditAmount,
        'expected_tax_payable_account_code': item.taxPayableAccountCode!,
        'expected_tax_recoverable_account_code':
            item.taxRecoverableAccountCode!,
        'expected_posting_date': item.applicationDate,
        'expected_fiscal_period_id': item.fiscalPeriodId!,
      },
    );
  }

  Future<Map<String, dynamic>> _get(
    UserSession session,
    String deviceId,
    String path,
    Map<String, String> query,
  ) => _request(
    () => _client.get(
      ApiConfig.endpoint(path).replace(queryParameters: query),
      headers: _headers(session, deviceId),
    ),
  );

  Future<TaxRecoverableRefundItem> _writeRefund(
    UserSession session,
    String deviceId,
    String path,
    Map<String, Object> body,
  ) async => TaxRecoverableRefundItem.fromPayload(
    stringMap(
      (await _request(
        () => _client.post(
          ApiConfig.endpoint(path),
          headers: _headers(session, deviceId, jsonBody: true),
          body: jsonEncode(body),
        ),
      ))['item'],
    ),
  );

  Future<TaxRecoverableCreditItem> _writeCredit(
    UserSession session,
    String deviceId,
    String path,
    Map<String, Object> body,
  ) async => TaxRecoverableCreditItem.fromPayload(
    stringMap(
      (await _request(
        () => _client.post(
          ApiConfig.endpoint(path),
          headers: _headers(session, deviceId, jsonBody: true),
          body: jsonEncode(body),
        ),
      ))['item'],
    ),
  );

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
        'The protected Tax Recoverable server could not be reached.',
        code: 'network_unavailable',
      );
    }
    late final Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable Tax Recoverable data.',
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

void _uuid(String value, String name) {
  if (!taxUuidPattern.hasMatch(value)) throw ArgumentError.value(value, name);
}

void _digest(String value, String name) {
  if (!taxDigestPattern.hasMatch(value)) throw ArgumentError.value(value, name);
}

DateTime _date(String value, String name) {
  final parsed = DateTime.tryParse(value);
  if (parsed == null ||
      !taxDatePattern.hasMatch(value) ||
      taxDateText(parsed) != value) {
    throw ArgumentError.value(value, name);
  }
  return parsed;
}

String _required(String value, String name) {
  final normalized = value.trim();
  if (normalized.isEmpty) throw ArgumentError.value(value, name);
  return normalized;
}

String _note(String value) {
  final normalized = value.trim();
  if (normalized.length < 20) throw ArgumentError.value(value, 'evidenceNote');
  return normalized;
}
