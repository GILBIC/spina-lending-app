import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

class CollectorCashByAssignedCollector {
  const CollectorCashByAssignedCollector({
    required this.collectorUserId,
    required this.collectorName,
    required this.amount,
  });

  final String collectorUserId;
  final String collectorName;
  final double amount;

  factory CollectorCashByAssignedCollector.fromPayload(Object? value) {
    final data = stringMap(value);
    return CollectorCashByAssignedCollector(
      collectorUserId:
          firstNonEmptyString(<Object?>[data['collector_user_id']]) ?? '',
      collectorName:
          firstNonEmptyString(<Object?>[data['collector_name']]) ?? 'Collector',
      amount: firstNumber(<Object?>[data['amount']])?.toDouble() ?? 0,
    );
  }
}

class CollectorCashAccountability {
  const CollectorCashAccountability({
    required this.totalCashHeld,
    required this.readyToRemitAmount,
    required this.readyToRemitCount,
    required this.awaitingAcceptanceAmount,
    required this.awaitingAcceptanceCount,
    this.assignedAreaCashHeld = 0,
    this.otherAreaCashHeld = 0,
    this.otherAreaByCollector = const <CollectorCashByAssignedCollector>[],
  });

  final double totalCashHeld;
  final double assignedAreaCashHeld;
  final double otherAreaCashHeld;
  final List<CollectorCashByAssignedCollector> otherAreaByCollector;
  final double readyToRemitAmount;
  final int readyToRemitCount;
  final double awaitingAcceptanceAmount;
  final int awaitingAcceptanceCount;

  factory CollectorCashAccountability.fromPayload(Object? value) {
    final data = stringMap(value);
    final rawBreakdown = data['other_area_by_collector'];
    final breakdown = rawBreakdown is List
        ? rawBreakdown
            .map(CollectorCashByAssignedCollector.fromPayload)
            .where((item) => item.amount > 0)
            .toList(growable: false)
        : const <CollectorCashByAssignedCollector>[];
    return CollectorCashAccountability(
      totalCashHeld:
          firstNumber(<Object?>[data['total_cash_held']])?.toDouble() ?? 0,
      assignedAreaCashHeld:
          firstNumber(<Object?>[data['assigned_area_cash_held']])?.toDouble() ?? 0,
      otherAreaCashHeld:
          firstNumber(<Object?>[data['other_area_cash_held']])?.toDouble() ?? 0,
      otherAreaByCollector: breakdown,
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
