import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/additional_tax.dart';
import 'package:gilbic_mobile/src/core/management/tax_value.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class AdditionalTaxRepository {
  Future<AdditionalTaxOverview> load(
    UserSession session, {
    required String deviceId,
    String amendmentStatus = 'all',
    int limit = 100,
    int offset = 0,
  });
  Future<AdditionalTaxItem> recordAmendmentEvidence(
    UserSession session, {
    required String deviceId,
    required AdditionalTaxCandidate candidate,
    required String idempotencyKey,
    required String amendmentBasis,
    required String amendmentDate,
    required String amendmentReference,
    required String evidenceReference,
    required String evidenceDigest,
    required String evidenceNote,
  });
  Future<AdditionalTaxItem> prepareLiability(
    UserSession session, {
    required String deviceId,
    required AdditionalTaxItem item,
  });
  Future<AdditionalTaxItem> postLiability(
    UserSession session, {
    required String deviceId,
    required AdditionalTaxItem item,
    required String confirmationToken,
  });
  Future<AdditionalTaxItem> recordPayment(
    UserSession session, {
    required String deviceId,
    required AdditionalTaxItem item,
    required String idempotencyKey,
    required String paymentDate,
    required String cashAccountSystemKey,
    required String paymentReference,
    required String evidenceReference,
    required String evidenceDigest,
    required String evidenceNote,
  });
  Future<AdditionalTaxItem> prepareSettlement(
    UserSession session, {
    required String deviceId,
    required AdditionalTaxItem item,
  });
  Future<AdditionalTaxItem> postSettlement(
    UserSession session, {
    required String deviceId,
    required AdditionalTaxItem item,
    required String confirmationToken,
  });
}

class SpinaAdditionalTaxRepository implements AdditionalTaxRepository {
  SpinaAdditionalTaxRepository({http.Client? client})
    : _client = client ?? http.Client();
  final http.Client _client;
  static const _base =
      '/api/mobile/v1/management/financial-accounting/tax/additional-amendments';

  @override
  Future<AdditionalTaxOverview> load(
    UserSession session, {
    required String deviceId,
    String amendmentStatus = 'all',
    int limit = 100,
    int offset = 0,
  }) async {
    if (!additionalTaxFilters.contains(amendmentStatus) ||
        limit < 1 ||
        limit > 200 ||
        offset < 0) {
      throw ArgumentError('Invalid additional-tax page coordinates.');
    }
    final endpoint = ApiConfig.endpoint(_base).replace(
      queryParameters: <String, String>{
        'amendment_status': amendmentStatus,
        'limit': '$limit',
        'offset': '$offset',
      },
    );
    return AdditionalTaxOverview.fromPayload(
      await _request(
        () => _client.get(endpoint, headers: _headers(session, deviceId)),
      ),
    );
  }

  @override
  Future<AdditionalTaxItem> recordAmendmentEvidence(
    UserSession session, {
    required String deviceId,
    required AdditionalTaxCandidate candidate,
    required String idempotencyKey,
    required String amendmentBasis,
    required String amendmentDate,
    required String amendmentReference,
    required String evidenceReference,
    required String evidenceDigest,
    required String evidenceNote,
  }) {
    _uuid(idempotencyKey, 'idempotencyKey');
    _digest(evidenceDigest, 'evidenceDigest');
    if (!amendmentBasisValues.contains(amendmentBasis)) {
      throw ArgumentError.value(amendmentBasis, 'amendmentBasis');
    }
    if (_date(
      amendmentDate,
      'amendmentDate',
    ).isBefore(DateTime.parse(candidate.filingDate))) {
      throw ArgumentError('Amendment evidence cannot predate filing.');
    }
    return _write(session, deviceId, '$_base/evidence', <String, Object>{
      'idempotency_key': idempotencyKey,
      'tax_return_id': candidate.taxReturnId,
      'tax_liability_posting_id': candidate.taxLiabilityPostingId,
      'replacement_evidence_id': candidate.replacementEvidenceId,
      'amendment_basis': amendmentBasis,
      'amendment_date': amendmentDate,
      'recognition_date': candidate.recognitionDate,
      'amendment_reference': _required(
        amendmentReference,
        'amendmentReference',
      ),
      'evidence_reference': _required(evidenceReference, 'evidenceReference'),
      'evidence_digest': evidenceDigest,
      'evidence_note': _note(evidenceNote),
    });
  }

  @override
  Future<AdditionalTaxItem> prepareLiability(
    UserSession session, {
    required String deviceId,
    required AdditionalTaxItem item,
  }) {
    item.requirePrepareLiability();
    return _write(
      session,
      deviceId,
      '$_base/${Uri.encodeComponent(item.amendmentEvidenceId)}/prepare-liability',
      const <String, Object>{'confirm': true},
    );
  }

