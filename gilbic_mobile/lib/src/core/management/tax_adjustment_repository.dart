import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/tax_adjustment.dart';
import 'package:gilbic_mobile/src/core/management/tax_value.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class TaxAdjustmentRepository {
  Future<TaxAdjustmentOverview> load(
    UserSession session, {
    required String deviceId,
    String adjustmentStatus = 'all',
    int limit = 100,
    int offset = 0,
  });
  Future<TaxAdjustmentItem> recordEvidence(
    UserSession session, {
    required String deviceId,
    required TaxAdjustmentCandidate candidate,
    required String idempotencyKey,
    required String adjustmentDate,
    required String adjustmentReference,
    required String evidenceReference,
    required String evidenceDigest,
    required String evidenceNote,
  });
  Future<TaxAdjustmentItem> prepare(
    UserSession session, {
    required String deviceId,
    required TaxAdjustmentItem item,
  });
  Future<TaxAdjustmentItem> post(
    UserSession session, {
    required String deviceId,
    required TaxAdjustmentItem item,
    required String confirmationToken,
  });
}

class SpinaTaxAdjustmentRepository implements TaxAdjustmentRepository {
  SpinaTaxAdjustmentRepository({http.Client? client})
    : _client = client ?? http.Client();
  final http.Client _client;

  @override
  Future<TaxAdjustmentOverview> load(
    UserSession session, {
    required String deviceId,
    String adjustmentStatus = 'all',
    int limit = 100,
    int offset = 0,
  }) async {
    if (!taxAdjustmentFilters.contains(adjustmentStatus) ||
        limit < 1 ||
        limit > 200 ||
        offset < 0) {
      throw ArgumentError('Invalid tax-adjustment page coordinates.');
    }
    final endpoint =
        ApiConfig.endpoint(
          '/api/mobile/v1/management/financial-accounting/tax/adjustments',
        ).replace(
          queryParameters: <String, String>{
            'adjustment_status': adjustmentStatus,
            'limit': '$limit',
            'offset': '$offset',
          },
        );
    return TaxAdjustmentOverview.fromPayload(
      await _request(
        () => _client.get(endpoint, headers: _headers(session, deviceId)),
      ),
    );
  }

  @override
  Future<TaxAdjustmentItem> recordEvidence(
    UserSession session, {
    required String deviceId,
    required TaxAdjustmentCandidate candidate,
    required String idempotencyKey,
    required String adjustmentDate,
    required String adjustmentReference,
    required String evidenceReference,
    required String evidenceDigest,
    required String evidenceNote,
  }) {
    _requireUuid(idempotencyKey, 'idempotencyKey');
    _requireDigest(evidenceDigest, 'evidenceDigest');
    final date = _date(adjustmentDate, 'adjustmentDate');
    if (date.isBefore(DateTime.parse(candidate.fiscalPeriodStart)) ||
        date.isAfter(DateTime.parse(candidate.fiscalPeriodEnd))) {
      throw ArgumentError('Adjustment date must stay in the original period.');
    }
    return _write(
      session,
      deviceId,
      '/api/mobile/v1/management/financial-accounting/tax/adjustments/evidence',
      <String, Object>{
        'idempotency_key': idempotencyKey,
        'tax_liability_posting_id': candidate.taxLiabilityPostingId,
        'replacement_evidence_id': candidate.replacementEvidenceId,
        'adjustment_kind': candidate.adjustmentKind,
        'adjustment_date': adjustmentDate,
        'adjustment_reference': _required(
          adjustmentReference,
          'adjustmentReference',
        ),
        'evidence_reference': _required(evidenceReference, 'evidenceReference'),
        'evidence_digest': evidenceDigest,
        'evidence_note': _note(evidenceNote),
      },
    );
  }

  @override
  Future<TaxAdjustmentItem> prepare(
    UserSession session, {
    required String deviceId,
    required TaxAdjustmentItem item,
  }) {
    item.requirePrepareCoordinates();
    return _write(
      session,
      deviceId,
      '/api/mobile/v1/management/financial-accounting/tax/adjustments/'
      '${Uri.encodeComponent(item.adjustmentEvidenceId)}/prepare',
      const <String, Object>{'confirm': true},
    );
  }

  @override
  Future<TaxAdjustmentItem> post(
    UserSession session, {
    required String deviceId,
    required TaxAdjustmentItem item,
    required String confirmationToken,
  }) {
    item.requirePostCoordinates();
    _requireDigest(confirmationToken, 'confirmationToken');
    return _write(
      session,
      deviceId,
      '/api/mobile/v1/management/financial-accounting/tax/adjustments/'
      '${Uri.encodeComponent(item.adjustmentEvidenceId)}/post',
      <String, Object>{
        'confirm': true,
        'confirmation_token': confirmationToken,
        'expected_evidence_digest': item.evidenceDigest,
        'expected_original_tax_due': item.originalTaxDue,
        'expected_replacement_tax_due': item.replacementTaxDue,
        'expected_adjustment_amount': item.adjustmentAmount,
        'expected_debit_account_code': item.debitAccountCode!,
        'expected_credit_account_code': item.creditAccountCode!,
        'expected_posting_date': item.adjustmentDate,
        'expected_fiscal_period_id': item.fiscalPeriodId!,
      },
    );
  }

  Future<TaxAdjustmentItem> _write(
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
    return TaxAdjustmentItem.fromPayload(stringMap(data['item']));
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
        'The protected tax-adjustment server could not be reached.',
        code: 'network_unavailable',
      );
    }
    late final Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable protected tax-adjustment data.',
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
