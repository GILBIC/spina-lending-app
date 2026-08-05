import 'dart:typed_data';

import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class RemittancePhotoDraft {
  const RemittancePhotoDraft({
    required this.filename,
    required this.contentType,
    required this.bytes,
  });

  final String filename;
  final String contentType;
  final Uint8List bytes;

  String? validate() {
    if (bytes.isEmpty) {
      return 'The handover photo is empty.';
    }
    if (bytes.length > 5 * 1024 * 1024) {
      return 'The handover photo must be 5 MB or smaller.';
    }
    if (!const <String>{'image/jpeg', 'image/png', 'image/webp'}
        .contains(contentType)) {
      return 'Choose a JPEG, PNG, or WebP photo.';
    }
    return null;
  }

  static RemittancePhotoDraft fromBytes({
    required String filename,
    required Uint8List bytes,
    String? suggestedContentType,
  }) {
    final detected = detectContentType(bytes);
    final contentType = detected ?? suggestedContentType ?? '';
    return RemittancePhotoDraft(
      filename: filename.trim().isEmpty ? 'handover-photo' : filename.trim(),
      contentType: contentType,
      bytes: bytes,
    );
  }

  static String? detectContentType(Uint8List bytes) {
    if (bytes.length >= 3 &&
        bytes[0] == 0xff &&
        bytes[1] == 0xd8 &&
        bytes[2] == 0xff) {
      return 'image/jpeg';
    }
    if (bytes.length >= 8 &&
        bytes[0] == 0x89 &&
        bytes[1] == 0x50 &&
        bytes[2] == 0x4e &&
        bytes[3] == 0x47 &&
        bytes[4] == 0x0d &&
        bytes[5] == 0x0a &&
        bytes[6] == 0x1a &&
        bytes[7] == 0x0a) {
      return 'image/png';
    }
    if (bytes.length >= 12 &&
        bytes[0] == 0x52 &&
        bytes[1] == 0x49 &&
        bytes[2] == 0x46 &&
        bytes[3] == 0x46 &&
        bytes[8] == 0x57 &&
        bytes[9] == 0x45 &&
        bytes[10] == 0x42 &&
        bytes[11] == 0x50) {
      return 'image/webp';
    }
    return null;
  }
}

class RemittancePhotoUploadResult {
  const RemittancePhotoUploadResult({
    required this.photoId,
    required this.remittanceId,
    required this.version,
    required this.filename,
    required this.contentType,
    required this.byteSize,
    required this.sha256Hex,
    required this.uploadedAt,
    required this.photoUrl,
  });

  final String photoId;
  final String remittanceId;
  final int version;
  final String filename;
  final String contentType;
  final int byteSize;
  final String sha256Hex;
  final DateTime? uploadedAt;
  final String photoUrl;

  static RemittancePhotoUploadResult fromPayload(Object? value) {
    final data = stringMap(value);
    final photoId = firstNonEmptyString(<Object?>[data['photo_id'], data['id']]);
    final remittanceId =
        firstNonEmptyString(<Object?>[data['remittance_id']]);
    if (photoId == null || remittanceId == null) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete handover-photo data.',
        code: 'invalid_remittance_photo_response',
      );
    }
    return RemittancePhotoUploadResult(
      photoId: photoId,
      remittanceId: remittanceId,
      version: firstNumber(<Object?>[data['version']])?.toInt() ?? 1,
      filename:
          firstNonEmptyString(<Object?>[data['original_filename']]) ?? '',
      contentType:
          firstNonEmptyString(<Object?>[data['content_type']]) ?? 'image/jpeg',
      byteSize: firstNumber(<Object?>[data['byte_size']])?.toInt() ?? 0,
      sha256Hex:
          firstNonEmptyString(<Object?>[data['sha256_hex']]) ?? '',
      uploadedAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['uploaded_at']]) ?? '',
      ),
      photoUrl: firstNonEmptyString(<Object?>[data['photo_url']]) ??
          '/api/mobile/v1/remittances/$remittanceId/handover-photo',
    );
  }
}
