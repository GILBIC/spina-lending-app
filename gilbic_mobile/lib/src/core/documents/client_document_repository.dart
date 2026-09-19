import 'dart:typed_data';

import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance_photo.dart';
import 'package:http/http.dart' as http;

class ClientDocument {
  const ClientDocument({
    required this.documentId,
    required this.byteCount,
    required this.releasedAt,
    required this.kind,
    required this.mediaType,
  });
  final String documentId;
  final int byteCount;
  final String releasedAt;
  final String kind;
  final String mediaType;
  String get label => switch (kind) {
    'signed_loan_contract' => 'Signed loan contract',
    'cash_release_acknowledgment' => 'Cash release acknowledgment',
    _ => 'Finalized loan packet',
  };
  factory ClientDocument.fromPayload(Object? value) {
    final data = stringMap(value);
    final id = data['document_id'];
    if (id is! String ||
        id.isEmpty ||
        !const {
          'application/pdf',
          'image/png',
          'image/jpeg',
        }.contains(data['media_type']) ||
        !const {
          'finalized_loan_packet',
          'signed_loan_contract',
          'cash_release_acknowledgment',
        }.contains(data['kind'])) {
      throw const SpinaApiException(
        'The server returned incomplete document information.',
      );
    }
    return ClientDocument(
      documentId: id,
      byteCount: (data['byte_count'] as num?)?.toInt() ?? 0,
      releasedAt: data['released_at'] as String? ?? '',
      kind: data['kind'] as String,
      mediaType: data['media_type'] as String,
    );
  }
}

class ClientDocumentFile {
  const ClientDocumentFile({
    required this.filename,
    required this.bytes,
    this.mediaType = 'application/pdf',
  });
  final String filename;
  final Uint8List bytes;
  final String mediaType;
}

abstract interface class ClientDocumentRepository {
  Future<List<ClientDocument>> listLoanDocuments(
    UserSession session, {
    required String deviceId,
    required String loanId,
  });
  Future<ClientDocumentFile> downloadLoanDocument(
    UserSession session, {
    required String deviceId,
    required String loanId,
    required String documentId,
  });
  Future<ClientDocumentFile> downloadStatement(
    UserSession session, {
    required String deviceId,
  });
  Future<ClientDocumentFile> downloadPaymentRecord(
    UserSession session, {
    required String deviceId,
    required String transactionId,
  });
}

class SpinaClientDocumentRepository implements ClientDocumentRepository {
  SpinaClientDocumentRepository({http.Client? client})
    : _client = client ?? http.Client();
  final http.Client _client;

  @override
  Future<List<ClientDocument>> listLoanDocuments(
    UserSession session, {
    required String deviceId,
    required String loanId,
  }) async {
    final response = await _get(
      session,
      deviceId,
      '/api/mobile/v1/client/loans/${Uri.encodeComponent(loanId)}/documents',
    );
    final data = stringMap(unwrapSpinaData(decodeJsonObject(response.body)));
    final documents = data['documents'];
    if (documents is! List) {
      throw const SpinaApiException(
        'The server returned incomplete document information.',
      );
    }
    return documents.map(ClientDocument.fromPayload).toList(growable: false);
  }

  @override
  Future<ClientDocumentFile> downloadLoanDocument(
    UserSession session, {
    required String deviceId,
    required String loanId,
    required String documentId,
  }) => _download(
    session,
    deviceId,
    '/api/mobile/v1/client/loans/${Uri.encodeComponent(loanId)}/documents/${Uri.encodeComponent(documentId)}',
    'loan-document-${_safeId(loanId)}-${_safeId(documentId)}',
    allowImages: true,
  );

  @override
  Future<ClientDocumentFile> downloadStatement(
    UserSession session, {
    required String deviceId,
  }) => _download(
    session,
    deviceId,
    '/api/mobile/v1/client/statement/document',
    'statement-of-account-record-copy.pdf',
  );

  @override
  Future<ClientDocumentFile> downloadPaymentRecord(
    UserSession session, {
    required String deviceId,
    required String transactionId,
  }) => _download(
    session,
    deviceId,
    '/api/mobile/v1/client/payments/${Uri.encodeComponent(transactionId)}/document',
    'payment-record-${_safeId(transactionId)}.pdf',
  );

  Future<ClientDocumentFile> _download(
    UserSession session,
    String deviceId,
    String path,
    String filename, {
    bool allowImages = false,
  }) async {
    final response = await _get(
      session,
      deviceId,
      path,
      accept: allowImages
          ? 'application/pdf,image/png,image/jpeg'
          : 'application/pdf',
    );
    final bytes = response.bodyBytes;
    final type = response.headers['content-type']?.split(';').first.trim();
    final isPdf =
        type == 'application/pdf' &&
        bytes.length >= 5 &&
        String.fromCharCodes(bytes.take(5)) == '%PDF-';
    final isImage =
        allowImages &&
        const {'image/png', 'image/jpeg'}.contains(type) &&
        RemittancePhotoDraft.detectContentType(bytes) == type;
    if (!isPdf && !isImage) {
      throw const SpinaApiException(
        'The server did not return a valid document.',
        code: 'invalid_document_response',
      );
    }
    final extension = switch (type) {
      'image/png' => 'png',
      'image/jpeg' => 'jpg',
      _ => 'pdf',
    };
    return ClientDocumentFile(
      filename: allowImages ? '$filename.$extension' : filename,
      bytes: bytes,
      mediaType: type!,
    );
  }

  Future<http.Response> _get(
    UserSession session,
    String deviceId,
    String path, {
    String accept = 'application/json',
  }) async {
    late final http.Response response;
    try {
      response = await _client
          .get(
            ApiConfig.endpoint(path),
            headers: {
              'Accept': accept,
              'Authorization': 'Bearer ${session.accessToken}',
              'X-Session-Id': session.accessToken,
              'X-Device-Id': deviceId,
            },
          )
          .timeout(const Duration(seconds: 45));
    } on Exception {
      throw const SpinaApiException(
        'Documents could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      Map<String, dynamic> payload = {};
      try {
        payload = decodeJsonObject(response.body);
      } on Object {
        /* Use safe fallback. */
      }
      final detail = stringMap(payload['detail']);
      throw SpinaApiException(
        firstNonEmptyString([
              detail['message'],
              payload['detail'] is String ? payload['detail'] : null,
              payload['message'],
            ]) ??
            'This document is not available. Refresh and try again.',
        statusCode: response.statusCode,
        code: firstNonEmptyString([detail['code'], payload['code']]),
      );
    }
    return response;
  }
}

String _safeId(String value) =>
    value.replaceAll(RegExp(r'[^a-zA-Z0-9_-]'), '_');
