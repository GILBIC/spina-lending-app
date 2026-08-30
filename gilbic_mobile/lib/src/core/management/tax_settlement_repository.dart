import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/tax_settlement.dart';
import 'package:gilbic_mobile/src/core/management/tax_value.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class TaxSettlementRepository {
  Future<TaxSettlementOverview> load(
    UserSession session, {
    required String deviceId,
    String settlementStatus = 'all',
    int limit = 100,
    int offset = 0,
  });
  Future<TaxSettlementItem> recordReturn(
    UserSession session, {
    required String deviceId,
    required List<TaxReturnLiabilityCandidate> candidates,
    required String idempotencyKey,
    required String returnPeriodStart,
    required String returnPeriodEnd,
    required String filingDate,
    required String returnReference,
    required String evidenceReference,
    required String evidenceDigest,
    required String evidenceNote,
  });
  Future<TaxSettlementItem> recordPayment(
    UserSession session, {
    required String deviceId,
    required TaxSettlementItem item,
    required String idempotencyKey,
    required String paymentDate,
    required String cashAccountSystemKey,
    required String paymentReference,
    required String evidenceReference,
    required String evidenceDigest,
    required String evidenceNote,
  });
  Future<TaxSettlementItem> prepare(
    UserSession session, {
    required String deviceId,
    required TaxSettlementItem item,
  });
  Future<TaxSettlementItem> post(
    UserSession session, {
    required String deviceId,
    required TaxSettlementItem item,
    required String confirmationToken,
  });
}

class SpinaTaxSettlementRepository implements TaxSettlementRepository {
  SpinaTaxSettlementRepository({http.Client? client})
    : _client = client ?? http.Client();
  final http.Client _client;

  @override
  Future<TaxSettlementOverview> load(
    UserSession session, {
    required String deviceId,
    String settlementStatus = 'all',
    int limit = 100,
    int offset = 0,
  }) async {
    if (!taxSettlementFilters.contains(settlementStatus) ||
        limit < 1 ||
        limit > 200 ||
        offset < 0) {
      throw ArgumentError('Invalid tax-settlement page coordinates.');
    }
    final endpoint =
        ApiConfig.endpoint(
          '/api/mobile/v1/management/financial-accounting/tax/settlements',
        ).replace(
          queryParameters: <String, String>{
            'settlement_status': settlementStatus,
            'limit': '$limit',
            'offset': '$offset',
          },
        );
    return TaxSettlementOverview.fromPayload(
      await _request(
        () => _client.get(endpoint, headers: _headers(session, deviceId)),
      ),
    );
  }

  @override
  Future<TaxSettlementItem> recordReturn(
    UserSession session, {
    required String deviceId,
    required List<TaxReturnLiabilityCandidate> candidates,
    required String idempotencyKey,
    required String returnPeriodStart,
    required String returnPeriodEnd,
    required String filingDate,
    required String returnReference,
    required String evidenceReference,
    required String evidenceDigest,
    required String evidenceNote,
  }) async {
    _requireUuid(idempotencyKey, 'idempotencyKey');
    _requireDigest(evidenceDigest, 'evidenceDigest');
    if (candidates.isEmpty || candidates.length > 500) {
      throw ArgumentError('At least one server-derived liability is required.');
    }
    final taxType = candidates.first.taxType;
    if (candidates.any((candidate) => candidate.taxType != taxType) ||
        candidates.map((candidate) => candidate.postingId).toSet().length !=
            candidates.length) {
      throw ArgumentError(
        'Return liabilities must be unique and one tax type.',
      );
    }
    final start = _date(returnPeriodStart, 'returnPeriodStart');
    final end = _date(returnPeriodEnd, 'returnPeriodEnd');
    final filing = _date(filingDate, 'filingDate');
    if (end.isBefore(start) ||
        filing.isBefore(end) ||
        candidates.any((candidate) {
          final recognition = DateTime.parse(candidate.recognitionDate);
          return recognition.isBefore(start) || recognition.isAfter(end);
        })) {
      throw ArgumentError('Return dates do not cover selected liabilities.');
    }
    final declaredTaxDue = _moneyFromCents(
      candidates.fold<int>(0, (total, item) => total + taxCents(item.taxDue)),
    );
    return _write(
      session,
      deviceId,
      '/api/mobile/v1/management/financial-accounting/tax/settlements/returns',
      <String, Object>{
        'idempotency_key': idempotencyKey,
        'tax_type': taxType,
        'return_period_start': returnPeriodStart,
        'return_period_end': returnPeriodEnd,
        'filing_date': filingDate,
        'declared_tax_due': declaredTaxDue,
        'return_reference': _required(returnReference, 'returnReference'),
        'evidence_reference': _required(evidenceReference, 'evidenceReference'),
        'evidence_digest': evidenceDigest,
        'evidence_note': _note(evidenceNote),
        'liability_posting_ids': candidates
            .map((candidate) => candidate.postingId)
            .toList(growable: false),
      },
    );
  }

