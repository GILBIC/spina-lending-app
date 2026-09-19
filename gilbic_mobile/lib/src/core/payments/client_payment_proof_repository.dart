import 'dart:typed_data';
import 'dart:convert';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

class PaymentProofDraft {
  const PaymentProofDraft({
    required this.filename,
    required this.mediaType,
    required this.bytes,
  });
  final String filename;
  final String mediaType;
  final Uint8List bytes;
}

class PaymentProofVersion {
  PaymentProofVersion.fromPayload(Object? value) : this._(stringMap(value));
  PaymentProofVersion._(Map<String, dynamic> data)
    : versionNumber = _integer(data, 'version_number'),
      mediaType = _text(data, 'media_type'),
      byteCount = _integer(data, 'byte_count'),
      uploadedAt = _text(data, 'uploaded_at'),
      note = data['note'] as String?;
  final int versionNumber;
  final String mediaType;
  final int byteCount;
  final String uploadedAt;
  final String? note;
}

class PaymentProofReview {
  PaymentProofReview.fromPayload(Object? value) : this._(stringMap(value));
  PaymentProofReview._(Map<String, dynamic> data)
    : decision = _text(data, 'decision'),
      reason = data['reason'] as String? ?? '',
      reviewedAt = _text(data, 'reviewed_at');
  final String decision;
  final String reason;
  final String reviewedAt;
}

class ClientPaymentProof {
  ClientPaymentProof.fromPayload(Object? value) : this._(stringMap(value));
  ClientPaymentProof._(Map<String, dynamic> data)
    : proofId = _text(data, 'proof_id'),
      loanId = _text(data, 'loan_id'),
      loanNumber = _text(data, 'loan_number'),
      loanTypeName = _text(data, 'loan_type_name'),
      status = _text(data, 'status'),
      currentVersion = PaymentProofVersion.fromPayload(data['current_version']),
      latestReview = data['latest_review'] == null
          ? null
          : PaymentProofReview.fromPayload(data['latest_review']),
      canReupload = data['can_reupload'] == true;
  final String proofId;
  final String loanId;
  final String loanNumber;
  final String loanTypeName;
  final String status;
  final PaymentProofVersion currentVersion;
  final PaymentProofReview? latestReview;
  final bool canReupload;
}

class PaymentProofHistoryEntry {
  PaymentProofHistoryEntry.fromPayload(Object? value)
    : this._(stringMap(value));
  PaymentProofHistoryEntry._(Map<String, dynamic> data)
    : version = PaymentProofVersion.fromPayload(data['version']),
      reviews = _list(
        data,
        'reviews',
      ).map(PaymentProofReview.fromPayload).toList(growable: false);
  final PaymentProofVersion version;
  final List<PaymentProofReview> reviews;
}

class PaymentProofDetail {
  PaymentProofDetail.fromPayload(Map<String, dynamic> data)
    : proof = ClientPaymentProof.fromPayload(data['proof']),
      history = _list(
        data,
        'history',
      ).map(PaymentProofHistoryEntry.fromPayload).toList(growable: false);
  final ClientPaymentProof proof;
  final List<PaymentProofHistoryEntry> history;
}

class PaymentProofList {
  PaymentProofList.fromPayload(Map<String, dynamic> data)
    : proofs = _list(
        data,
        'proofs',
      ).map(ClientPaymentProof.fromPayload).toList(growable: false),
      hasMore = data['has_more'] == true,
      uploadAvailable =
          stringMap(data['capability'])['upload_available'] == true &&
          stringMap(data['capability'])['posts_payment'] == false,
      allowedMediaTypes =
          (stringMap(data['capability'])['allowed_media_types'] as List?)
              ?.whereType<String>()
              .toList(growable: false) ??
          const [],
      maxBytes =
          (stringMap(data['capability'])['max_bytes'] as num?)?.toInt() ?? 0,
      message =
          stringMap(data['capability'])['message'] as String? ??
          'Payment proof uploads are not currently available.';
  final List<ClientPaymentProof> proofs;
  final bool hasMore;
  final bool uploadAvailable;
  final List<String> allowedMediaTypes;
  final int maxBytes;
  final String message;
}

