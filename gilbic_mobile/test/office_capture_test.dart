import 'dart:convert';
import 'package:crypto/crypto.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/office/office_repository.dart';
import 'package:gilbic_mobile/src/features/office/office_review_capture_page.dart';
import 'package:gilbic_mobile/src/features/office/office_widgets.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const clientId = '11111111-1111-4111-8111-111111111111';
const cifId = '22222222-2222-4222-8222-222222222222';
const evidenceId = '33333333-3333-4333-8333-333333333333';
final hash = List.filled(64, 'a').join();
final png = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
);
OfficeIdentity identity() => OfficeIdentity(
  const UserSession(
    userId: 'employee',
    username: 'employee',
    displayName: 'Employee',
    role: AppRole.employee,
    rawRole: 'employee',
    accessToken: 'token',
    permissions: ['client_onboarding.requirement.review'],
  ),
  'device',
);
OfficeRecord source({bool privacy = false}) => {
  'purpose': privacy ? 'privacy_acknowledgment' : 'cif_review',
  'cif_version_id': cifId,
};
OfficeRecord contextRecord({bool privacy = false, bool optional = false}) => {
  ...source(privacy: privacy),
  'client_id': clientId,
  'application_id': null,
  'application_version_id': null,
  'snapshot_sha256': hash,
  'issuable': true,
  'review_snapshot': {
    'client_id': clientId,
    'cif_version_id': cifId,
    'information': {'full_name': 'Named Borrower'},
    if (privacy) ...{
      'optional_service_communications': optional,
      'notice': {'version': 'N1', 'sha256': hash},
      'consent': {'version': 'C1', 'sha256': hash},
    },
  },
};
OfficeRecord captured({bool privacy = false}) => {
  ...source(privacy: privacy),
  'client_id': clientId,
  'application_id': null,
  'application_version_id': null,
  'snapshot_sha256': hash,
  'evidence_id': evidenceId,
  'evidence_reference': 'office-evidence:$evidenceId',
  'media_type': 'image/png',
  'content_sha256': sha256.convert(png).toString(),
  'byte_count': png.length,
};
http.Response json(Object? value, [int status = 200]) => http.Response(
  jsonEncode(value),
  status,
  headers: {'content-type': 'application/json'},
);
Future<void> reveal(WidgetTester tester, Finder finder) async {
  await tester.scrollUntilVisible(
    finder,
    200,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'uncertain privacy acknowledgment reuses the saved signed evidence',
    (tester) async {
      var captures = 0;
      final acknowledgments = <http.Request>[];
      await tester.pumpWidget(
        MaterialApp(
          home: OfficeReviewCapturePage(
            actor: identity(),
            clientId: clientId,
            source: source(privacy: true),
            privacy: true,
            repository: OfficeRepository(
              client: MockClient((request) async {
                if (request.method == 'GET') {
                  return json(contextRecord(privacy: true));
                }
                if (request.url.path.endsWith('/review-evidence')) {
                  captures++;
                  return json(captured(privacy: true), 201);
                }
                acknowledgments.add(request);
                if (acknowledgments.length == 1) {
                  return json({'detail': 'Reply lost'}, 503);
                }
                return json({
                  'client_id': clientId,
                  'cif_version_id': cifId,
                  'evidence_id': evidenceId,
                  'optional_service_communications': false,
                  'notice_version': 'N1',
                  'notice_sha256': hash,
                  'consent_version': 'C1',
                  'consent_sha256': hash,
                });
              }),
            ),
            picker: (_) async => OfficePhoto(png, 'image/png'),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await reveal(tester, find.text('Gallery'));
      await tester.tap(find.text('Gallery'));
      await tester.pumpAndSettle();
      final witness = find.text(
        'I witnessed the applicant review these exact privacy documents and sign with the optional choice shown.',
      );
      await reveal(tester, witness);
      await tester.tap(witness);
      await tester.pumpAndSettle();
      final save = find.text('Record privacy acknowledgment');
      await reveal(tester, save);
      final callback = tester
          .widget<FilledButton>(
            find.ancestor(of: save, matching: find.byType(FilledButton)),
          )
          .onPressed!;
      callback();
      callback();
      await tester.pumpAndSettle();
      expect(captures, 1);
      expect(acknowledgments.length, 1);
      await tester.drag(find.byType(Scrollable).first, const Offset(0, 10000));
      await tester.pumpAndSettle();
      final recover = find.text('Recover exact signed capture');
      await reveal(tester, recover);
      await tester.tap(recover);
      await tester.pumpAndSettle();
      expect(captures, 1);
      expect(acknowledgments.length, 2);
      expect(acknowledgments[0].url, acknowledgments[1].url);
      expect(acknowledgments[0].body, acknowledgments[1].body);
      expect(find.text('Privacy acknowledgment recorded.'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets(
    'uncertain capture recovers the identical UUID bytes and snapshot',
    (tester) async {
      final attempts = <http.Request>[];
      await tester.pumpWidget(
        MaterialApp(
          home: OfficeReviewCapturePage(
            actor: identity(),
            clientId: clientId,
            source: source(),
            repository: OfficeRepository(
              client: MockClient((request) async {
                if (request.method == 'GET') return json(contextRecord());
                attempts.add(request);
                return attempts.length == 1
                    ? json({'detail': 'Reply lost'}, 503)
                    : json(captured(), 201);
              }),
            ),
            picker: (_) async => OfficePhoto(png, 'image/png'),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Gallery'));
      await tester.pumpAndSettle();
      final witness = find.text(
        'I witnessed the applicant sign this exact information review.',
      );
      await reveal(tester, witness);
      await tester.tap(witness);
      await tester.pumpAndSettle();
      final save = find.text('Save signed review evidence');
      await reveal(tester, save);
      await tester.tap(save);
      await tester.pumpAndSettle();
      expect(attempts.length, 1);
      await tester.drag(find.byType(Scrollable).first, const Offset(0, 10000));
      await tester.pumpAndSettle();
      final recover = find.text('Recover exact signed capture');
      await reveal(tester, recover);
      await tester.tap(recover);
      await tester.pumpAndSettle();
      expect(attempts.length, 2);
      expect(attempts[0].url, attempts[1].url);
      expect(attempts[0].bodyBytes, attempts[1].bodyBytes);
      expect(
        find.text('Signed evidence saved for this exact version.'),
        findsOneWidget,
      );
    },
  );
  testWidgets(
    'cancelled image picker cannot enable capture even with attestation',
    (tester) async {
      var writes = 0;
      await tester.pumpWidget(
        MaterialApp(
          home: OfficeReviewCapturePage(
            actor: identity(),
            clientId: clientId,
            source: source(),
            repository: OfficeRepository(
              client: MockClient((request) async {
                if (request.method == 'POST') writes++;
                return json(contextRecord());
              }),
            ),
            picker: (_) async => null,
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Gallery'));
      await tester.pumpAndSettle();
      final witness = find.text(
        'I witnessed the applicant sign this exact information review.',
      );
      await reveal(tester, witness);
      await tester.tap(witness);
      await tester.pumpAndSettle();
      final save = find.ancestor(
        of: find.text('Save signed review evidence'),
        matching: find.byType(FilledButton),
      );
      expect(tester.widget<FilledButton>(save).onPressed, isNull);
      expect(writes, 0);
    },
  );
  testWidgets(
    'signed image is captured only with witness and exact context hash',
    (tester) async {
      var writes = 0;
      await tester.pumpWidget(
        MaterialApp(
          home: OfficeReviewCapturePage(
            actor: identity(),
            clientId: clientId,
            source: source(),
            repository: OfficeRepository(
              client: MockClient((request) async {
                if (request.method == 'GET') return json(contextRecord());
                writes++;
                expect(request.bodyBytes, png);
                expect(
                  request.url.queryParameters['expected_snapshot_sha256'],
                  hash,
                );
                expect(
                  request.url.queryParameters['witnessed_wet_signature'],
                  'true',
                );
                return json(captured(), 201);
              }),
            ),
            picker: (_) async => OfficePhoto(png, 'image/png'),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Gallery'));
      await tester.pumpAndSettle();
      final saveText = find.text('Save signed review evidence');
      expect(
        tester
            .widget<FilledButton>(
              find.ancestor(of: saveText, matching: find.byType(FilledButton)),
            )
            .onPressed,
        isNull,
      );
      final witness = find.text(
        'I witnessed the applicant sign this exact information review.',
      );
      await reveal(tester, witness);
      await tester.tap(witness);
      await tester.pumpAndSettle();
      await reveal(tester, saveText);
      await tester.tap(saveText);
      await tester.pumpAndSettle();
      expect(writes, 1);
      expect(
        find.text('Signed evidence saved for this exact version.'),
        findsOneWidget,
      );
      expect(find.text('Save signed review evidence'), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets(
    'privacy choice invalidates old context and binds signed acknowledgment separately',
    (tester) async {
      var captures = 0;
      var acknowledgments = 0;
      await tester.pumpWidget(
        MaterialApp(
          home: OfficeReviewCapturePage(
            actor: identity(),
            clientId: clientId,
            source: source(privacy: true),
            privacy: true,
            repository: OfficeRepository(
              client: MockClient((request) async {
                if (request.method == 'GET') {
                  return json(
                    contextRecord(
                      privacy: true,
                      optional:
                          request
                              .url
                              .queryParameters['optional_service_communications'] ==
                          'true',
                    ),
                  );
                }
                if (request.url.path.endsWith('/review-evidence')) {
                  captures++;
                  expect(
                    request
                        .url
                        .queryParameters['optional_service_communications'],
                    'true',
                  );
                  expect(
                    request.url.queryParameters['purpose'],
                    'privacy_acknowledgment',
                  );
                  return json(captured(privacy: true), 201);
                }
                acknowledgments++;
                expect(
                  request.url.path.endsWith('/privacy/acknowledgments'),
                  isTrue,
                );
                final body = jsonDecode(request.body);
                expect(body['optional_service_communications'], isTrue);
                expect(body['cif_version_id'], cifId);
                expect(
                  body['evidence_reference'],
                  'office-evidence:$evidenceId',
                );
                return json({
                  'client_id': clientId,
                  'cif_version_id': cifId,
                  'evidence_id': evidenceId,
                  'optional_service_communications': true,
                  'notice_version': 'N1',
                  'notice_sha256': hash,
                  'consent_version': 'C1',
                  'consent_sha256': hash,
                });
              }),
            ),
            picker: (_) async => OfficePhoto(png, 'image/png'),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(
        find.text(
          'Optional service communications beyond necessary loan servicing',
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Record privacy acknowledgment'), findsNothing);
      await tester.tap(find.text('Load current review'));
      await tester.pumpAndSettle();
      await reveal(tester, find.text('Gallery'));
      await tester.tap(find.text('Gallery'));
      await tester.pumpAndSettle();
      final witness = find.text(
        'I witnessed the applicant review these exact privacy documents and sign with the optional choice shown.',
      );
      await reveal(tester, witness);
      await tester.tap(witness);
      await tester.pumpAndSettle();
      final save = find.text('Record privacy acknowledgment');
      await reveal(tester, save);
      await tester.tap(save);
      await tester.pumpAndSettle();
      expect(captures, 1);
      expect(acknowledgments, 1);
      expect(find.text('Privacy acknowledgment recorded.'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
}
