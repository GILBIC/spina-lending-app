import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

class CollectorCashAccountability {
  const CollectorCashAccountability({
    required this.totalCashHeld,
    required this.readyToRemitAmount,
    required this.readyToRemitCount,
    required this.awaitingAcceptanceAmount,
    required this.awaitingAcceptanceCount,
  });

  final double totalCashHeld;
  final double readyToRemitAmount;
  final int readyToRemitCount;
  final double awaitingAcceptanceAmount;
  final int awaitingAcceptanceCount;

  factory CollectorCashAccountability.fromPayload(Object? value) {
    final data = stringMap(value);
    return CollectorCashAccountability(
      totalCashHeld:
          firstNumber(<Object?>[data['total_cash_held']])?.toDouble() ?? 0,
      readyToRemitAmount:
          firstNumber(<Object?>[data['ready_to_remit_amount']])?.toDouble() ?? 0,
      readyToRemitCount:
          firstNumber(<Object?>[data['ready_to_remit_count']])?.toInt() ?? 0,
      awaitingAcceptanceAmount: firstNumber(
            <Object?>[data['awaiting_acceptance_amount']],
          )?.toDouble() ??
          0,
      awaitingAcceptanceCount: firstNumber(
            <Object?>[data['awaiting_acceptance_count']],
          )?.toInt() ??
          0,
    );
  }
}

abstract interface class CollectorCashAccountabilityRepository {
  Future<CollectorCashAccountability> load(
    UserSession session, {
    required String deviceId,
  });
}

class SpinaCollectorCashAccountabilityRepository
    implements CollectorCashAccountabilityRepository {
  SpinaCollectorCashAccountabilityRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<CollectorCashAccountability> load(
    UserSession session, {
    required String deviceId,
  }) async {
    late final http.Response response;
    try {
      response = await _client.get(
        ApiConfig.endpoint('/api/mobile/v1/collector/cash-accountability'),
        headers: <String, String>{
          'Accept': 'application/json',
          'Authorization': 'Bearer ${session.accessToken}',
          'X-Session-Id': session.accessToken,
          'X-Device-Id': deviceId,
        },
      );
    } on Exception {
      throw const SpinaApiException(
        'Collector cash accountability could not reach the Gilbic server.',
        code: 'network_unavailable',
      );
    }

    Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(utf8.decode(response.bodyBytes));
    } on Object {
      throw SpinaApiException(
        'The Gilbic server returned unreadable cash accountability data.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = stringMap(payload['detail']);
      throw SpinaApiException(
        firstNonEmptyString(<Object?>[
              detail['message'],
              payload['message'],
            ]) ??
            apiErrorMessage(payload, statusCode: response.statusCode),
        statusCode: response.statusCode,
        code: firstNonEmptyString(<Object?>[
          detail['code'],
          payload['code'],
        ]),
      );
    }

    return CollectorCashAccountability.fromPayload(
      unwrapSpinaData(payload, statusCode: response.statusCode),
    );
  }
}
