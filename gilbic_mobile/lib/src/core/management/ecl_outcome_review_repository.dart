import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/management/ecl_outcome_review.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

abstract interface class EclOutcomeReviewRepository {
  Future<EclOutcomeReviewQueueData> loadQueue(
    UserSession session, {
    required String deviceId,
    String status = 'pending',
    int limit = 100,
    int offset = 0,
  });

  Future<EclOutcomeReviewEpisode> reviewOutcome(
    UserSession session, {
    required String deviceId,
    required int historicalEpisodeId,
    required bool defaultLabel,
    required String evidenceBasis,
    required String evidenceReference,
    required String reviewNote,
  });
}

class SpinaEclOutcomeReviewRepository implements EclOutcomeReviewRepository {
  SpinaEclOutcomeReviewRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<EclOutcomeReviewQueueData> loadQueue(
    UserSession session, {
    required String deviceId,
    String status = 'pending',
    int limit = 100,
    int offset = 0,
  }) async {
    final base = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting/ecl-outcome-review',
    );
    final endpoint = base.replace(queryParameters: <String, String>{
      'review_status': status,
      'limit': '$limit',
      'offset': '$offset',
    });
    final payload = await _request(
      () => _client.get(endpoint, headers: _headers(session, deviceId)),
    );
    final data = stringMap(
      unwrapSpinaData(payload.data, statusCode: payload.statusCode),
    );
    return EclOutcomeReviewQueueData.fromPayload(data);
  }

  @override
  Future<EclOutcomeReviewEpisode> reviewOutcome(
    UserSession session, {
    required String deviceId,
    required int historicalEpisodeId,
    required bool defaultLabel,
    required String evidenceBasis,
    required String evidenceReference,
    required String reviewNote,
  }) async {
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/management/financial-accounting/ecl-outcome-review/$historicalEpisodeId',
    );
    final payload = await _request(
      () => _client.post(
        endpoint,
        headers: _headers(session, deviceId, jsonBody: true),
        body: jsonEncode(<String, Object>{
          'default_label': defaultLabel,
          'evidence_basis': evidenceBasis,
          'evidence_reference': evidenceReference.trim(),
          'review_note': reviewNote.trim(),
        }),
      ),
    );
    final data = stringMap(
      unwrapSpinaData(payload.data, statusCode: payload.statusCode),
    );
    return EclOutcomeReviewEpisode.fromPayload(data);
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
        'Historical outcome review could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }

    late final Map<String, dynamic> payload;
    try {
      payload = decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable historical outcome-review data.',
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
