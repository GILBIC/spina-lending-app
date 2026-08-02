import 'dart:convert';
import 'dart:typed_data';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance_photo.dart';
import 'package:http/http.dart' as http;

abstract interface class RemittancePhotoRepository {
  Future<RemittancePhotoUploadResult> upload(
    UserSession session, {
    required String deviceId,
    required String remittanceId,
    required RemittancePhotoDraft draft,
  });

  Future<Uint8List> loadLatest(
    UserSession session, {
    required String deviceId,
    required String remittanceId,
  });
}

class SpinaRemittancePhotoRepository implements RemittancePhotoRepository {
  SpinaRemittancePhotoRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  @override
  Future<RemittancePhotoUploadResult> upload(
    UserSession session, {
    required String deviceId,
    required String remittanceId,
    required RemittancePhotoDraft draft,
  }) async {
    final validationError = draft.validate();
    if (validationError != null) {
      throw SpinaApiException(
        validationError,
        code: 'invalid_remittance_photo',
      );
    }

    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/collector/remittances/$remittanceId/handover-photo',
    );
    late final http.Response response;
    try {
      response = await _client.post(
        endpoint,
        headers: <String, String>{
          'Accept': 'application/json',
          'Content-Type': draft.contentType,
          'Authorization': 'Bearer ${session.accessToken}',
          'X-Session-Id': session.accessToken,
          'X-Device-Id': deviceId,
          'X-File-Name': draft.filename,
        },
        body: draft.bytes,
      );
    } on Exception {
      throw const SpinaApiException(
        'The handover photo could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }

    final payload = _decodeJson(response);
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return RemittancePhotoUploadResult.fromPayload(
        unwrapSpinaData(payload, statusCode: response.statusCode),
      );
    }

    throw _apiError(response, payload);
  }

  @override
  Future<Uint8List> loadLatest(
    UserSession session, {
    required String deviceId,
    required String remittanceId,
  }) async {
    final endpoint = ApiConfig.endpoint(
      '/api/mobile/v1/remittances/$remittanceId/handover-photo',
    );
    late final http.Response response;
    try {
      response = await _client.get(
        endpoint,
        headers: <String, String>{
          'Accept': 'image/jpeg,image/png,image/webp',
          'Authorization': 'Bearer ${session.accessToken}',
          'X-Session-Id': session.accessToken,
          'X-Device-Id': deviceId,
        },
      );
    } on Exception {
      throw const SpinaApiException(
        'The handover photo could not be loaded.',
        code: 'network_unavailable',
      );
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return response.bodyBytes;
    }

    Map<String, dynamic> payload;
    try {
      payload = _decodeJson(response);
    } on Object {
      throw SpinaApiException(
        'The handover photo could not be loaded.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }
    throw _apiError(response, payload);
  }

  Map<String, dynamic> _decodeJson(http.Response response) {
    try {
      return decodeJsonObject(utf8.decode(response.bodyBytes));
    } on Object {
      throw SpinaApiException(
        'The SPINA server returned unreadable handover-photo data.',
        statusCode: response.statusCode,
        code: 'invalid_server_response',
      );
    }
  }

  SpinaApiException _apiError(
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
