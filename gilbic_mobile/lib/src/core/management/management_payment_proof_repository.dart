import 'dart:convert';

import 'package:crypto/crypto.dart';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

const managementProofDecisions = [
  'reviewed',
  'correction_required',
  'rejected',
];

class ManagementProofVersion {
  ManagementProofVersion.fromPayload(Object? value) : this._(stringMap(value));
  ManagementProofVersion._(Map<String, dynamic> data)
    : versionId = _text(data, 'version_id'),
      number = _integer(data, 'version_number'),
      mediaType = _text(data, 'media_type'),
      byteCount = _integer(data, 'byte_count'),
      sha256 = _text(data, 'sha256'),
      uploadedAt = _text(data, 'uploaded_at'),
      note = data['note'] as String? ?? '' {
    if (!['application/pdf', 'image/png', 'image/jpeg'].contains(mediaType) ||
        byteCount > 10 * 1024 * 1024 ||
        !RegExp(r'^[0-9a-f]{64}$').hasMatch(sha256)) {
      throw _invalid();
    }
  }
  final String versionId, mediaType, sha256, uploadedAt, note;
  final int number, byteCount;
}

class ManagementProofReview {
  ManagementProofReview.fromPayload(Object? value) : this._(stringMap(value));
  ManagementProofReview._(Map<String, dynamic> data)
    : reviewId = _text(data, 'review_id'),
      decision = _text(data, 'decision'),
      reason = data['reason'] as String? ?? '',
      reviewedAt = _text(data, 'reviewed_at') {
    if (!managementProofDecisions.contains(decision)) throw _invalid();
  }
  final String reviewId, decision, reason, reviewedAt;
}

class ManagementPaymentProof {
  ManagementPaymentProof.fromPayload(Object? value) : this._(stringMap(value));
  ManagementPaymentProof._(Map<String, dynamic> data)
    : proofId = _text(data, 'proof_id'),
      loanId = _text(data, 'loan_id'),
      loanNumber = _text(data, 'loan_number'),
      loanTypeName = _text(data, 'loan_type_name'),
      clientName = _text(data, 'client_name'),
      clientCode = _text(data, 'client_code'),
      status = _text(data, 'status'),
      currentVersion = ManagementProofVersion.fromPayload(
        data['current_version'],
      ),
      latestReview = data['latest_review'] == null
          ? null
          : ManagementProofReview.fromPayload(data['latest_review']) {
    if (data['official_payment_posted'] != false ||
        status != (latestReview?.decision ?? 'under_review')) {
      throw _invalid();
    }
  }
  final String proofId,
      loanId,
      loanNumber,
      loanTypeName,
      clientName,
      clientCode,
      status;
  final ManagementProofVersion currentVersion;
  final ManagementProofReview? latestReview;
}

class ManagementProofHistory {
  ManagementProofHistory.fromPayload(Object? value) : this._(stringMap(value));
  ManagementProofHistory._(Map<String, dynamic> data)
    : version = ManagementProofVersion.fromPayload(data['version']),
      reviews = _list(
        data,
        'reviews',
      ).map(ManagementProofReview.fromPayload).toList(growable: false);
  final ManagementProofVersion version;
  final List<ManagementProofReview> reviews;
}

class ManagementProofDetail {
  ManagementProofDetail.fromPayload(Map<String, dynamic> data)
    : proof = ManagementPaymentProof.fromPayload(data['proof']),
      history = _list(
        data,
        'history',
      ).map(ManagementProofHistory.fromPayload).toList(growable: false) {
    final current = history
        .where((item) => item.version.number == proof.currentVersion.number)
        .toList();
    if (current.length != 1 ||
        current.single.version.versionId != proof.currentVersion.versionId ||
        current.single.version.sha256 != proof.currentVersion.sha256 ||
        history.map((item) => item.version.number).toSet().length !=
            history.length ||
        history.any(
          (item) => item.version.number > proof.currentVersion.number,
        ) ||
        (current.single.reviews.firstOrNull?.reviewId !=
            proof.latestReview?.reviewId)) {
      throw _invalid();
    }
  }
  final ManagementPaymentProof proof;
  final List<ManagementProofHistory> history;
}

