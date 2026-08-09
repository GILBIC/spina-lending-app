import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/contract_collection_activation.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class ContractCollectionActivationRepository {
  Future<ContractCollectionActivationData> load(
    UserSession session, {
    required String deviceId,
  });

  Future<ContractCollectionActivationLoan> activate(
    UserSession session, {
    required String deviceId,
    required String loanId,
    required String activationNote,
  });

  Future<ContractCollectionActivationLoan> deactivate(
    UserSession session, {
    required String deviceId,
    required String loanId,
    required String activationNote,
  });
}

class SpinaContractCollectionActivationRepository
    implements ContractCollectionActivationRepository {
  SpinaContractCollectionActivationRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<ContractCollectionActivationData> load(
    UserSession session, {
    required String deviceId,
  }) async {
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting/contract-collection-activation',
    );
    final payload = await _request(
      () => _client.get(endpoint, headers: _headers(session, deviceId)),
    );
    final data = stringMap(
      unwrapSpinaData(payload.data, statusCode: payload.statusCode),
    );
    return ContractCollectionActivationData.fromPayload(data);
  }

  @override
  Future<ContractCollectionActivationLoan> activate(
    UserSession session, {
    required String deviceId,
    required String loanId,
    required String activationNote,
  }) {
    return _changeState(
      session,
      deviceId: deviceId,
      loanId: loanId,
      activationNote: activationNote,
      action: 'activate',
    );
  }

  @override
  Future<ContractCollectionActivationLoan> deactivate(
    UserSession session, {
    required String deviceId,
    required String loanId,
    required String activationNote,
  }) {
    return _changeState(
      session,
      deviceId: deviceId,
      loanId: loanId,
      activationNote: activationNote,
      action: 'deactivate',
    );
  }

  Future<ContractCollectionActivationLoan> _changeState(
    UserSession session, {
    required String deviceId,
    required String loanId,
    required String activationNote,
    required String action,
  }) async {
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting/contract-collection-activation/$loanId/$action',
    );
    final payload = await _request(
      () => _client.post(
        endpoint,
        headers: _headers(session, deviceId, jsonBody: true),
        body: jsonEncode(<String, Object>{
          'activation_note': activationNote.trim(),
          'confirm_action': true,
        }),
      ),
    );
    final data = stringMap(
      unwrapSpinaData(payload.data, statusCode: payload.statusCode),
    );
    return ContractCollectionActivationLoan.fromPayload(data);
  }

  Map<String, String> _headers(
    UserSession session,
    String deviceId, {
    bool jsonBody = false,
  }) {
    return <String, String>{
      'Accept': 'application/json',
      if (jsonBody) 'Content-Type': 'application/json',
      'Authorization': 'Bearer ${session.accessToken}',
      'X-Session-Id': session.accessToken,
      'X-Device-Id': deviceId,
    };
  }

  Future<_Response> _request(Future<http.Response> Function() request) async {
    late final http.Response response;
    try {
      response = await request();
    } on Exception {
      throw const SpinaApiException(
        'Contract collection activation could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }

    late final Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable contract activation data.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return _Response(response.statusCode, payload);
    }

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
}

class _Response {
  const _Response(this.statusCode, this.data);

  final int statusCode;
  final Map<String, dynamic> data;
}
