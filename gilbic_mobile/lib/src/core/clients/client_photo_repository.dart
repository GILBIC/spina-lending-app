import 'dart:typed_data';

import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/office/office_repository.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance_photo.dart';
import 'package:http/http.dart' as http;

const clientPhotoMaxBytes = 5 * 1024 * 1024;

bool canManageClientPhoto(UserSession session) =>
    (session.hasRole(AppRole.employee) ||
        session.hasRole(AppRole.management)) &&
    session.hasPermission('client_onboarding.requirement.review');

void validateClientPhoto(Uint8List bytes, String contentType) {
  if (bytes.isEmpty || bytes.length > clientPhotoMaxBytes) {
    throw const SpinaApiException('Choose a photo no larger than 5 MiB.');
  }
  if (!['image/jpeg', 'image/png'].contains(contentType) ||
      RemittancePhotoDraft.detectContentType(bytes) != contentType) {
    throw const SpinaApiException('Choose a JPEG or PNG photo.');
  }
}

class ClientPhotoRecord {
  const ClientPhotoRecord({
    required this.clientId,
    required this.canUpload,
    this.photoId,
    this.version = 0,
    this.contentType,
    this.byteSize,
  });
  final String clientId;
  final bool canUpload;
  final String? photoId;
  final int version;
  final String? contentType;
  final int? byteSize;
}

/// Private transport only: photo bytes are never written to a local cache.
class ClientPhotoRepository {
  ClientPhotoRepository({http.Client? client})
    : _client = client ?? http.Client(),
      _ownsClient = client == null;
  final http.Client _client;
  final bool _ownsClient;

  String _path(String clientId) {
    officeCheck(officeUuid(clientId));
    return '/api/v1/clients/$clientId/photo';
  }

  Future<http.Response> _send(
    UserSession session,
    String deviceId,
    String path, {
    Uint8List? bytes,
    String? contentType,
  }) async {
    if (session.isExpired || session.accessToken.isEmpty || deviceId.isEmpty) {
      throw const SpinaApiException(
        'Sign in again to view this photo.',
        statusCode: 401,
      );
    }
    final request = http.Request(
      bytes == null ? 'GET' : 'POST',
      ApiConfig.endpoint(path),
    );
    request.followRedirects = false;
    request.headers.addAll({
      'Authorization': 'Bearer ${session.accessToken}',
      'X-Session-Id': session.accessToken,
      'X-Device-Id': deviceId,
      'Cache-Control': 'no-store',
      'Accept': 'application/json,image/jpeg,image/png',
      if (bytes != null) 'Content-Type': contentType!,
    });
    if (bytes != null) request.bodyBytes = Uint8List.fromList(bytes);
    late final http.Response response;
    try {
      response = await _client
          .send(request)
          .then(http.Response.fromStream)
          .timeout(const Duration(seconds: 45));
    } on Exception {
      throw const SpinaApiException(
        'The photo request could not reach the server.',
        code: 'network_unavailable',
      );
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw SpinaApiException(
        response.statusCode == 409
            ? 'The saved photo changed. Reload it before choosing a replacement.'
            : 'The photo is unavailable. Try again when access is restored.',
        statusCode: response.statusCode,
      );
    }
    return response;
  }

  ClientPhotoRecord _record(http.Response response, String clientId) {
    try {
      final envelope = decodeJsonObject(response.body);
      officeCheck(envelope['success'] == true && envelope['data'] is Map);
      final value = stringMap(envelope['data']);
      officeCheck(
        officeSame(value['client_id'], clientId) &&
            value['can_upload'] is bool &&
            value.containsKey('photo'),
      );
      if (value['photo'] == null) {
        return ClientPhotoRecord(
          clientId: clientId,
          canUpload: value['can_upload'],
        );
      }
      final photo = stringMap(value['photo']);
      final id = photo['photo_id'];
      officeCheck(
        officeUuid(id) &&
            photo['version'] is int &&
            photo['version'] > 0 &&
            ['image/jpeg', 'image/png'].contains(photo['content_type']) &&
            photo['byte_size'] is int &&
            photo['byte_size'] > 0 &&
            photo['byte_size'] <= clientPhotoMaxBytes &&
            photo['uploaded_at'] is String &&
            DateTime.tryParse(photo['uploaded_at']) != null &&
            officeUuid(photo['uploaded_by_user_id']) &&
            photo['content_url'] == '${_path(clientId)}/content?photo_id=$id',
      );
      return ClientPhotoRecord(
        clientId: clientId,
        canUpload: value['can_upload'],
        photoId: id,
        version: photo['version'],
        contentType: photo['content_type'],
        byteSize: photo['byte_size'],
      );
    } on Object {
      throw const SpinaApiException(
        'The photo response does not match this client. Reload the record.',
        code: 'invalid_client_photo',
      );
    }
  }

  Future<ClientPhotoRecord> load(
    UserSession session,
    String deviceId,
    String clientId,
  ) async => _record(await _send(session, deviceId, _path(clientId)), clientId);

  Future<Uint8List?> content(
    UserSession session,
    String deviceId,
    ClientPhotoRecord record,
  ) async {
    if (record.photoId == null) return null;
    officeCheck(officeUuid(record.photoId));
    final response = await _send(
      session,
      deviceId,
      '${_path(record.clientId)}/content?photo_id=${record.photoId}',
    );
    final type = response.headers['content-type']?.split(';').first.trim();
    officeCheck(
      type == record.contentType &&
          response.bodyBytes.length == record.byteSize,
    );
    validateClientPhoto(response.bodyBytes, type ?? '');
    return response.bodyBytes;
  }

  Future<ClientPhotoRecord> upload(
    UserSession session,
    String deviceId,
    String clientId, {
    required String requestId,
    required int expectedVersion,
    required Uint8List bytes,
    required String contentType,
  }) async {
    if (!canManageClientPhoto(session)) {
      throw const SpinaApiException(
        'Only authorized office staff can upload client photos.',
        statusCode: 403,
      );
    }
    officeCheck(officeUuid(requestId) && expectedVersion >= 0);
    validateClientPhoto(bytes, contentType);
    final record = _record(
      await _send(
        session,
        deviceId,
        '${_path(clientId)}?request_id=$requestId&expected_version=$expectedVersion',
        bytes: bytes,
        contentType: contentType,
      ),
      clientId,
    );
    officeCheck(record.photoId != null && record.version > expectedVersion);
    return record;
  }

  void close() {
    if (_ownsClient) _client.close();
  }
}
