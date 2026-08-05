import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/client_registration_review.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class ClientRegistrationReviewRepository {
  Future<List<ClientRegistrationReview>> loadPending(
    UserSession session, {
    required String deviceId,
  });

  Future<List<ClientLinkCandidate>> searchCandidates(
    UserSession session, {
    required String deviceId,
    required String query,
  });

  Future<void> approve(
    UserSession session, {
    required String deviceId,
    required String userId,
    required String clientId,
    String reviewNote = '',
  });

  Future<void> reject(
    UserSession session, {
    required String deviceId,
    required String userId,
    required String reviewNote,
  });
}

class SpinaClientRegistrationReviewRepository
    implements ClientRegistrationReviewRepository {
  SpinaClientRegistrationReviewRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<List<ClientRegistrationReview>> loadPending(
    UserSession session, {
    required String deviceId,
  }) async {
    final data = stringMap(
      await _request(
        session,
        deviceId: deviceId,
        method: 'GET',
        uri: ApiConfig.managementClientRegistrationsEndpoint,
      ),
    );
    final values = data['registrations'];
    if (values is! Iterable) {
      return const <ClientRegistrationReview>[];
    }
    return values
        .map(ClientRegistrationReview.fromPayload)
        .whereType<ClientRegistrationReview>()
        .toList(growable: false);
  }

  @override
  Future<List<ClientLinkCandidate>> searchCandidates(
    UserSession session, {
    required String deviceId,
    required String query,
  }) async {
    final normalized = query.trim();
    if (normalized.length < 2) {
      return const <ClientLinkCandidate>[];
    }
    final data = stringMap(
      await _request(
        session,
        deviceId: deviceId,
        method: 'GET',
        uri: ApiConfig.managementClientCandidatesEndpoint(normalized),
      ),
    );
    final values = data['clients'];
    if (values is! Iterable) {
      return const <ClientLinkCandidate>[];
    }
    return values
        .map(ClientLinkCandidate.fromPayload)
        .whereType<ClientLinkCandidate>()
        .toList(growable: false);
  }

  @override
  Future<void> approve(
    UserSession session, {
    required String deviceId,
    required String userId,
    required String clientId,
    String reviewNote = '',
  }) async {
    await _request(
      session,
      deviceId: deviceId,
      method: 'POST',
      uri: ApiConfig.managementApproveClientRegistrationEndpoint(userId),
      body: <String, Object?>{
        'client_id': clientId,
        'review_note': reviewNote.trim(),
      },
    );
  }

  @override
  Future<void> reject(
    UserSession session, {
    required String deviceId,
    required String userId,
    required String reviewNote,
  }) async {
    await _request(
      session,
      deviceId: deviceId,
      method: 'POST',
      uri: ApiConfig.managementRejectClientRegistrationEndpoint(userId),
      body: <String, Object?>{'review_note': reviewNote.trim()},
    );
  }

  Future<Object?> _request(
    UserSession session, {
    required String deviceId,
    required String method,
    required Uri uri,
    Map<String, Object?>? body,
  }) async {
    final headers = <String, String>{
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ${session.accessToken}',
      'X-Session-Id': session.accessToken,
      'X-Device-Id': deviceId,
    };
    late final http.Response response;
    try {
      response = method == 'POST'
          ? await _client.post(
              uri,
              headers: headers,
              body: jsonEncode(body ?? const <String, Object?>{}),
            )
          : await _client.get(uri, headers: headers);
    } on Exception {
      throw const SpinaApiException(
        'Client approvals could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }

    Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable client approval data.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return unwrapSpinaData(payload, statusCode: response.statusCode);
    }

    throw SpinaApiException(
      apiErrorMessage(payload, statusCode: response.statusCode),
      statusCode: response.statusCode,
      code: firstNonEmptyString(<Object?>[
        stringMap(payload['error'])['code'],
        payload['code'],
      ]),
    );
  }
}
