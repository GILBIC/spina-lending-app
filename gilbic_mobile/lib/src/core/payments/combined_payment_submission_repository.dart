import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/combined_payment_submission.dart';
import 'package:gilbic_mobile/src/core/payments/payment_contract_version.dart';
import 'package:http/http.dart' as http;

abstract interface class CombinedPaymentSubmissionRepository {
  Future<CombinedPaymentSubmissionResult> submit(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  );
}

class SpinaCombinedPaymentSubmissionRepository
    implements CombinedPaymentSubmissionRepository {
  SpinaCombinedPaymentSubmissionRepository({
    http.Client? client,
    Uri? submissionUri,
  })  : _client = client ?? http.Client(),
        _submissionUri =
            submissionUri ?? ApiConfig.combinedPaymentSubmissionEndpoint;

  final http.Client _client;
  final Uri _submissionUri;

  @override
  Future<CombinedPaymentSubmissionResult> submit(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  ) async {
    final validationError = draft.validate();
    if (validationError != null) {
      throw SpinaApiException(
        validationError,
        code: 'invalid_combined_payment_draft',
      );
    }

    late final http.Response response;
    try {
      response = await _client.post(
        _submissionUri,
        headers: <String, String>{
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ${session.accessToken}',
          'X-Session-Id': session.accessToken,
          'Idempotency-Key': draft.idempotencyKey,
          'X-Client-Transaction-Id': draft.idempotencyKey,
          'X-Device-Id': draft.deviceId,
          'X-Gilbic-Contract-Version': PaymentContractVersion.value,
        },
        body: jsonEncode(draft.toJson()),
      );
    } on Exception {
      throw const SpinaApiException(
        'The combined payment could not reach the SPINA server. Retry with the same transaction key.',
        code: 'network_unavailable',
      );
    }

    final payload = _decodeResponse(response);
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return CombinedPaymentSubmissionResult.fromPayload(
        unwrapSpinaData(payload, statusCode: response.statusCode),
      );
    }

    final detail = _detailMessage(payload['detail']);
    throw SpinaApiException(
      detail ?? apiErrorMessage(payload, statusCode: response.statusCode),
      statusCode: response.statusCode,
      code: firstNonEmptyString(<Object?>[
        stringMap(payload['detail'])['code'],
        stringMap(payload['error'])['code'],
        payload['code'],
      ]),
    );
  }

  Map<String, dynamic> _decodeResponse(http.Response response) {
    try {
      return decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable combined payment data.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }
  }
}

String? _detailMessage(Object? detail) {
  if (detail is String && detail.trim().isNotEmpty) {
    return detail.trim();
  }
  final mapped = stringMap(detail);
  return firstNonEmptyString(<Object?>[mapped['message']]);
}