abstract interface class ClientPaymentProofRepository {
  Future<PaymentProofList> list(
    UserSession session, {
    required String deviceId,
    int offset = 0,
  });
  Future<PaymentProofDetail> load(
    UserSession session, {
    required String deviceId,
    required String proofId,
  });
  Future<PaymentProofDetail> upload(
    UserSession session, {
    required String deviceId,
    required String loanId,
    required String requestId,
    required String note,
    required PaymentProofDraft draft,
  });
  Future<PaymentProofDetail> reupload(
    UserSession session, {
    required String deviceId,
    required String proofId,
    required String requestId,
    required int expectedVersion,
    required String note,
    required PaymentProofDraft draft,
  });
  Future<ClientDocumentFile> download(
    UserSession session, {
    required String deviceId,
    required String proofId,
    required PaymentProofVersion version,
  });
}

class SpinaClientPaymentProofRepository
    implements ClientPaymentProofRepository {
  SpinaClientPaymentProofRepository({http.Client? client})
    : _client = client ?? http.Client();
  final http.Client _client;
  static const _base = '/api/mobile/v1/client/payment-proofs';

  @override
  Future<PaymentProofList> list(
    UserSession session, {
    required String deviceId,
    int offset = 0,
  }) async => PaymentProofList.fromPayload(
    await _json(session, deviceId, '$_base?limit=50&offset=$offset'),
  );

  @override
  Future<PaymentProofDetail> load(
    UserSession session, {
    required String deviceId,
    required String proofId,
  }) async {
    final detail = PaymentProofDetail.fromPayload(
      await _json(session, deviceId, '$_base/${Uri.encodeComponent(proofId)}'),
    );
    _checkDetail(detail, proofId: proofId);
    return detail;
  }

  @override
  Future<PaymentProofDetail> upload(
    UserSession session, {
    required String deviceId,
    required String loanId,
    required String requestId,
    required String note,
    required PaymentProofDraft draft,
  }) async {
    final detail = PaymentProofDetail.fromPayload(
      await _json(
        session,
        deviceId,
        _withQuery(_base, {'loan_id': loanId, 'request_id': requestId}),
        draft: draft,
        note: note,
      ),
    );
    _checkDetail(detail, loanId: loanId);
    return detail;
  }

  @override
  Future<PaymentProofDetail> reupload(
    UserSession session, {
    required String deviceId,
    required String proofId,
    required String requestId,
    required int expectedVersion,
    required String note,
    required PaymentProofDraft draft,
  }) async {
    final detail = PaymentProofDetail.fromPayload(
      await _json(
        session,
        deviceId,
        _withQuery('$_base/${Uri.encodeComponent(proofId)}/versions', {
          'request_id': requestId,
          'expected_version': '$expectedVersion',
        }),
        draft: draft,
        note: note,
      ),
    );
    _checkDetail(detail, proofId: proofId);
    return detail;
  }

  @override
  Future<ClientDocumentFile> download(
    UserSession session, {
    required String deviceId,
    required String proofId,
    required PaymentProofVersion version,
  }) async {
    final response = await _request(
      session,
      deviceId,
      '$_base/${Uri.encodeComponent(proofId)}/versions/${version.versionNumber}/content',
      accept: version.mediaType,
    );
    final type = response.headers['content-type']?.split(';').first.trim();
    if (type != version.mediaType ||
        response.bodyBytes.isEmpty ||
        response.bodyBytes.length != version.byteCount) {
      throw const SpinaApiException(
        'The server returned incomplete proof content.',
      );
    }
    final extension = switch (type) {
      'application/pdf' => 'pdf',
      'image/png' => 'png',
      'image/jpeg' => 'jpg',
      _ => null,
    };
    if (extension == null) {
      throw const SpinaApiException('This proof file type cannot be saved.');
    }
    return ClientDocumentFile(
      filename:
          'payment-proof-${proofId.replaceAll(RegExp(r"[^a-zA-Z0-9_-]"), "_")}-v${version.versionNumber}.$extension',
      bytes: response.bodyBytes,
      mediaType: type!,
    );
  }

  Future<Map<String, dynamic>> _json(
    UserSession session,
    String deviceId,
    String path, {
    PaymentProofDraft? draft,
    String note = '',
  }) async {
    final response = await _request(
      session,
      deviceId,
      path,
      draft: draft,
      note: note,
    );
    try {
      return stringMap(
        unwrapSpinaData(
          decodeJsonObject(response.body),
          statusCode: response.statusCode,
        ),
      );
    } on SpinaApiException {
      rethrow;
    } on Object {
      throw const SpinaApiException(
        'The server returned unreadable proof data.',
      );
    }
  }

  Future<http.Response> _request(
    UserSession session,
    String deviceId,
    String path, {
    PaymentProofDraft? draft,
    String accept = 'application/json',
    String note = '',
  }) async {
    final headers = {
      'Accept': accept,
      'Authorization': 'Bearer ${session.accessToken}',
      'X-Session-Id': session.accessToken,
      'X-Device-Id': deviceId,
    };
    late final http.Response response;
    try {
      final request = draft == null
          ? _client.get(ApiConfig.endpoint(path), headers: headers)
          : _client.post(
              ApiConfig.endpoint(path),
              headers: {
                ...headers,
                'Content-Type': draft.mediaType,
                if (note.isNotEmpty)
                  'X-Proof-Note': base64Encode(utf8.encode(note)),
              },
              body: draft.bytes,
            );
      response = await request.timeout(const Duration(seconds: 45));
    } on Exception {
      throw const SpinaApiException(
        'Payment proofs could not reach the SPINA server. Retry the same upload to check its result.',
        code: 'network_unavailable',
      );
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      Map<String, dynamic> payload = {};
      try {
        payload = decodeJsonObject(response.body);
      } on Object {
        /* Safe fallback. */
      }
      final detail = stringMap(payload['detail']);
      throw SpinaApiException(
        firstNonEmptyString([
              detail['message'],
              payload['detail'] is String ? payload['detail'] : null,
              payload['message'],
            ]) ??
            'Payment proof could not be saved or loaded. Refresh and try again.',
        statusCode: response.statusCode,
        code: firstNonEmptyString([detail['code'], payload['code']]),
      );
    }
    return response;
  }
}

