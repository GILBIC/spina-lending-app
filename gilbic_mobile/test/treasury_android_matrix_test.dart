import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_repository.dart';
import 'package:gilbic_mobile/src/features/mirror/safe_mirror_surface.dart';
import 'package:gilbic_mobile/src/features/treasury/treasury_claim_page.dart';
import 'package:gilbic_mobile/src/features/treasury/treasury_command_page.dart';
import 'package:gilbic_mobile/src/features/treasury/treasury_workspace_page.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/android_role_fixture.dart';
import 'support/treasury_fixture.dart';

void main() {
  for (final view in [
    'claim',
    'receipt',
    'reconciliation',
    'outgoing',
    'private-proof',
  ]) {
    for (final width in [320.0, 360.0, 412.0]) {
      for (final scale in [1.0, 1.3, 2.0]) {
        testWidgets(
          '$view at $width/$scale preserves exact amount, controls and privacy',
          (tester) async {
            var posts = 0;
            final w = workspace()
              ..['borrower_choices'] = [
                {
                  'client_id': user,
                  'name': 'Synthetic current borrower',
                  'allowed_account_ids': [account],
                  'loans': [
                    {
                      'loan_id': ledger,
                      'loan_number': 'Synthetic current loan',
                      'loan_type': 'Regular',
                      'expected_version': 0,
                    },
                  ],
                },
              ]
              ..['source_choices'] = [
                {
                  'id': event,
                  'kind': 'salary_advance',
                  'version': 1,
                  'payee_id': user,
                  'payee_name': 'Synthetic employee',
                  'amount': '20.01',
                  'status': 'approved',
                  'supported': true,
                  'partial_supported': false,
                },
              ];
            (w['capabilities'] as Map).addAll(<String, bool>{
              'receipt_apply': true,
              'reconciliation_observe': true,
              'reconciliation_match': true,
              'disbursement_record': true,
            });
            ((w['accounts'] as List).single['actions'] as List).addAll(<String>[
              'receipt_apply',
              'reconciliation_observe',
              'reconciliation_match',
              'disbursement_record',
            ]);
            final record = {
              'id': event,
              'version': 1,
              'account_id': account,
              'ledger_context_id': ledger,
              'status': view == 'receipt'
                  ? 'received_awaiting_recording'
                  : 'balanced_unresolved',
              'amount': '90071992547409.91',
              'remaining_amount': '90071992547409.91',
              'reference': 'Synthetic private reference',
              'actual_balance': '20.01',
              'expected_balance': '20.01',
              'difference': '0.00',
              'coverage_start': '2026-10-01T00:00:00Z',
              'cutoff': '2026-10-02T00:00:00Z',
              'blockers': ['Actual statement matching remains incomplete.'],
              'can_close': false,
              'observations': [
                {'id': user, 'amount': '20.01', 'reference': null},
              ],
              'loan_choices': [
                {
                  'loan_id': ledger,
                  'loan_number': 'Synthetic current loan',
                  'loan_type': 'Regular',
                  'expected_version': 0,
                },
              ],
            };
            final repo = SpinaTreasuryRepository(
              session: session(),
              deviceId: 'external',
              journal: MemoryTreasuryJournal(),
              client: MockClient((r) async {
                if (r.method == 'POST') posts++;
                if (r.url.path.endsWith('/workspace')) return jsonResponse(w);
                if (r.url.path.endsWith('/content')) {
                  return http.Response.bytes(
                    base64Decode(
                      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
                    ),
                    200,
                    headers: {
                      'content-type': 'image/png',
                      'cache-control': 'no-store',
                    },
                  );
                }
                return jsonResponse(record);
              }),
            );
            await repo.loadWorkspace();
            final Widget page = switch (view) {
              'claim' => TreasuryClaimPage(
                repository: repo,
                account: repo.workspace!.accounts.single,
                borrowerChoices: (w['borrower_choices'] as List)
                    .cast<Map<String, dynamic>>(),
                claim: {
                  'id': event,
                  'version': 1,
                  'client_id': user,
                  'current_version': {
                    'amount': '90071992547409.91',
                    'reference': 'Synthetic reference',
                    'loan_ids': [ledger],
                  },
                },
              ),
              'receipt' => TreasuryRecordPage(
                repository: repo,
                kind: TreasuryListKind.receipts,
                id: event,
              ),
              'reconciliation' => TreasuryRecordPage(
                repository: repo,
                kind: TreasuryListKind.reconciliations,
                id: event,
              ),
              'outgoing' => TreasuryCommandPage(
                repository: repo,
                account: repo.workspace!.accounts.single,
                action: TreasuryAction.disbursementRecord,
                initial: {'amount': '90071992547409.91'},
              ),
              _ => TreasuryPrivateFilePage(
                repository: repo,
                claimId: event,
                version: 1,
                mediaType: 'image/png',
              ),
            };
            final semantics = tester.ensureSemantics();
            try {
              await pumpAndroidRoleFixture(
                tester,
                home: page,
                size: Size(width, 900),
                textScaler: TextScaler.linear(scale),
              );
              await tester.pumpAndSettle();
              expect(tester.takeException(), isNull);
              expect(find.byType(SafeMirrorSurface), findsNothing);
              expect(
                MirrorNavigationObserver.safeNames.any(
                  (n) => n.contains('treasury'),
                ),
                isFalse,
              );
              if (view == 'claim') {
                expect(
                  tester
                      .widget<TextField>(
                        find.widgetWithText(TextField, 'Amount (PHP)'),
                      )
                      .controller!
                      .text,
                  '90071992547409.91',
                );
              }
              await _capture(tester, '$view-${width.toInt()}-$scale-top');
              final last = switch (view) {
                'claim' => 'Review submission',
                'outgoing' => 'Review and confirm',
                'receipt' => 'Prepare loan application',
                'reconciliation' => 'Match statement transaction',
                _ => null,
              };
              if (last != null) {
                await tester.scrollUntilVisible(
                  find.text(last),
                  200,
                  scrollable: find.byType(Scrollable).first,
                );
                await tester.ensureVisible(find.text(last));
                await tester.pumpAndSettle();
                expect(find.text(last), findsOneWidget);
                await expectLater(
                  tester,
                  meetsGuideline(androidTapTargetGuideline),
                );
              }
              if (view == 'reconciliation') {
                expect(find.text('Close reconciliation'), findsNothing);
              }
              expect(posts, 0);
              expect(tester.takeException(), isNull);
              await _capture(tester, '$view-${width.toInt()}-$scale-action');
            } finally {
              semantics.dispose();
            }
          },
        );
      }
    }
  }
  testWidgets(
    'claim keyboard leaves reviewed submission reachable at large text',
    (tester) async {
      final repo = SpinaTreasuryRepository(
        session: session(),
        deviceId: 'external',
        journal: MemoryTreasuryJournal(),
        client: MockClient(
          (r) async => jsonResponse(workspace(private: false)),
        ),
      );
      await repo.loadWorkspace();
      await pumpAndroidRoleFixture(
        tester,
        home: TreasuryClaimPage(
          repository: repo,
          account: repo.workspace!.accounts.single,
          borrowerChoices: [
            {
              'client_id': user,
              'name': 'Synthetic own borrower',
              'loans': [
                {'loan_id': ledger, 'loan_number': 'Synthetic loan'},
              ],
            },
          ],
        ),
        size: const Size(320, 900),
        textScaler: TextScaler.linear(2),
        viewInsets: const EdgeInsets.only(bottom: 300),
      );
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('Review submission'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.ensureVisible(find.text('Review submission'));
      await tester.pumpAndSettle();
      expect(
        tester.getRect(find.text('Review submission')).bottom,
        lessThan(600),
      );
      expect(tester.takeException(), isNull);
    },
  );
}

Future<void> _capture(WidgetTester tester, String name) async {
  final folder = Platform.environment['SPINA_TREASURY_CAPTURE_DIR'];
  if (folder == null) return;
  final boundary = tester.renderObject<RenderRepaintBoundary>(
    find.byKey(const Key('android-role-capture')),
  );
  await tester.runAsync(() async {
    final captured = await boundary.toImage(pixelRatio: 1);
    try {
      final bytes = await captured.toByteData(format: ui.ImageByteFormat.png);
      if (bytes == null) throw StateError('Synthetic capture unavailable');
      await Directory(folder).create(recursive: true);
      await File(
        '$folder/$name.png',
      ).writeAsBytes(bytes.buffer.asUint8List(), flush: true);
    } finally {
      captured.dispose();
    }
  });
}
