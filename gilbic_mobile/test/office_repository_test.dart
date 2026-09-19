import 'dart:convert';
import 'dart:typed_data';
import 'package:crypto/crypto.dart';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/office/office_repository.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const clientId = '11111111-1111-4111-8111-111111111111';
const versionId = '22222222-2222-4222-8222-222222222222';
const evidenceId = '33333333-3333-4333-8333-333333333333';
const requestId = '44444444-4444-4444-8444-444444444444';
final snapshotHash = List.filled(64, 'a').join();

OfficeIdentity actor({
  AppRole role = AppRole.employee,
  List<String>? permissions,
}) => OfficeIdentity(
  UserSession(
    userId: 'staff',
    username: 'staff',
    displayName: 'Staff',
    role: role,
    rawRole: role.name,
    accessToken: 'token',
    permissions: permissions ?? const ['client_onboarding.requirement.review'],
  ),
  'device',
);

void main() {
  test(
    'non-office roles and missing permission never send protected requests',
    () async {
      var calls = 0;
      final repository = OfficeRepository(
        client: MockClient((request) async {
          calls++;
          return http.Response('{}', 200);
        }),
      );
      for (final identity in [
        actor(role: AppRole.collector),
        actor(permissions: []),
      ]) {
        await expectLater(
          repository.loadCif(identity, clientId),
          throwsA(isA<SpinaApiException>()),
        );
      }
      expect(calls, 0);
    },
  );

  test(
    'CIF read uses active device and rejects another client response',
    () async {
      final repository = OfficeRepository(
        client: MockClient((request) async {
          expect(request.headers['Authorization'], 'Bearer token');
          expect(request.headers['X-Device-Id'], 'device');
          expect(
            request.url.queryParameters['include_identity_information'],
            'true',
          );
          return http.Response(
            jsonEncode({
              'client_id': versionId,
              'cif_version_id': versionId,
              'version_number': 1,
              'review_scope': 'cif_information_only',
              'status': 'draft',
              'full_name': 'Borrower',
              'phone_number': '09123456789',
              'email': null,
              'present_address': 'Office address',
            }),
            200,
          );
        }),
      );
      await expectLater(
        repository.loadCif(actor(), clientId),
        throwsA(isA<SpinaApiException>()),
      );
    },
  );

  test(
    'signed capture sends bytes, exact snapshot and stable request identity',
    () async {
      final bytes = Uint8List.fromList([137, 80, 78, 71, 13, 10, 26, 10]);
      final repository = OfficeRepository(
        client: MockClient((request) async {
          expect(request.method, 'POST');
          expect(request.bodyBytes, bytes);
          expect(request.headers['Content-Type'], 'image/png');
          expect(request.url.queryParameters['request_id'], requestId);
          expect(
            request.url.queryParameters['expected_snapshot_sha256'],
            snapshotHash,
          );
          expect(
            request.url.queryParameters['witnessed_wet_signature'],
            'true',
          );
          return http.Response(
            jsonEncode({
              'client_id': clientId,
              'cif_version_id': versionId,
              'application_id': null,
              'application_version_id': null,
              'purpose': 'cif_review',
              'snapshot_sha256': snapshotHash,
              'evidence_id': evidenceId,
              'evidence_reference': 'office-evidence:$evidenceId',
              'content_sha256': sha256.convert(bytes).toString(),
              'byte_count': bytes.length,
              'media_type': 'image/png',
            }),
            201,
          );
        }),
      );
      final record = await repository.captureReview(
        actor(),
        clientId,
        source: {'purpose': 'cif_review', 'cif_version_id': versionId},
        snapshotHash: snapshotHash,
        requestId: requestId,
        bytes: bytes,
        mediaType: 'image/png',
      );
      expect(record['evidence_reference'], 'office-evidence:$evidenceId');
    },
  );

  test(
    'capture rejects changed content metadata and evidence download requires its hash',
    () async {
      final bytes = Uint8List.fromList([137, 80, 78, 71, 13, 10, 26, 10]);
      final evidence = <String, dynamic>{
        'client_id': clientId,
        'cif_version_id': versionId,
        'purpose': 'cif_review',
        'snapshot_sha256': snapshotHash,
        'evidence_id': evidenceId,
        'evidence_reference': 'office-evidence:$evidenceId',
        'content_sha256': sha256.convert(bytes).toString(),
        'byte_count': bytes.length,
        'media_type': 'image/png',
      };
      for (final change in [
        {'content_sha256': snapshotHash},
        {'byte_count': 1},
        {'media_type': 'image/jpeg'},
      ]) {
        final repository = OfficeRepository(
          client: MockClient(
            (_) async =>
                http.Response(jsonEncode({...evidence, ...change}), 201),
          ),
        );
        await expectLater(
          repository.captureReview(
            actor(),
            clientId,
            source: {'purpose': 'cif_review', 'cif_version_id': versionId},
            snapshotHash: snapshotHash,
            requestId: requestId,
            bytes: bytes,
            mediaType: 'image/png',
          ),
          throwsA(isA<SpinaApiException>()),
        );
      }
      var calls = 0;
      final repository = OfficeRepository(
        client: MockClient((_) async {
          calls++;
          return http.Response.bytes(
            bytes,
            200,
            headers: {'content-type': 'image/png'},
          );
        }),
      );
      await expectLater(
        repository.downloadEvidence(actor(), clientId, {
          ...evidence,
          'content_sha256': null,
        }),
        throwsA(isA<SpinaApiException>()),
      );
      expect(calls, 0);
    },
  );

  test(
    'application amount stays exact text and new version uses expected version',
    () async {
      final repository = OfficeRepository(
        client: MockClient((request) async {
          final body = jsonDecode(request.body) as Map;
          expect(body['expected_version_number'], 3);
          expect(
            body['information']['request']['requested_amount'],
            '9007199254740993.01',
          );
          return http.Response(
            jsonEncode({
              'client_id': clientId,
              'application_id': evidenceId,
              'application_version_id': requestId,
              'cif_version_id': versionId,
              'version_number': 4,
              'review_scope': 'loan_application_information_only',
              'application_reference': 'APP-1',
              'information': body['information'],
              'missing_fields': [],
            }),
            200,
          );
        }),
      );
      await repository.saveApplication(
        actor(),
        clientId,
        reference: 'APP-1',
        cifVersionId: versionId,
        applicationId: evidenceId,
        expectedVersion: 3,
        information: {
          'request': {'requested_amount': '9007199254740993.01'},
          'repayment': {},
        },
      );
    },
  );

  test(
    'protected errors, non-documents and changed hashes never produce a file',
    () async {
      for (final response in [
        http.Response('{"detail":"Device revoked"}', 403),
        http.Response(
          '{"success":true}',
          200,
          headers: {'content-type': 'application/pdf'},
        ),
        http.Response(
          '%PDF-1.4 changed',
          200,
          headers: {'content-type': 'application/pdf'},
        ),
      ]) {
        final repository = OfficeRepository(
          client: MockClient((request) async => response),
        );
        await expectLater(
          repository.downloadPrivacy(
            actor(),
            clientId,
            versionId,
            'notice',
            snapshotHash,
          ),
          throwsA(isA<SpinaApiException>()),
        );
      }
    },
  );
}