String _withQuery(String path, Map<String, String> query) =>
    '$path?${Uri(queryParameters: query).query}';
void _checkDetail(
  PaymentProofDetail detail, {
  String? proofId,
  String? loanId,
}) {
  if ((proofId != null && detail.proof.proofId != proofId) ||
      (loanId != null && detail.proof.loanId != loanId) ||
      !detail.history.any(
        (entry) =>
            entry.version.versionNumber ==
            detail.proof.currentVersion.versionNumber,
      )) {
    throw const SpinaApiException(
      'The server did not confirm this payment-proof request. Retry the same submission to check its result.',
      code: 'invalid_proof_response',
    );
  }
}

String _text(Map<String, dynamic> data, String key) {
  final value = data[key];
  if (value is String && value.isNotEmpty) return value;
  throw const SpinaApiException(
    'The server returned incomplete payment-proof data.',
  );
}

int _integer(Map<String, dynamic> data, String key) {
  final value = data[key];
  if (value is int && value >= 0) return value;
  throw const SpinaApiException(
    'The server returned incomplete payment-proof data.',
  );
}

List<dynamic> _list(Map<String, dynamic> data, String key) {
  final value = data[key];
  if (value is List) return value;
  throw const SpinaApiException(
    'The server returned incomplete payment-proof data.',
  );
}

String paymentProofStatusLabel(String status) => switch (status) {
  'under_review' => 'Under review',
  'reviewed' => 'Evidence reviewed',
  'correction_required' => 'Correction required',
  'rejected' => 'Rejected',
  _ => 'Review status unavailable',
};
