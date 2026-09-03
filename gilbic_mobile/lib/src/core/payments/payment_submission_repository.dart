import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/payment_contract_version.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission.dart';
import 'package:http/http.dart' as http;

abstract interface class PaymentSubmissionRepository {
  Future<PaymentSubmissionResult> submit(
    UserSession session,
    PaymentSubmissionDraft draft,
  );
}

class SpinaPaymentSubmissionRepository
    implements PaymentSubmissionRepository {
  SpinaPaymentSubmissionRepository({
    http.Client? client,
    Uri? submissionUri,
  })  : _client = client ?? http.Client(),
        _submissionUri = submissionUri ?? ApiConfig.paymentSubmissionEndpoint;

  final http.Client _client;
  final Uri _submissionUri;

  @override
  Future<PaymentSubmissionResult> submit(
    UserSession session,
    PaymentSubmissionDraft draft,
  ) async {
    final validationError = draft.validate();
    if (validationError != null) {
      throw SpinaApiException(
        validationError,
        code: 'invalid_payment_draft',
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
        'The collection could not reach the SPINA server. Retry with the same transaction key.',
        code: 'network_unavailable',
      );
    }

    final payload = _decodeResponse(response);
    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = unwrapSpinaData(
        payload,
        statusCode: response.statusCode,
      );
      return PaymentSubmissionResult.fromPayload(
        data,
        idempotencyKey: draft.idempotencyKey,
        fallbackDisposition: PaymentSubmissionDisposition.accepted,
      );
    }

    if (response.statusCode == 409) {
      return PaymentSubmissionResult.fromPayload(
        payload.containsKey('data') ? payload['data'] : payload,
        idempotencyKey: draft.idempotencyKey,
        fallbackDisposition: PaymentSubmissionDisposition.conflict,
      );
    }

    if (response.statusCode == 400 || response.statusCode == 422) {
      final rejected = <String, dynamic>{
        ...stringMap(payload.containsKey('data') ? payload['data'] : payload),
      };
      final detailMessage = _validationDetailMessage(payload['detail']);
      if (firstNonEmptyString(<Object?>[rejected['message']]) == null &&
          detailMessage != null) {
        rejected['message'] = detailMessage;
      }
      final error = stringMap(payload['error']);
      if (firstNonEmptyString(<Object?>[rejected['code']]) == null) {
        rejected['code'] = firstNonEmptyString(<Object?>[
          error['code'],
          payload['code'],
          detailMessage == null ? null : 'request_validation_failed',
        ]);
      }
      return PaymentSubmissionResult.fromPayload(
        rejected,
        idempotencyKey: draft.idempotencyKey,
        fallbackDisposition: PaymentSubmissionDisposition.rejected,
      );
    }

    final error = stringMap(payload['error']);
    throw SpinaApiException(
      apiErrorMessage(payload, statusCode: response.statusCode),
      statusCode: response.statusCode,
      code: firstNonEmptyString(<Object?>[
        error['code'],
        payload['code'],
      ]),
    );
  }

  Map<String, dynamic> _decodeResponse(http.Response response) {
    try {
      return decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable collection data.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }
  }
}

String? _validationDetailMessage(Object? detail) {
  if (detail is String && detail.trim().isNotEmpty) {
    return detail.trim();
  }
  if (detail is! List || detail.isEmpty) {
    return null;
  }

  final first = stringMap(detail.first);
  final message = firstNonEmptyString(<Object?>[first['msg'], first['message']]);
  if (message == null) {
    return null;
  }

  final location = first['loc'];
  if (location is List && location.isNotEmpty) {
    final field = location.last.toString().trim();
    if (field.isNotEmpty && field != 'body') {
      return 'Payment request issue for $field: $message';
    }
  }
  return 'Payment request issue: $message';
}
