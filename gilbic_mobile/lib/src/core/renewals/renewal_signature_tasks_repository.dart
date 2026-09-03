import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

class RenewalSignatureTask {
  const RenewalSignatureTask({
    required this.signerId,
    required this.requestId,
    required this.partyRole,
    required this.fullName,
    required this.governmentIdVerified,
    required this.selfieVerified,
    required this.signed,
    required this.clientDecision,
    required this.status,
    required this.borrowerName,
    required this.loanNumber,
    required this.officeProcessingRequired,
  });

  final String signerId;
  final String requestId;
  final String partyRole;
  final String fullName;
  final bool governmentIdVerified;
  final bool selfieVerified;
  final bool signed;
  final String? clientDecision;
  final String status;
  final String borrowerName;
  final String loanNumber;
  final bool officeProcessingRequired;

  bool get borrowerAccepted => clientDecision == 'accepted';

  bool get readyToSign =>
      status == 'approved' &&
      borrowerAccepted &&
      governmentIdVerified &&
      selfieVerified &&
      !officeProcessingRequired &&
      !signed;

  factory RenewalSignatureTask.fromPayload(Map<String, dynamic> payload) {
    String requiredString(String key) {
      final value = firstNonEmptyString(<Object?>[payload[key]]);
      if (value == null) {
        throw SpinaApiException(
          'The Gilbic server omitted $key from a renewal signature task.',
          code: 'invalid_renewal_signature_payload',
        );
      }
      return value;
    }

    return RenewalSignatureTask(
      signerId: requiredString('signer_id'),
      requestId: requiredString('request_id'),
      partyRole: requiredString('party_role'),
      fullName: requiredString('full_name'),
      governmentIdVerified: payload['government_id_verified'] == true,
      selfieVerified: payload['selfie_verified'] == true,
      signed: payload['signed'] == true,
      clientDecision: firstNonEmptyString(<Object?>[payload['client_decision']]),
      status: requiredString('status').toLowerCase(),
      borrowerName: requiredString('borrower_name'),
      loanNumber: requiredString('loan_number'),
      officeProcessingRequired: payload['office_processing_required'] == true,
    );
  }
}

abstract interface class RenewalSignatureTasksRepository {
  Future<List<RenewalSignatureTask>> list(
    UserSession session, {
    required String deviceId,
  });

  Future<void> sign(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required String signerId,
  });
}

class SpinaRenewalSignatureTasksRepository
    implements RenewalSignatureTasksRepository {
  SpinaRenewalSignatureTasksRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<List<RenewalSignatureTask>> list(
    UserSession session, {
    required String deviceId,
  }) async {
    final payload = await _request(
      session,
      deviceId: deviceId,
      method: 'GET',
      uri: ApiConfig.endpoint('/api/mobile/v1/renewal-signatures/mine'),
    );
    final data = stringMap(unwrapSpinaData(payload));
    final raw = data['signatures'];
    if (raw is! List) {
      throw const SpinaApiException(
        'The Gilbic server returned incomplete renewal signature data.',
        code: 'invalid_renewal_signature_payload',
      );
    }
    return raw
        .map((item) => RenewalSignatureTask.fromPayload(stringMap(item)))
        .toList(growable: false);
  }

  @override
  Future<void> sign(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required String signerId,
  }) async {
    await _request(
      session,
      deviceId: deviceId,
      method: 'POST',
      uri: ApiConfig.endpoint(
        '/api/mobile/v1/renewals/${Uri.encodeComponent(requestId)}/signers/${Uri.encodeComponent(signerId)}/sign',
      ),
      body: const <String, Object?>{},
    );
  }

  Future<Map<String, dynamic>> _request(
    UserSession session, {
    required String deviceId,
    required String method,
    required Uri uri,
    Map<String, Object?>? body,
  }) async {
    late final http.Response response;
    final headers = <String, String>{
      'Accept': 'application/json',
      'Authorization': 'Bearer ${session.accessToken}',
      'X-Session-Id': session.accessToken,
      'X-Device-Id': deviceId,
    };
    try {
      if (method == 'GET') {
        response = await _client.get(uri, headers: headers);
      } else {
        headers['Content-Type'] = 'application/json';
        response = await _client.post(
          uri,
          headers: headers,
          body: jsonEncode(body ?? const <String, Object?>{}),
        );
      }
    } on Exception {
      throw const SpinaApiException(
        'Renewal signatures could not reach the Gilbic server.',
        code: 'network_unavailable',
      );
    }

    final payload = _decode(response);
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
    return payload;
  }

  Map<String, dynamic> _decode(http.Response response) {
    try {
      return decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The Gilbic server returned unreadable renewal signature data.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }
  }
}
