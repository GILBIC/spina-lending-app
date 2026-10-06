import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/request_money.dart';
import 'package:http/http.dart' as http;

abstract interface class CollectionPaymentUndoRepository {
  Future<void> undo(
    UserSession session, {
    required String deviceId,
    required String transactionId,
    required String loanId,
    required String expectedRouteRevision,
    required String reason,
  });
}

class SpinaCollectionPaymentUndoRepository
    implements CollectionPaymentUndoRepository {
  SpinaCollectionPaymentUndoRepository({http.Client? client})
    : _client = client ?? http.Client();
  final http.Client _client;

  @override
  Future<void> undo(
    UserSession session, {
    required String deviceId,
    required String transactionId,
    required String loanId,
    required String expectedRouteRevision,
    required String reason,
  }) async {
    final version = int.tryParse(
      expectedRouteRevision.split(':').last.replaceFirst('v', ''),
    );
    if (transactionId.trim().isEmpty ||
        deviceId.trim().isEmpty ||
        version == null ||
        version < 0 ||
        expectedRouteRevision != 'loan:$loanId:v$version' ||
        reason.trim().length < 3 ||
        reason.trim().length > 500) {
      throw const SpinaApiException(
        'Refresh the route and enter a reason before undoing this payment.',
        code: 'invalid_undo_request',
      );
    }
    late final http.Response response;
    try {
      response = await _client
          .post(
            ApiConfig.endpoint(
              '/api/mobile/v1/collector/collections/$transactionId/undo-payment',
            ),
            headers: {
              'Accept': 'application/json',
              'Content-Type': 'application/json',
              'Authorization': 'Bearer ${session.accessToken}',
              'X-Session-Id': session.accessToken,
              'X-Device-Id': deviceId,
            },
            body: jsonEncode({
              'reason': reason.trim(),
              'expected_route_revision': expectedRouteRevision,
            }),
          )
          .timeout(const Duration(seconds: 30));
    } on Exception {
      throw const SpinaApiException(
        'Undo result is not confirmed. Retry the same undo or refresh the route.',
        code: 'undo_unconfirmed',
      );
    }
    Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'Undo result is not confirmed. Refresh the route.',
        statusCode: response.statusCode,
        code: 'undo_unconfirmed',
      );
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = stringMap(payload['detail']);
      throw SpinaApiException(
        detail['message']?.toString() ??
            'The payment could not be undone. Refresh the route.',
        statusCode: response.statusCode,
        code: detail['code']?.toString(),
      );
    }
    final data = stringMap(
      unwrapSpinaData(payload, statusCode: response.statusCode),
    );
    final balance = requestMoneyCents(data['restored_balance']);
    if (data['transaction_id'] != transactionId ||
        data['loan_id'] != loanId ||
        data['route_revision'] != 'loan:$loanId:v${version + 1}' ||
        data['receipt_number'] is! String ||
        (data['receipt_number'] as String).trim().isEmpty ||
        DateTime.tryParse(data['voided_at']?.toString() ?? '') == null ||
        balance == null ||
        balance < BigInt.zero) {
      throw const SpinaApiException(
        'Undo result is not confirmed. Refresh the route.',
        code: 'undo_unconfirmed',
      );
    }
  }
}
