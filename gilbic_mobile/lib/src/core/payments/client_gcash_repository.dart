import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/client_gcash.dart';
import 'package:http/http.dart' as http;

abstract interface class ClientGcashRepository {
  Future<ClientGcashCapability> loadCapability(
    UserSession session, {
    required String deviceId,
  });

  Future<ClientGcashIntent> createIntent(
    UserSession session, {
    required String deviceId,
    required String idempotencyKey,
    required List<ClientGcashAllocation> allocations,
  });

  Future<ClientGcashIntent> loadIntent(
    UserSession session, {
    required String deviceId,
    required String intentId,
  });
}

class SpinaClientGcashRepository implements ClientGcashRepository {
  SpinaClientGcashRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<ClientGcashCapability> loadCapability(
    UserSession session, {
    required String deviceId,
  }) async {
    final endpoint = ApiConfig.endpoint('/api/mobile/v1/client/gcash/config');
    final response = await _send(
      () => _client.get(endpoint, headers: _headers(session, deviceId)),
      networkMessage: 'GCash could not reach the SPINA server.',
    );
    final payload = _payload(response, context: 'GCash configuration');
    if (_successful(response)) {
      return ClientGcashCapability.fromPayload(
        stringMap(unwrapSpinaData(payload, statusCode: response.statusCode)),
      );
    }
    throw _error(response, payload);
  }

  @override
  Future<ClientGcashIntent> createIntent(
    UserSession session, {
    required String deviceId,
    required String idempotencyKey,
    required List<ClientGcashAllocation> allocations,
  }) async {
    final endpoint =
        ApiConfig.endpoint('/api/mobile/v1/client/gcash/payment-intents');
    final response = await _send(
      () => _client.post(
        endpoint,
        headers: <String, String>{
          ..._headers(session, deviceId),
          'Content-Type': 'application/json',
        },
        body: jsonEncode(<String, dynamic>{
          'idempotency_key': idempotencyKey,
          'allocations': allocations
              .map((allocation) => allocation.toPayload())
              .toList(growable: false),
        }),
      ),
      networkMessage: 'GCash payment could not reach the SPINA server.',
    );
    final payload = _payload(response, context: 'GCash checkout');
    if (_successful(response)) {
      return ClientGcashIntent.fromPayload(
        stringMap(unwrapSpinaData(payload, statusCode: response.statusCode)),
      );
    }
    throw _error(response, payload);
  }

  @override
  Future<ClientGcashIntent> loadIntent(
    UserSession session, {
    required String deviceId,
    required String intentId,
  }) async {
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/client/gcash/payment-intents/$intentId',
    );
    final response = await _send(
      () => _client.get(endpoint, headers: _headers(session, deviceId)),
      networkMessage: 'GCash status could not reach the SPINA server.',
    );
    final payload = _payload(response, context: 'GCash payment status');
    if (_successful(response)) {
      return ClientGcashIntent.fromPayload(
        stringMap(unwrapSpinaData(payload, statusCode: response.statusCode)),
      );
    }
    throw _error(response, payload);
  }

  Map<String, String> _headers(UserSession session, String deviceId) =>
      <String, String>{
        'Accept': 'application/json',
        'Authorization': 'Bearer ${session.accessToken}',
        'X-Session-Id': session.accessToken,
        'X-Device-Id': deviceId,
      };

  Future<http.Response> _send(
    Future<http.Response> Function() request, {
    required String networkMessage,
  }) async {
    try {
      return await request();
    } on Exception {
      throw SpinaApiException(
        networkMessage,
        code: 'network_unavailable',
      );
    }
  }

  Map<String, dynamic> _payload(
    http.Response response, {
    required String context,
  }) {
    try {
      return decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned an unreadable $context response.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }
  }

  bool _successful(http.Response response) =>
      response.statusCode >= 200 && response.statusCode < 300;

  SpinaApiException _error(
    http.Response response,
    Map<String, dynamic> payload,
  ) {
    final detail = payload['detail'];
    final detailMap = stringMap(detail);
    return SpinaApiException(
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
}
