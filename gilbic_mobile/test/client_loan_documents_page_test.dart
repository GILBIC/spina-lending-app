import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_repository.dart';
import 'package:gilbic_mobile/src/features/client/client_loan_documents_page.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'client_documents_repository_test.dart' show session;
import 'client_payment_proofs_page_test.dart' show device;

void main() {
  testWidgets(
    'released packet and exact signed/release scans have distinct download actions',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1000, 1600));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      ClientDocumentFile? saved;
      final repository = SpinaClientDocumentRepository(
        client: MockClient((request) async {
          expect(request.headers['Authorization'], 'Bearer token');
          expect(request.headers['X-Device-Id'], 'device');
          if (request.url.path.endsWith('/documents')) {
            return http.Response(
              jsonEncode({
                'success': true,
                'data': {
                  'documents': [
                    {
                      'document_id': 'packet',
                      'kind': 'finalized_loan_packet',
                      'media_type': 'application/pdf',
                      'byte_count': 8,
                      'released_at': '2026-09-19',
                    },
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
          expect(
            request.url.path,
            '/api/mobile/v1/client/loans/loan-1/documents/signed',
          );
          return http.Response.bytes(
            [137, 80, 78, 71, 13, 10, 26, 10],
            200,
            headers: {'content-type': 'image/png'},
          );
        }),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: ClientLoanDocumentsPage(
            session: session,
            deviceIdentityProvider: device(),
            loanId: 'loan-1',
            loanNumber: 'LN-1',
            repository: repository,
            saver: (document) async {
              saved = document;
              return true;
            },
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Finalized loan packet'), findsOneWidget);
      expect(find.text('Signed loan contract'), findsOneWidget);
      expect(find.text('Cash release acknowledgment'), findsOneWidget);
      await tester.tap(find.text('Download signed loan contract'));
      await tester.pumpAndSettle();
      expect(saved?.mediaType, 'image/png');
      expect(saved?.filename, 'loan-document-loan-1-signed.png');
      expect(find.text('Document saved.'), findsOneWidget);
    },
  );

  testWidgets(
    'unavailable or unowned loan does not display a download action',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: ClientLoanDocumentsPage(
            session: session,
            deviceIdentityProvider: device(),
            loanId: 'other',
            loanNumber: 'Unknown',
            repository: SpinaClientDocumentRepository(
              client: MockClient(
                (_) async => http.Response(
                  jsonEncode({'detail': 'Loan not found.'}),
                  404,
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Loan not found.'), findsOneWidget);
      expect(find.textContaining('Download '), findsNothing);
    },
  );
}