class ManagementProofList {
  ManagementProofList.fromPayload(Map<String, dynamic> data)
    : proofs = _list(
        data,
        'proofs',
      ).map(ManagementPaymentProof.fromPayload).toList(growable: false),
      hasMore = data['has_more'] == true {
    if (data['has_more'] is! bool || (hasMore && proofs.isEmpty)) {
      throw _invalid();
    }
  }
  final List<ManagementPaymentProof> proofs;
  final bool hasMore;
}

class ManagementProofReviewAttempt {
  const ManagementProofReviewAttempt({
    required this.proofId,
    required this.requestId,
    required this.expectedVersion,
    required this.expectedReviewId,
    required this.decision,
    required this.reason,
  });
  final String proofId, requestId, decision, reason;
  final int expectedVersion;
  final String? expectedReviewId;
  Map<String, Object?> toPayload() => {
    'request_id': requestId,
    'expected_version': expectedVersion,
    'expected_review_id': expectedReviewId,
    'decision': decision,
    'reason': reason,
  };
}

abstract interface class ManagementPaymentProofRepository {
  Future<ManagementProofList> list(
    UserSession session, {
    required String deviceId,
    int offset = 0,
  });
  Future<ManagementProofDetail> load(
    UserSession session, {
    required String deviceId,
    required String proofId,
  });
  Future<ManagementProofDetail> review(
    UserSession session, {
    required String deviceId,
    required ManagementProofReviewAttempt attempt,
  });
  Future<ClientDocumentFile> download(
    UserSession session, {
    required String deviceId,
    required String proofId,
    required ManagementProofVersion version,
  });
}

