import 'dart:convert';
import 'dart:async';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:crypto/crypto.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/office/office_repository.dart';
import 'package:gilbic_mobile/src/features/office/office_cif_page.dart';
import 'package:gilbic_mobile/src/features/office/office_application_page.dart';
import 'package:gilbic_mobile/src/features/office/office_signature_input.dart';
import 'package:gilbic_mobile/src/features/office/office_widgets.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/office/office_intake_page.dart';
import 'package:gilbic_mobile/src/features/office/office_review_capture_page.dart';
import 'package:gilbic_mobile/src/features/office/office_workspace_page.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/office_ui_fixture.dart';

void main() {
  testWidgets(
    'New application prepares a fresh reference and form without saving',
    (tester) async {
      final requests = <http.Request>[];
      final repository = OfficeRepository(
        client: MockClient((request) async {
          requests.add(request);
          if (request.url.path.endsWith('/entry-context')) {
            return response({
              'client_id': clientId,
              'cif_version_id': cifId,
              'cif_version_number': 1,
              'loan_types': [],
            });
          }
          return response({'detail': 'No saved application'}, 404);
        }),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: OfficeApplicationPage(
            actor: actor(),
            repository: repository,
            clientId: clientId,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('New application'), findsOneWidget);
      await tester.tap(find.text('New application'));
      await tester.pumpAndSettle();
      expect(find.text('Requested loan'), findsOneWidget);
      expect(
        tester
            .widget<TextFormField>(
              find.byKey(const Key('office-application_reference')),
            )
            .controller!
            .text,
        startsWith('LOAN-'),
      );
      expect(requests.every((r) => r.method == 'GET'), isTrue);
    },
  );

  testWidgets(
    'finger strokes persist across scrolling, export PNG, and clear safely',
    (tester) async {
      final ready = Completer<OfficePhoto>();
      OfficePhoto? selected;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ListView(
              children: [
                OfficeSignatureInput(
                  enabled: true,
                  onChanged: (value) {
                    selected = value;
                    if (value != null && !ready.isCompleted)
                      ready.complete(value);
                  },
                ),
                const SizedBox(height: 2000),
              ],
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      final start =
          tester.getTopLeft(find.byKey(const Key('office-signature-pad'))) +
          const Offset(40, 40);
      final gesture = await tester.startGesture(start);
      await gesture.moveBy(const Offset(50, 30));
      await tester.pump();
      await gesture.moveBy(const Offset(80, -20));
      await tester.pump();
      expect(find.text('Signing…'), findsOneWidget);
      await gesture.up();
      for (var i = 0; i < 100 && !ready.isCompleted; i++) {
        await tester.runAsync(
          () => Future<void>.delayed(const Duration(milliseconds: 20)),
        );
        await tester.pump();
      }
      expect(
        ready.isCompleted,
        isTrue,
        reason: tester
            .widgetList<Text>(find.byType(Text))
            .map((text) => text.data)
            .join(' | '),
      );
      final image = selected;
      expect(image, isNotNull);
      final decoded = await tester.runAsync(
        () => ui.instantiateImageCodec(image!.bytes),
      );
      final frame = await tester.runAsync(() => decoded!.getNextFrame());
      expect(frame!.image.width, 960);
      expect(frame.image.height, 480);
      frame.image.dispose();
      decoded!.dispose();
      final output = Platform.environment['SPINA_SIGNATURE_TEST_OUTPUT'];
      if (output != null) {
        await tester.runAsync(() => File(output).writeAsBytes(image!.bytes));
      }
      await tester.pumpAndSettle();
      final scrolling = tester
          .state<ScrollableState>(find.byType(Scrollable))
          .position;
      scrolling.jumpTo(scrolling.maxScrollExtent);
      await tester.pumpAndSettle();
      scrolling.jumpTo(0);
      await tester.pumpAndSettle();
      expect(
        find.text('Signature ready. Check it before saving.'),
        findsOneWidget,
      );
      await tester.tap(find.text('Clear signature'));
      await tester.pumpAndSettle();
      expect(selected, isNull);
    },
  );

  test(
    'screen capture attests the correct method and rejects a paper receipt',
    () async {
      final bytes = base64Decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
      );
      var method = 'screen_signature';
      final repository = OfficeRepository(
        client: MockClient((request) async {
          expect(
            request.url.queryParameters['capture_method'],
            'screen_signature',
          );
          expect(
            request.url.queryParameters['witnessed_screen_signature'],
            'true',
          );
          expect(
            request.url.queryParameters.containsKey('witnessed_wet_signature'),
            isFalse,
          );
          return response({
            'client_id': clientId,
            'cif_version_id': cifId,
            'purpose': 'cif_review',
            'application_id': null,
            'application_version_id': null,
            'snapshot_sha256': 'a' * 64,
            'capture_method': method,
            'evidence_id': applicantId,
            'evidence_reference': 'office-evidence:$applicantId',
            'media_type': 'image/png',
            'byte_count': bytes.length,
            'content_sha256': sha256.convert(bytes).toString(),
          });
        }),
      );
      Future<OfficeRecord> capture() => repository.captureReview(
        actor(),
        clientId,
        source: {'purpose': 'cif_review', 'cif_version_id': cifId},
        snapshotHash: 'a' * 64,
        requestId: applicantId,
        bytes: bytes,
        mediaType: 'image/png',
        captureMethod: 'screen_signature',
      );
      expect((await capture())['capture_method'], 'screen_signature');
      method = 'paper_scan';
      await expectLater(capture(), throwsA(isA<SpinaApiException>()));
    },
  );

  test(
    'finder rejects invalid paging duplicate rows and foreign client applications',
    () async {
      final item = {
        'applicant_id': applicantId,
        'intake_reference': 'INT-1',
        'client_id': clientId,
        'full_name': 'Sample Applicant',
        'phone_number': '09123456789',
        'intake_status': 'eligible_for_cif',
        'created_at': '2026-10-01T00:00:00Z',
        'updated_at': '2026-10-06T00:00:00Z',
      };
      var page = <String, dynamic>{
        'as_of': '2026-10-06T00:00:00Z',
        'has_more': false,
        'next_cursor': null,
        'items': [item],
      };
      final repository = OfficeRepository(
        client: MockClient((request) async => response(page)),
      );
      expect((await repository.findIntakes(actor()))['items'], hasLength(1));
      page = {...page, 'has_more': true};
      await expectLater(
        repository.findIntakes(actor()),
        throwsA(isA<SpinaApiException>()),
      );
      page = {
        ...page,
        'has_more': false,
        'items': [item, item],
      };
      await expectLater(
        repository.findIntakes(actor()),
        throwsA(isA<SpinaApiException>()),
      );
      page = {
        ...page,
        'items': [],
        'intake': {
          'applicant_id': applicantId,
          'intake_reference': 'INT-1',
          'client_id': cifId,
          'intake_status': 'eligible_for_cif',
        },
      };
      await expectLater(
        repository.findApplications(actor(), 'INT-1', clientId),
        throwsA(isA<SpinaApiException>()),
      );
    },
  );
  testWidgets(
    'eligible intake continues to its verified CIF without typing or writes',
    (tester) async {
      final requests = <http.Request>[];
      final repository = OfficeRepository(
        client: MockClient((request) async {
          requests.add(request);
          if (request.url.path.endsWith('/case')) return response(intake);
          if (request.url.path.endsWith('/cif-client')) {
            return response({
              'client_id': clientId,
              'application_reference': 'INT-1',
            });
          }
          if (request.url.path.endsWith('/review-summary')) {
            return response(cif);
          }
          return response({'detail': 'Unexpected request'}, 404);
        }),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: OfficeIntakePage(
            actor: actor(),
            repository: repository,
            reference: 'INT-1',
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Continue to CIF'), findsOneWidget);
      await tester.tap(find.text('Continue to CIF'));
      await tester.pumpAndSettle();
      expect(find.text('1. Review details'), findsOneWidget);
      expect(find.text('Sample Applicant'), findsWidgets);
      expect(requests.every((request) => request.method == 'GET'), isTrue);
      expect(
        requests
            .where((r) => r.url.path.endsWith('/cif-client'))
            .single
            .url
            .path,
        endsWith('/INT-1/cif-client'),
      );
    },
  );

  testWidgets(
    'CIF checklist keeps verification draft when another task opens',
    (tester) async {
      final repository = OfficeRepository(
        client: MockClient((request) async => response(cif)),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: OfficeCifPage(
            actor: actor(),
            repository: repository,
            clientId: clientId,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('1. Review details'), findsOneWidget);
      await reveal(tester, '4. Identity verification');
      await tester.tap(find.text('4. Identity verification'));
      await tester.pumpAndSettle();
      await reveal(tester, 'Provider evidence reference');
      await tester.enterText(
        find.byKey(const Key('office-baseline_reference')),
        'PROVIDER-EXACT-1',
      );
      await reveal(tester, '2. Applicant signature');
      await tester.tap(find.text('2. Applicant signature'));
      await tester.pumpAndSettle();
      await reveal(tester, '4. Identity verification');
      await tester.tap(find.text('4. Identity verification'));
      await tester.pumpAndSettle();
      expect(
        tester
            .widget<TextFormField>(
              find.byKey(const Key('office-baseline_reference')),
            )
            .controller!
            .text,
        'PROVIDER-EXACT-1',
      );
      expect(find.text('Activate verified CIF'), findsNothing);
    },
  );

  testWidgets(
    'native signing offers finger input and rejects blank signature',
    (tester) async {
      var writes = 0;
      final repository = OfficeRepository(
        client: MockClient((request) async {
          if (request.method != 'GET') writes++;
          return response({
            'client_id': clientId,
            'cif_version_id': cifId,
            'purpose': 'cif_review',
            'application_id': null,
            'application_version_id': null,
            'snapshot_sha256': 'a' * 64,
            'review_snapshot': {
              'client_id': clientId,
              'cif_version_id': cifId,
              'information': {'full_name': 'Sample Applicant'},
            },
          });
        }),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: OfficeReviewCapturePage(
            actor: actor(),
            repository: repository,
            clientId: clientId,
            source: {'purpose': 'cif_review', 'cif_version_id': cifId},
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Sign on screen'), findsOneWidget);
      await reveal(tester, 'Sign on screen');
      await tester.tap(find.text('Sign on screen'));
      await tester.pumpAndSettle();
      await reveal(tester, 'Save signature');
      expect(
        tester
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, 'Save signature'),
            )
            .onPressed,
        isNull,
      );
      expect(writes, 0);
    },
  );

  testWidgets(
    'Office finder opens saved intake from list without a typed reference',
    (tester) async {
      final requests = <http.Request>[];
      final repository = OfficeRepository(
        client: MockClient((request) async {
          requests.add(request);
          if (request.url.path.endsWith('/case')) return response(intake);
          return response({
            'as_of': '2026-10-06T00:00:00Z',
            'has_more': false,
            'next_cursor': null,
            'items': [
              {
                'applicant_id': applicantId,
                'intake_reference': 'INT-1',
                'client_id': clientId,
                'full_name': 'Sample Applicant',
                'phone_number': '09123456789',
                'intake_status': 'eligible_for_cif',
                'created_at': '2026-10-01T00:00:00Z',
                'updated_at': '2026-10-06T00:00:00Z',
              },
            ],
          });
        }),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: OfficeWorkspacePage(
            session: staff,
            deviceIdentityProvider: DeviceIdentityProvider(
              store: MemoryDeviceIdentityStore(),
              platformResolver: () => 'android',
              appVersionResolver: () async => 'test',
            ),
            repository: repository,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Find an intake or application'), findsOneWidget);
      await tester.tap(find.text('Find an intake or application'));
      await tester.pumpAndSettle();
      await reveal(tester, 'Continue INT-1');
      await tester.tap(find.text('Continue INT-1'));
      await tester.pumpAndSettle();
      expect(find.text('Continue to CIF'), findsOneWidget);
      expect(requests.every((r) => r.method == 'GET'), isTrue);
    },
  );
}
