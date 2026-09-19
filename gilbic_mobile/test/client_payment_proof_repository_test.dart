import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/payments/client_payment_proof_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'client_documents_repository_test.dart' show session;

void main() {
  test(
    'a different loan or proof in a successful upload response stays uncertain',
    () async {
      final draft = PaymentProofDraft(
        filename: 'proof.png',
        mediaType: 'image/png',
        bytes: Uint8List.fromList([137, 80, 78, 71, 13, 10, 26, 10]),
      );
      for (final responseProof in [
        {...proof, 'loan_id': 'another-loan'},
        {...proof, 'proof_id': 'another-proof'},
      ]) {
        final repository = SpinaClientPaymentProofRepository(
          client: MockClient(
            (_) async => http.Response(
              jsonEncode({
                'success': true,
                'data': {...detail, 'proof': responseProof},
              }),
              201,
            ),
          ),
        );
        final future = responseProof['loan_id'] == 'another-loan'
            ? repository.upload(
                session,
                deviceId: 'device',
                loanId: 'loan-1',
                requestId: 'retry',
                note: '',
                draft: draft,
              )
            : repository.reupload(
                session,
                deviceId: 'device',
                proofId: 'proof-1',
                requestId: 'retry',
                expectedVersion: 1,
                note: '',
                draft: draft,
              );
        await expectLater(
          future,
          throwsA(
            isA<SpinaApiException>().having(
              (error) => error.statusCode,
              'uncertain status',
              isNull,
            ),
          ),
        );
      }
    },
  );

  test(
    'uploads raw evidence with stable request and optimistic version, never money',
    () async {
      final requests = <http.Request>[];
      final repository = SpinaClientPaymentProofRepository(
        client: MockClient((request) async {
          requests.add(request);
          expect(request.headers['Authorization'], 'Bearer token');
          expect(request.headers['X-Device-Id'], 'device');
          return http.Response(
            jsonEncode({'success': true, 'data': detail}),
            201,
          );
        }),
      );
      final draft = PaymentProofDraft(
        filename: 'proof.png',
        mediaType: 'image/png',
        bytes: Uint8List.fromList([137, 80, 78, 71, 13, 10, 26, 10]),
      );
      await repository.upload(
        session,
        deviceId: 'device',
        loanId: 'loan-1',
        requestId: 'retry-1',
        note: 'Reference 123',
        draft: draft,
      );
      await repository.reupload(
        session,
        deviceId: 'device',
        proofId: 'proof-1',
        requestId: 'retry-2',
        expectedVersion: 1,
        note: 'Corrected proof',
        draft: draft,
      );
      expect(requests[0].url.queryParameters, {
        'loan_id': 'loan-1',
        'request_id': 'retry-1',
      });
      expect(requests[1].url.queryParameters, {
        'request_id': 'retry-2',
        'expected_version': '1',
      });
      expect(
        utf8.decode(base64Decode(requests[0].headers['X-Proof-Note']!)),
        'Reference 123',
      );
      expect(
        utf8.decode(base64Decode(requests[1].headers['X-Proof-Note']!)),
        'Corrected proof',
      );
      expect(requests[0].headers['Content-Type'], 'image/png');
      expect(requests[0].bodyBytes, draft.bytes);
      expect(
        requests[1].url.path,
        '/api/mobile/v1/client/payment-proofs/proof-1/versions',
      );
    },
  );

  test(
    'capability defaults closed and preserves immutable review history',
    () async {
      final repository = SpinaClientPaymentProofRepository(
        client: MockClient(
          (request) async => http.Response(
            jsonEncode({
              'success': true,
              'data': request.url.path.endsWith('proof-1')
                  ? detail
                  : {
                      'proofs': [proof],
                      'has_more': false,
                    },
            }),
            200,
          ),
        ),
      );
      final list = await repository.list(session, deviceId: 'device');
      expect(list.uploadAvailable, false);
      final record = await repository.load(
        session,
        deviceId: 'device',
        proofId: 'proof-1',
      );
      expect(record.proof.status, 'correction_required');
      expect(record.proof.latestReview?.reason, 'Reference is not visible');
      expect(record.history.single.version.versionNumber, 1);
      expect(
        record.history.single.reviews.single.decision,
        'correction_required',
      );
    },
  );
}

final version = {
  'version_id': 'v1',
  'version_number': 1,
  'media_type': 'image/png',
  'byte_count': 8,
  'sha256': 'abc',
  'uploaded_at': '2026-09-19T00:00:00Z',
  'note': 'Original',
};
final review = {
  'review_id': 'r1',
  'decision': 'correction_required',
  'reason': 'Reference is not visible',
  'reviewed_at': '2026-09-19T01:00:00Z',
};
final proof = {
  'proof_id': 'proof-1',
  'loan_id': 'loan-1',
  'loan_number': 'LN-1',
  'loan_type_name': 'Regular',
  'status': 'correction_required',
  'current_version': version,
  'latest_review': review,
  'can_reupload': true,
  'official_payment_posted': false,
};
final detail = {
  'proof': proof,
  'history': [
    {
      'version': version,
      'reviews': [review],
    },
  ],
};
