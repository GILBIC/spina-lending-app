import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test(
    'released signed scans retain image media and safe unique filename',
    () async {
      final png = [137, 80, 78, 71, 13, 10, 26, 10];
      final repository = SpinaClientDocumentRepository(
        client: MockClient((request) async {
          if (request.url.path.endsWith('/documents')) {
            return http.Response(
              jsonEncode({
                'success': true,
                'data': {
                  'documents': [
                    {
                      'document_id': 'signed',
                      'kind': 'signed_loan_contract',
                      'media_type': 'image/png',
                      'byte_count': 8,
                      'released_at': '2026-09-19',
                    },
                    {
                      'document_id': 'cash',
                      'kind': 'cash_release_acknowledgment',
                      'media_type': 'image/jpeg',
                      'byte_count': 3,
                      'released_at': '2026-09-19',
                    },
                  ],
                },
              }),
              200,
            );
          }
          return http.Response.bytes(
            png,
            200,
            headers: {'content-type': 'image/png'},
          );
        }),
      );
      final documents = await repository.listLoanDocuments(
        session,
        deviceId: 'device',
        loanId: 'loan-1',
      );
      expect(documents.map((document) => document.label), [
        'Signed loan contract',
        'Cash release acknowledgment',
      ]);
      final file = await repository.downloadLoanDocument(
        session,
        deviceId: 'device',
        loanId: 'loan-1',
        documentId: 'signed',
      );
      expect(file.mediaType, 'image/png');
      expect(file.filename, 'loan-document-loan-1-signed.png');
      expect(file.bytes, png);
      await expectLater(
        repository.downloadStatement(session, deviceId: 'device'),
        throwsA(isA<SpinaApiException>()),
      );
    },
  );

  test(
    'document requests retain session/device protection and use bounded paths',
    () async {
      final paths = <String>[];
      final repository = SpinaClientDocumentRepository(
        client: MockClient((request) async {
          expect(request.headers['Authorization'], 'Bearer token');
          expect(request.headers['X-Session-Id'], 'token');
          expect(request.headers['X-Device-Id'], 'device');
          paths.add(request.url.path);
          if (request.url.path.endsWith('/documents')) {
            return http.Response(
              jsonEncode({
                'success': true,
                'data': {
                  'documents': [
                    {
                      'document_id': 'doc-1',
                      'kind': 'finalized_loan_packet',
                      'media_type': 'application/pdf',
                      'byte_count': 8,
                      'content_sha256': 'abc',
                      'generated_at': '2026-09-19T01:00:00Z',
                      'released_at': '2026-09-19T02:00:00Z',
                      'download_path': 'https://untrusted.example/never-use',
                    },
                  ],
                },
              }),
              200,
            );
          }
          return http.Response(
            '%PDF-1.7',
            200,
            headers: {'content-type': 'application/pdf'},
          );
        }),
      );
      final documents = await repository.listLoanDocuments(
        session,
        deviceId: 'device',
        loanId: 'loan-1',
      );
      expect(documents.single.documentId, 'doc-1');
      final file = await repository.downloadLoanDocument(
        session,
        deviceId: 'device',
        loanId: 'loan-1',
        documentId: 'doc-1',
      );
      expect(file.filename, 'loan-document-loan-1-doc-1.pdf');
      expect(utf8.decode(file.bytes), '%PDF-1.7');
      await repository.downloadStatement(session, deviceId: 'device');
      await repository.downloadPaymentRecord(
        session,
        deviceId: 'device',
        transactionId: 'payment-1',
      );
      expect(paths, [
        '/api/mobile/v1/client/loans/loan-1/documents',
        '/api/mobile/v1/client/loans/loan-1/documents/doc-1',
        '/api/mobile/v1/client/statement/document',
        '/api/mobile/v1/client/payments/payment-1/document',
      ]);
    },
  );

  test(
    'JSON errors and non-PDF success cannot become a saved document',
    () async {
      for (final response in [
        http.Response(
          jsonEncode({
            'detail': {'message': 'Not available', 'code': 'unavailable'},
          }),
          409,
        ),
        http.Response(
          '<html>Sign in</html>',
          200,
          headers: {'content-type': 'text/html'},
        ),
        http.Response(
          'not pdf',
          200,
          headers: {'content-type': 'application/pdf'},
        ),
      ]) {
        final repository = SpinaClientDocumentRepository(
          client: MockClient((_) async => response),
        );
        await expectLater(
          repository.downloadStatement(session, deviceId: 'device'),
          throwsA(isA<SpinaApiException>()),
        );
      }
    },
  );
}

const session = UserSession(
  userId: 'client',
  username: 'client',
  displayName: 'Client',
  role: AppRole.client,
  rawRole: 'Client',
  accessToken: 'token',
  permissions: [],
);
