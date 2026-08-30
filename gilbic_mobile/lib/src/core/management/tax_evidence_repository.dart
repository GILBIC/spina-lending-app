import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/tax_evidence.dart';
import 'package:gilbic_mobile/src/core/management/tax_value.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class TaxEvidenceRepository {
  Future<TaxEvidenceOverview> load(
    UserSession session, {
    required String deviceId,
    String readiness = 'all',
    int limit = 100,
    int offset = 0,
  });
  Future<String> recordRule(
    UserSession session, {
    required String deviceId,
    required TaxRuleEvidenceDraft draft,
    required String idempotencyKey,
  });
  Future<String> recordDst(
    UserSession session, {
    required String deviceId,
    required DstTaxReadiness source,
    required DstEvidenceDraft draft,
    required String idempotencyKey,
  });
  Future<String> recordPercentage(
    UserSession session, {
    required String deviceId,
    required PercentageTaxReadiness source,
    required PercentageTaxEvidenceDraft draft,
    required String idempotencyKey,
  });
}

class SpinaTaxEvidenceRepository implements TaxEvidenceRepository {
  SpinaTaxEvidenceRepository({http.Client? client})
    : _client = client ?? http.Client();
  final http.Client _client;

  @override
  Future<TaxEvidenceOverview> load(
    UserSession session, {
    required String deviceId,
    String readiness = 'all',
    int limit = 100,
    int offset = 0,
  }) async {
    if (!const <String>{'all', 'ready', 'blocked'}.contains(readiness) ||
        limit < 1 ||
        limit > 200 ||
        offset < 0) {
      throw ArgumentError('Invalid tax-evidence page coordinates.');
    }
    final endpoint =
        ApiConfig.endpoint(
          '/api/mobile/v1/management/financial-accounting/tax',
        ).replace(
          queryParameters: <String, String>{
            'readiness': readiness,
            'limit': '$limit',
            'offset': '$offset',
          },
        );
    return TaxEvidenceOverview.fromPayload(
      await _request(
        () => _client.get(endpoint, headers: _headers(session, deviceId)),
      ),
    );
  }

  @override
  Future<String> recordRule(
    UserSession session, {
    required String deviceId,
    required TaxRuleEvidenceDraft draft,
    required String idempotencyKey,
  }) async {
    draft.validate();
    _retry(idempotencyKey);
    final data = await _post(
      session,
      deviceId,
      '/api/mobile/v1/management/financial-accounting/tax/rules',
      draft.toPayload(idempotencyKey.toLowerCase()),
    );
    _receiptPolicy(data);
    return taxUuid(data, 'rule_evidence_id');
  }

  @override
  Future<String> recordDst(
    UserSession session, {
    required String deviceId,
    required DstTaxReadiness source,
    required DstEvidenceDraft draft,
    required String idempotencyKey,
  }) async {
    draft.validate();
    _retry(idempotencyKey);
    final data = await _post(
      session,
      deviceId,
      '/api/mobile/v1/management/financial-accounting/tax/dst-evidence',
      <String, Object?>{
        'confirm': true,
        'idempotency_key': idempotencyKey.toLowerCase(),
        'loan_id': source.loanId,
        'disbursement_event_id': source.disbursementEventId,
        'rule_evidence_id': draft.ruleEvidenceId,
        'expected_issue_price': source.protectedIssuePrice,
        'expected_term_days': source.protectedTermDays,
        'expected_tax_due': draft.expectedTaxDue,
        'instrument_reference': draft.instrumentReference.trim(),
        'instrument_digest': draft.instrumentDigest,
        'calculation_reference': draft.calculationReference.trim(),
        'calculation_digest': draft.calculationDigest,
        'management_rationale': draft.managementRationale.trim(),
        'supersedes_evidence_id': source.evidenceId,
      },
    );
    _receiptPolicy(data);
    return taxUuid(data, 'dst_evidence_id');
  }

  @override
  Future<String> recordPercentage(
    UserSession session, {
    required String deviceId,
    required PercentageTaxReadiness source,
    required PercentageTaxEvidenceDraft draft,
    required String idempotencyKey,
  }) async {
    draft.validate(source.sourceCashAmount);
    _retry(idempotencyKey);
    final data = await _post(
      session,
      deviceId,
      '/api/mobile/v1/management/financial-accounting/tax/percentage-evidence',
      <String, Object?>{
        'confirm': true,
        'idempotency_key': idempotencyKey.toLowerCase(),
        'transaction_id': source.transactionId,
        'rule_evidence_id': draft.ruleEvidenceId,
        'expected_source_cash_amount': source.sourceCashAmount,
        'taxable_lending_receipt_amount': draft.taxableLendingReceiptAmount,
        'principal_receipt_amount': draft.principalReceiptAmount,
        'expected_tax_due': draft.expectedTaxDue,
        'allocation_reference': draft.allocationReference.trim(),
        'allocation_digest': draft.allocationDigest,
        'management_rationale': draft.managementRationale.trim(),
        'supersedes_evidence_id': source.evidenceId,
      },
    );
    _receiptPolicy(data);
    return taxUuid(data, 'percentage_tax_evidence_id');
  }

  Future<Map<String, dynamic>> _post(
    UserSession session,
    String deviceId,
    String path,
    Map<String, Object?> body,
  ) => _request(
    () => _client.post(
      ApiConfig.endpoint(path),
      headers: _headers(session, deviceId, jsonBody: true),
      body: jsonEncode(body),
    ),
  );

  void _retry(String value) {
    if (!taxUuidPattern.hasMatch(value)) {
      throw ArgumentError.value(
        value,
        'idempotencyKey',
        'Expected an RFC 4122 UUID.',
      );
    }
  }

  void _receiptPolicy(Map<String, dynamic> data) {
    if (taxBool(data, 'tax_posting_enabled') ||
        taxBool(data, 'automatic_source_posting')) {
      throw invalidTaxPayload('evidence receipt policy');
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
        'The protected tax-evidence server could not be reached.',
        code: 'network_unavailable',
      );
    }
    late final Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable protected tax data.',
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
