import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/office/office_repository.dart';
import 'package:gilbic_mobile/src/features/office/office_cif_page.dart';
import 'package:gilbic_mobile/src/features/office/office_finder_page.dart';
import 'package:gilbic_mobile/src/features/office/office_review_capture_page.dart';
import 'package:gilbic_mobile/src/features/office/office_signature_input.dart';
import 'package:gilbic_mobile/src/features/office/office_widgets.dart';
import 'package:http/testing.dart';
import 'support/office_ui_fixture.dart';

OfficeRecord privacyContext() => {
  'client_id': clientId,
  'cif_version_id': cifId,
  'purpose': 'privacy_acknowledgment',
  'application_id': null,
  'application_version_id': null,
  'snapshot_sha256': 'a' * 64,
  'issuable': true,
  'review_snapshot': {
    'client_id': clientId,
    'cif_version_id': cifId,
    'optional_service_communications': false,
    'notice': {'version': 'N1', 'sha256': 'b' * 64},
    'consent': {'version': 'C1', 'sha256': 'c' * 64},
  },
};

void main() {
  testWidgets(
    'same-version information correction invalidates recorded privacy task',
    (tester) async {
      var current = Map<String, dynamic>.of(cif);
      final repository = OfficeRepository(
        client: MockClient((request) async {
          if (request.url.path.endsWith('/privacy/context')) {
            return response(privacyContext());
          }
          if (request.method == 'PATCH') {
            current = {
              ...current,
              ...jsonDecode(request.body)['corrected_information']
                  as Map<String, dynamic>,
            };
          }
          return response(current);
        }),
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
      await reveal(tester, '3. Privacy acknowledgment');
      await tester.tap(find.text('3. Privacy acknowledgment'));
      await tester.pumpAndSettle();
      await reveal(tester, 'Privacy notice and consent');
      await tester.tap(find.text('Privacy notice and consent'));
      await tester.pumpAndSettle();
      // The signing route returns only verified evidence; exercise the parent's result boundary.
      tester.state<NavigatorState>(find.byType(Navigator)).pop<OfficeRecord>({
        'evidence_id': applicantId,
        'evidence_reference': 'office-evidence:$applicantId',
      });
      await tester.pumpAndSettle();
      final privacyCard = find.ancestor(
        of: find.text('3. Privacy acknowledgment'),
        matching: find.byType(Card),
      );
      expect(
        find.descendant(
          of: privacyCard,
          matching: find.byIcon(Icons.check_circle_outline),
        ),
        findsOneWidget,
      );
      await tester.drag(find.byType(ListView).first, const Offset(0, 1000));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Correct information'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('office-full_name')),
        'Corrected Applicant',
      );
      await reveal(tester, 'Reason for correction (required)');
      await tester.enterText(
        find.byKey(const Key('office-reason')),
        'Correct spelling',
      );
      await reveal(tester, 'Save corrected information');
      await tester.tap(find.text('Save corrected information'));
      await tester.pumpAndSettle();
      await tester.drag(find.byType(ListView).first, const Offset(0, 2000));
      await tester.pumpAndSettle();
      await reveal(tester, '3. Privacy acknowledgment');
      expect(
        find.descendant(
          of: privacyCard,
          matching: find.byIcon(Icons.check_circle_outline),
        ),
        findsNothing,
      );
    },
  );

  testWidgets(
    'finder refreshes the same query after returning from an intake',
    (tester) async {
      var reads = 0;
      final repository = OfficeRepository(
        client: MockClient((request) async {
          if (request.url.path.endsWith('/case')) return response(intake);
          reads++;
          return response({
            'as_of': '2026-10-06T00:00:00Z',
            'has_more': false,
            'next_cursor': null,
            'items': [
              {
                'applicant_id': applicantId,
                'intake_reference': 'INT-1',
                'client_id': clientId,
                'full_name': reads > 1
                    ? 'Updated Applicant'
                    : 'Sample Applicant',
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
          home: OfficeFinderPage(actor: actor(), repository: repository),
        ),
      );
      await tester.pumpAndSettle();
      await reveal(tester, 'Continue INT-1');
      await tester.tap(find.text('Continue INT-1'));
      await tester.pumpAndSettle();
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(reads, 2);
      expect(find.text('Updated Applicant'), findsOneWidget);
    },
  );

  for (final statuses in [
    [415],
    [409],
    [503, 415],
    [503, 422],
    [503, 409],
  ]) {
    final status = statuses.first;
    testWidgets(
      'signature responses $statuses distinguish rejection from uncertainty',
      (tester) async {
        tester.view.physicalSize = const Size(390, 844);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        var writes = 0;
        final captureBodies = <String>[];
        final captureUrls = <Uri>[];
        final repository = OfficeRepository(
          client: MockClient((request) async {
            if (request.method == 'POST') {
              writes++;
              captureBodies.add(base64Encode(request.bodyBytes));
              captureUrls.add(request.url);
              return response({
                'detail': 'Synthetic capture response',
              }, statuses[(writes - 1).clamp(0, statuses.length - 1)]);
            }
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
            builder: (context, child) => MediaQuery(
              data: MediaQuery.of(
                context,
              ).copyWith(textScaler: const TextScaler.linear(2)),
              child: child!,
            ),
            home: OfficeReviewCapturePage(
              actor: actor(),
              repository: repository,
              clientId: clientId,
              source: {'purpose': 'cif_review', 'cif_version_id': cifId},
            ),
          ),
        );
        await tester.pumpAndSettle();
        await reveal(tester, 'Sign on screen');
        await tester.tap(find.text('Sign on screen'));
        await tester.pumpAndSettle();
        // PNG production and blank/cancel handling are exercised by the drawing widget test.
        tester
            .widget<OfficeSignatureInput>(find.byType(OfficeSignatureInput))
            .onChanged(
              OfficePhoto(
                base64Decode(
                  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
                ),
                'image/png',
              ),
            );
        await tester.pumpAndSettle();
        await reveal(
          tester,
          'I witnessed the applicant sign this exact information review.',
        );
        await tester.tap(
          find.text(
            'I witnessed the applicant sign this exact information review.',
          ),
        );
        await tester.pumpAndSettle();
        // Tapping the selected mode must preserve both the drawing and witness.
        await tester.drag(find.byType(ListView).first, const Offset(0, 2000));
        await tester.pumpAndSettle();
        await reveal(tester, 'Sign on screen');
        await tester.tap(find.text('Sign on screen'));
        await tester.pumpAndSettle();
        await reveal(tester, 'Save signature');
        expect(tester.takeException(), isNull);
        await tester.tap(find.text('Save signature'));
        await tester.pumpAndSettle();
        await tester.drag(find.byType(ListView).first, const Offset(0, 2000));
        await tester.pumpAndSettle();
        await reveal(tester, 'Sign on screen');
        expect(
          tester
              .widget<ChoiceChip>(
                find.widgetWithText(ChoiceChip, 'Sign on screen'),
              )
              .onSelected,
          status == 415 ? isNotNull : isNull,
        );
        expect(writes, 1);
        if (status == 409) {
          tester
              .state<ScrollableState>(find.byType(Scrollable).first)
              .position
              .jumpTo(0);
          await tester.pumpAndSettle();
          await reveal(tester, 'Load current review');
          expect(
            tester
                .widget<OutlinedButton>(
                  find.widgetWithText(OutlinedButton, 'Load current review'),
                )
                .onPressed,
            isNotNull,
          );
        }
        if (status == 503) {
          await tester.drag(find.byType(ListView).first, const Offset(0, 2000));
          await tester.pumpAndSettle();
          await reveal(tester, 'Recover exact signed capture');
          await tester.tap(find.text('Recover exact signed capture'));
          await tester.pumpAndSettle();
          expect(writes, 2);
          expect(captureBodies.last, captureBodies.first);
          expect(captureUrls.last, captureUrls.first);
          expect(
            captureUrls.last.queryParameters['capture_method'],
            'screen_signature',
          );
          tester
              .state<ScrollableState>(find.byType(Scrollable).first)
              .position
              .jumpTo(0);
          await tester.pumpAndSettle();
          await reveal(tester, 'Load current review');
          expect(
            tester
                .widget<OutlinedButton>(
                  find.widgetWithText(OutlinedButton, 'Load current review'),
                )
                .onPressed,
            isNull,
          );
        }
        expect(tester.takeException(), isNull);
      },
    );
  }
}