  @override
  Future<AdditionalTaxItem> postLiability(
    UserSession session, {
    required String deviceId,
    required AdditionalTaxItem item,
    required String confirmationToken,
  }) {
    item.requirePostLiability();
    _digest(confirmationToken, 'confirmationToken');
    return _write(
      session,
      deviceId,
      '$_base/${Uri.encodeComponent(item.amendmentEvidenceId)}/post-liability',
      <String, Object>{
        'confirm': true,
        'confirmation_token': confirmationToken,
        'expected_evidence_digest': item.evidenceDigest,
        'expected_original_declared_tax_due': item.originalDeclaredTaxDue,
        'expected_revised_declared_tax_due': item.revisedDeclaredTaxDue,
        'expected_original_item_tax_due': item.originalItemTaxDue,
        'expected_replacement_item_tax_due': item.replacementItemTaxDue,
        'expected_additional_tax_due': item.additionalTaxDue,
        'expected_expense_account_code': item.expenseAccountCode!,
        'expected_tax_payable_account_code': item.taxPayableAccountCode!,
        'expected_posting_date': item.recognitionDate,
        'expected_fiscal_period_id': item.liabilityFiscalPeriodId!,
      },
    );
  }

  @override
  Future<AdditionalTaxItem> recordPayment(
    UserSession session, {
    required String deviceId,
    required AdditionalTaxItem item,
    required String idempotencyKey,
    required String paymentDate,
    required String cashAccountSystemKey,
    required String paymentReference,
    required String evidenceReference,
    required String evidenceDigest,
    required String evidenceNote,
  }) {
    item.requirePayment();
    _uuid(idempotencyKey, 'idempotencyKey');
    _digest(evidenceDigest, 'evidenceDigest');
    if (!const <String>{
      'cash_office',
      'cash_bank_gcash',
    }.contains(cashAccountSystemKey)) {
      throw ArgumentError.value(cashAccountSystemKey, 'cashAccountSystemKey');
    }
    if (_date(
      paymentDate,
      'paymentDate',
    ).isBefore(DateTime.parse(item.amendmentDate))) {
      throw ArgumentError('Payment evidence cannot predate the amendment.');
    }
    return _write(
      session,
      deviceId,
      '$_base/${Uri.encodeComponent(item.amendmentEvidenceId)}/payment-evidence',
      <String, Object>{
        'idempotency_key': idempotencyKey,
        'payment_date': paymentDate,
        'payment_amount': item.paymentRequiredAmount,
        'cash_account_system_key': cashAccountSystemKey,
        'payment_reference': _required(paymentReference, 'paymentReference'),
        'evidence_reference': _required(evidenceReference, 'evidenceReference'),
        'evidence_digest': evidenceDigest,
        'evidence_note': _note(evidenceNote),
      },
    );
  }

  @override
  Future<AdditionalTaxItem> prepareSettlement(
    UserSession session, {
    required String deviceId,
    required AdditionalTaxItem item,
  }) {
    item.requirePrepareSettlement();
    return _write(
      session,
      deviceId,
      '$_base/${Uri.encodeComponent(item.amendmentEvidenceId)}/prepare-settlement',
      const <String, Object>{'confirm': true},
    );
  }

  @override
  Future<AdditionalTaxItem> postSettlement(
    UserSession session, {
    required String deviceId,
    required AdditionalTaxItem item,
    required String confirmationToken,
  }) {
    item.requirePostSettlement();
    _digest(confirmationToken, 'confirmationToken');
    return _write(
      session,
      deviceId,
      '$_base/${Uri.encodeComponent(item.amendmentEvidenceId)}/post-settlement',
      <String, Object>{
        'confirm': true,
        'confirmation_token': confirmationToken,
        'expected_amendment_evidence_digest': item.evidenceDigest,
        'expected_additional_liability_confirmation_digest':
            item.liabilityConfirmationDigest!,
        'expected_payment_evidence_digest': item.paymentEvidenceDigest!,
        'expected_payment_amount': item.paymentAmount!,
        'expected_tax_payable_account_code': item.taxPayableAccountCode!,
        'expected_cash_account_code': item.paymentCashAccountCode!,
        'expected_posting_date': item.paymentDate!,
        'expected_fiscal_period_id': item.settlementFiscalPeriodId!,
      },
    );
  }

  Future<AdditionalTaxItem> _write(
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
    return AdditionalTaxItem.fromPayload(stringMap(data['item']));
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
        'The protected additional-tax server could not be reached.',
        code: 'network_unavailable',
      );
    }
    late final Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable protected additional-tax data.',
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
