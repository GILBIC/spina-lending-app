import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/collection_correction.dart';
import 'package:http/http.dart' as http;

abstract interface class CollectionCorrectionRepository {
  Future<CollectionCorrectionResult> correct(
    UserSession session, {
    required String deviceId,
    required CollectionCorrectionDraft draft,
  });
}

class SpinaCollectionCorrectionRepository
    implements CollectionCorrectionRepository {
  SpinaCollectionCorrectionRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<CollectionCorrectionResult> correct(
    UserSession session, {
    required String deviceId,
    required CollectionCorrectionDraft draft,
  }) async {
    final validationError = draft.validate();
    if (validationError != null) {
      throw SpinaApiException(
        validationError,
        code: 'invalid_correction_draft',
      );
    }

    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/collector/collections/${draft.transactionId}',
    );
    late final http.Response response;
    try {
      response = await _client.patch(
        endpoint,
        headers: <String, String>{
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ${session.accessToken}',
          'X-Session-Id': session.accessToken,
          'X-Device-Id': deviceId,
        },
        body: jsonEncode(draft.toJson()),
      );
    } on Exception {
      throw const SpinaApiException(
        'The correction could not reach the SPINA server. Check the connection and try again.',
        code: 'network_unavailable',
      );
    }

    final payload = _decodeResponse(response);
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return CollectionCorrectionResult.fromPayload(
        unwrapSpinaData(payload, statusCode: response.statusCode),
      );
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

  Map<String, dynamic> _decodeResponse(http.Response response) {
    try {
      return decodeJsonObject(response.body);
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable correction data.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }
  }
}