class SpinaManagementPaymentProofRepository
    implements ManagementPaymentProofRepository {
  SpinaManagementPaymentProofRepository({http.Client? client})
    : _client = client ?? http.Client();
  final http.Client _client;
  static const _base = '/api/mobile/v1/management/payment-proofs';

  @override
  Future<ManagementProofList> list(
    UserSession session, {
    required String deviceId,
    int offset = 0,
  }) async => ManagementProofList.fromPayload(
    await _json(session, deviceId, '$_base?limit=50&offset=$offset'),
  );

  @override
  Future<ManagementProofDetail> load(
    UserSession session, {
    required String deviceId,
    required String proofId,
  }) async {
    final detail = ManagementProofDetail.fromPayload(
      await _json(session, deviceId, '$_base/${Uri.encodeComponent(proofId)}'),
    );
    if (detail.proof.proofId != proofId) throw _invalid();
    return detail;
  }

  @override
  Future<ManagementProofDetail> review(
    UserSession session, {
    required String deviceId,
    required ManagementProofReviewAttempt attempt,
  }) async {
    if (!managementProofDecisions.contains(attempt.decision) ||
        attempt.reason.length > 1000 ||
        (attempt.decision != 'reviewed' && attempt.reason.trim().isEmpty)) {
      throw const SpinaApiException(
        'A reason is required for correction or rejection.',
        statusCode: 422,
      );
    }
    final detail = ManagementProofDetail.fromPayload(
      await _json(
        session,
        deviceId,
        '$_base/${Uri.encodeComponent(attempt.proofId)}/reviews',
        body: attempt.toPayload(),
      ),
    );
    // An idempotent retry may return a later version; the immutable historical
    // version must still contain the submitted decision, even after new uploads.
    if (detail.proof.proofId != attempt.proofId ||
        !detail.history.any((item) {
          if (item.version.number != attempt.expectedVersion) return false;
          // Reviews arrive newest first. A matching older decision is not
          // evidence that this attempt, based on expectedReviewId, committed.
          final boundary = attempt.expectedReviewId == null
              ? item.reviews.length
              : item.reviews.indexWhere(
                  (review) => review.reviewId == attempt.expectedReviewId,
                );
          return boundary > 0 &&
              item.reviews
                  .take(boundary)
                  .any(
                    (review) =>
                        review.decision == attempt.decision &&
                        review.reason == attempt.reason,
                  );
        })) {
      throw _invalid();
    }
    return detail;
  }

  @override
  Future<ClientDocumentFile> download(
    UserSession session, {
    required String deviceId,
    required String proofId,
    required ManagementProofVersion version,
  }) async {
    final response = await _request(
      session,
      deviceId,
      '$_base/${Uri.encodeComponent(proofId)}/versions/${version.number}/content',
      accept: version.mediaType,
    );
    if (response.headers['content-type']?.split(';').first.trim() !=
            version.mediaType ||
        response.bodyBytes.length != version.byteCount ||
        sha256.convert(response.bodyBytes).toString() != version.sha256) {
      throw _invalid();
    }
    final extension = switch (version.mediaType) {
      'application/pdf' => 'pdf',
      'image/png' => 'png',
      _ => 'jpg',
    };
    return ClientDocumentFile(
      filename:
          'payment-proof-${proofId.replaceAll(RegExp(r"[^a-zA-Z0-9_-]"), '_')}-v${version.number}.$extension',
      bytes: response.bodyBytes,
      mediaType: version.mediaType,
    );
  }

  Future<Map<String, dynamic>> _json(
    UserSession session,
    String deviceId,
    String path, {
    Map<String, Object?>? body,
  }) async {
    final response = await _request(session, deviceId, path, body: body);
    try {
      return stringMap(
        unwrapSpinaData(
          decodeJsonObject(response.body),
          statusCode: response.statusCode,
        ),
      );
    } on Object {
      throw _invalid();
    }
  }

  Future<http.Response> _request(
    UserSession session,
    String deviceId,
    String path, {
    Map<String, Object?>? body,
    String accept = 'application/json',
  }) async {
    final headers = {
      'Accept': accept,
      'Authorization': 'Bearer ${session.accessToken}',
      'X-Device-Id': deviceId,
    };
    late final http.Response response;
    try {
      response =
          await (body == null
                  ? _client.get(ApiConfig.endpoint(path), headers: headers)
                  : _client.post(
                      ApiConfig.endpoint(path),
                      headers: {...headers, 'Content-Type': 'application/json'},
                      body: jsonEncode(body),
                    ))
              .timeout(const Duration(seconds: 45));
    } on Exception {
      throw const SpinaApiException(
        'The server result could not be confirmed. Retry the same review to check its result.',
        code: 'network_unavailable',
      );
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      Map<String, dynamic> payload = {};
      try {
        payload = decodeJsonObject(response.body);
      } on Object {
        /* Keep HTTP denial authoritative. */
      }
      final detail = stringMap(payload['detail']);
      throw SpinaApiException(
        firstNonEmptyString([
              detail['message'],
              payload['detail'] is String ? payload['detail'] : null,
              payload['message'],
            ]) ??
            'Payment evidence is unavailable. Refresh your authorized session and try again.',
        statusCode: response.statusCode,
      );
    }
    return response;
  }
}

SpinaApiException _invalid() => const SpinaApiException(
  'The server did not confirm complete payment-evidence data.',
  code: 'invalid_proof_response',
);
String _text(Map<String, dynamic> data, String key) {
  final value = data[key];
  if (value is String && value.isNotEmpty) return value;
  throw _invalid();
}

int _integer(Map<String, dynamic> data, String key) {
  final value = data[key];
  if (value is int && value > 0) return value;
  throw _invalid();
}

List<dynamic> _list(Map<String, dynamic> data, String key) {
  final value = data[key];
  if (value is List) return value;
  throw _invalid();
}