  @override
  Future<TaxSettlementItem> recordPayment(
    UserSession session, {
    required String deviceId,
    required TaxSettlementItem item,
    required String idempotencyKey,
    required String paymentDate,
    required String cashAccountSystemKey,
    required String paymentReference,
    required String evidenceReference,
    required String evidenceDigest,
    required String evidenceNote,
  }) {
    item.requirePaymentCoordinates();
    _requireUuid(idempotencyKey, 'idempotencyKey');
    _requireDigest(evidenceDigest, 'evidenceDigest');
    if (!const <String>{
      'cash_office',
      'cash_bank_gcash',
    }.contains(cashAccountSystemKey)) {
      throw ArgumentError('Unsupported tax payment cash account.');
    }
    if (_date(
      paymentDate,
      'paymentDate',
    ).isBefore(DateTime.parse(item.filingDate))) {
      throw ArgumentError(
        'Payment date cannot predate retained filing evidence.',
      );
    }
    return _write(
      session,
      deviceId,
      '/api/mobile/v1/management/financial-accounting/tax/settlements/returns/'
      '${Uri.encodeComponent(item.taxReturnId)}/payments',
      <String, Object>{
        'idempotency_key': idempotencyKey,
        'payment_date': paymentDate,
        'payment_amount': item.declaredTaxDue,
        'cash_account_system_key': cashAccountSystemKey,
        'payment_reference': _required(paymentReference, 'paymentReference'),
        'evidence_reference': _required(evidenceReference, 'evidenceReference'),
        'evidence_digest': evidenceDigest,
        'evidence_note': _note(evidenceNote),
      },
    );
  }

  @override
  Future<TaxSettlementItem> prepare(
    UserSession session, {
    required String deviceId,
    required TaxSettlementItem item,
  }) {
    item.requirePrepareCoordinates();
    return _write(
      session,
      deviceId,
      '/api/mobile/v1/management/financial-accounting/tax/settlements/payments/'
      '${Uri.encodeComponent(item.paymentEvidenceId!)}/prepare',
      const <String, Object>{'confirm': true},
    );
  }

  @override
  Future<TaxSettlementItem> post(
    UserSession session, {
    required String deviceId,
    required TaxSettlementItem item,
    required String confirmationToken,
  }) {
    item.requirePostCoordinates();
    _requireDigest(confirmationToken, 'confirmationToken');
    return _write(
      session,
      deviceId,
      '/api/mobile/v1/management/financial-accounting/tax/settlements/payments/'
      '${Uri.encodeComponent(item.paymentEvidenceId!)}/post',
      <String, Object>{
        'confirm': true,
        'confirmation_token': confirmationToken,
        'expected_return_evidence_digest': item.returnEvidenceDigest,
        'expected_payment_evidence_digest': item.paymentEvidenceDigest!,
        'expected_payment_amount': item.paymentAmount!,
        'expected_tax_payable_account_code': item.taxPayableAccountCode!,
        'expected_cash_account_code': item.cashAccountCode!,
        'expected_posting_date': item.paymentDate!,
        'expected_fiscal_period_id': item.fiscalPeriodId!,
      },
    );
  }

  Future<TaxSettlementItem> _write(
    UserSession session,
    String deviceId,
    String path,
    Map<String, Object> body,
  ) async {
    final data = await _request(
      () => _client.post(
        ApiConfig.endpoint(path),
        headers: _headers(session, deviceId, jsonBody: true),
        body: jsonEncode(body),
      ),
    );
    return TaxSettlementItem.fromPayload(stringMap(data['item']));
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
        'The protected tax-settlement server could not be reached.',
        code: 'network_unavailable',
      );
    }
    late final Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable protected tax-settlement data.',
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

void _requireUuid(String value, String name) {
  if (!taxUuidPattern.hasMatch(value)) throw ArgumentError.value(value, name);
}

void _requireDigest(String value, String name) {
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

String _moneyFromCents(int cents) =>
    '${cents ~/ 100}.${(cents % 100).toString().padLeft(2, '0')}';
