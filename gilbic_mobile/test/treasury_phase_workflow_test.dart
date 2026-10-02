import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_repository.dart';
import 'package:gilbic_mobile/src/core/media/private_image_store.dart';
import 'package:gilbic_mobile/src/features/treasury/treasury_command_page.dart';
import 'package:gilbic_mobile/src/features/treasury/treasury_workspace_page.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/android_role_fixture.dart';
import 'support/treasury_fixture.dart';

class EmptySubmittedFiles extends PrivateImageStore {
  @override
  Future<void> cleanup({String? keepPath}) async {}
}

Map<String, dynamic> staffWorkspace() {
  final w = workspace();
  (w['capabilities'] as Map).addAll(<String, bool>{
    'receipt_verify': true,
    'receipt_apply': true,
    'reconciliation_close': true,
  });
  ((w['accounts'] as List).single['actions'] as List).addAll(<String>[
    'receipt_verify',
    'receipt_apply',
    'reconciliation_close',
  ]);
  return w;
}

Map<String, dynamic> previewBody() => {
  'expected_version': 1,
  'mode': 'single',
  'total_amount': '20.01',
  'loans': [
    {'loan_id': ledger, 'expected_version': 0},
  ],
  'intent': 'scheduled',
  'covered_dates': [],
  'effective_date': '2026-10-02',
};
Map<String, dynamic> serverPreview() => {
  'contract_version': 1,
  'actor': {'user_id': user, 'device_id': device},
  'account_id': account,
  'ledger_context_id': ledger,
  'receipt_id': event,
  'receipt_version': 1,
  'remaining_amount': '20.01',
  'digest': 'a' * 64,
  'mode': 'single',
  'total_amount': '20.01',
  'effective_date': '2026-10-02',
  'loans': [
    {'loan_id': ledger, 'expected_version': 0},
  ],
  'allocations': [
    {
      'loan_id': ledger,
      'loan_type': 'Regular',
      'component': 'scheduled',
      'intent': 'scheduled',
      'covered_dates': ['2026-10-02'],
      'amount': '20.01',
      'applied_amount': '20.01',
      'unallocated_amount': '0.00',
    },
  ],
  'blockers': [],
  'can_apply': true,
};
void main() {
  test(
    'blocked current preview carries actual blockers and no digest without a write attempt',
    () async {
      final p = serverPreview()
        ..['can_apply'] = false
        ..['digest'] = null
        ..['allocations'] = []
        ..['blockers'] = [
          {
            'code': 'treasury_conflict',
            'message': 'Current loan state unavailable',
          },
        ];
      final repo = SpinaTreasuryRepository(
        session: session(),
        deviceId: 'external',
        journal: MemoryTreasuryJournal(),
        client: MockClient(
          (r) async => jsonResponse(r.method == 'GET' ? staffWorkspace() : p),
        ),
      );
      await repo.loadWorkspace();
      final result = await repo.preview(event, previewBody());
      expect(result['can_apply'], isFalse);
      expect(result['digest'], isNull);
      expect(result['blockers'], [
        {
          'code': 'treasury_conflict',
          'message': 'Current loan state unavailable',
        },
      ]);
      expect(repo.pendingRequestId, isNull);
    },
  );
  test(
    'changed receipt capacity/empty server rows/actor are never valid preview',
    () async {
      for (final mutate in <void Function(Map<String, dynamic>)>[
        (p) => p['receipt_id'] = ledger,
        (p) => p['allocations'] = [],
        (p) => (p['actor'] as Map)['device_id'] = event,
      ]) {
        final p = serverPreview();
        mutate(p);
        final repo = SpinaTreasuryRepository(
          session: session(),
          deviceId: 'external',
          journal: MemoryTreasuryJournal(),
          client: MockClient(
            (r) async => jsonResponse(r.method == 'GET' ? staffWorkspace() : p),
          ),
        );
        await repo.loadWorkspace();
        await expectLater(
          repo.preview(event, previewBody()),
          throwsA(isA<TreasuryUncertain>()),
        );
        expect(repo.pendingRequestId, isNull);
      }
    },
  );
  test(
    'one recipient verification remains durable when allocation fails; no automatic second POST',
    () async {
      final posts = <Map<String, dynamic>>[];
      var received = false;
      final repo = SpinaTreasuryRepository(
        session: session(),
        deviceId: 'external',
        journal: MemoryTreasuryJournal(),
        client: MockClient((r) async {
          if (r.url.path.endsWith('/workspace')) {
            return jsonResponse(staffWorkspace());
          }
          if (r.url.path.endsWith('/allocation-preview')) {
            return jsonResponse(serverPreview());
          }
          if (r.method == 'GET') {
            return jsonResponse({
              'id': event,
              'version': 1,
              'account_id': account,
              'client_id': user,
              'amount': '20.01',
              'remaining_amount': '20.01',
              'applied_amount': '0.00',
              'verification': 'manually_verified',
              'status': 'received_awaiting_recording',
              'loan_choices': [
                {
                  'loan_id': ledger,
                  'expected_version': 0,
                  'loan_type': 'Regular',
                  'loan_number': 'Synthetic regular',
                },
              ],
            });
          }
          final body = jsonDecode(r.body) as Map<String, dynamic>;
          posts.add(body);
          if (body['action'] == 'receipt_apply') {
            return http.Response(
              '{"detail":{"code":"allocation_blocked","message":"Current protected allocation is blocked."}}',
              409,
            );
          }
          received = true;
          return jsonResponse({
            'contract_version': 1,
            'request_id': body['request_id'],
            'action': body['action'],
            'status': 'saved',
            'target_id': event,
            'version': 1,
            'result': {
              'actor_user_id': user,
              'device_id': device,
              'account_id': account,
              'ledger_context_id': ledger,
              'receipt': {
                'id': event,
                'version': 1,
                'client_id': user,
                'amount': '20.01',
                'remaining_amount': '20.01',
                'status': 'received_awaiting_recording',
                'verification': 'manually_verified',
              },
            },
          });
        }),
      );
      await repo.loadWorkspace();
      await repo.execute(
        TreasuryCommand(
          TreasuryAction.receiptVerify,
          requestId: requestId,
          accountId: account,
          expectedVersion: 1,
          fields: {
            'client_id': user,
            'amount': '20.01',
            'provider': 'gcash',
            'reference': 'Synthetic actual recipient reference',
            'effective_at': '2026-10-02T00:00:00Z',
            'evidence_id': ledger,
            'recipient_attestation': 'Recipient statement checked',
            'reason': 'Synthetic',
          },
        ),
      );
      expect(received, isTrue);
      expect(posts.length, 1);
      final p = await repo.preview(event, previewBody());
      await expectLater(
        repo.execute(
          TreasuryCommand(
            TreasuryAction.receiptApply,
            requestId: user,
            accountId: account,
            expectedVersion: 1,
            fields: {
              ...previewBody()..remove('expected_version'),
              'receipt_id': event,
              'digest': p['digest'],
            },
          ),
        ),
        throwsA(isA<Exception>()),
      );
      expect(posts.length, 2);
      expect(posts.where((p) => p['action'] == 'receipt_verify').length, 1);
      expect(
        (await repo.detail(
          TreasuryListKind.receipts,
          event,
        ))['remaining_amount'],
        '20.01',
      );
      expect(repo.pendingRequestId, isNull);
    },
  );
  testWidgets(
    'server preview must stay unchanged before confirm; large text retains actual allocation',
    (tester) async {
      var actions = 0;
      final repo = SpinaTreasuryRepository(
        session: session(),
        deviceId: 'external',
        journal: MemoryTreasuryJournal(),
        client: MockClient((r) async {
          if (r.url.path.endsWith('/workspace')) {
            return jsonResponse(staffWorkspace());
          }
          if (r.url.path.endsWith('/allocation-preview')) {
            return jsonResponse(serverPreview());
          }
          actions++;
          return jsonResponse(null);
        }),
      );
      await repo.loadWorkspace();
      await pumpAndroidRoleFixture(
        tester,
        home: TreasuryCommandPage(
          repository: repo,
          account: repo.workspace!.accounts.single,
          action: TreasuryAction.receiptApply,
          initial: {
            'receipt_id': event,
            'expected_version': 1,
            'total_amount': '20.01',
            'effective_date': '2026-10-02',
            'loan_choices': [
              {
                'loan_id': ledger,
                'expected_version': 0,
                'loan_type': 'Regular',
                'loan_number': 'Synthetic regular',
              },
            ],
          },
        ),
        size: const Size(320, 900),
        textScaler: TextScaler.linear(2),
      );
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('Synthetic regular (Regular)'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.ensureVisible(find.text('Synthetic regular (Regular)'));
      await tester.tap(find.text('Synthetic regular (Regular)'));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('Prepare server allocation'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.ensureVisible(find.text('Prepare server allocation'));
      await tester.tap(find.text('Prepare server allocation'));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('This unchanged allocation can be recorded.'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      expect(
        find.text('This unchanged allocation can be recorded.'),
        findsOneWidget,
      );
      expect(actions, 0);
      expect(tester.takeException(), isNull);
      await tester.scrollUntilVisible(
        find.widgetWithText(TextFormField, 'Amount to apply'),
        -200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Amount to apply'),
        '20.02',
      );
      await tester.pump();
      expect(
        find.text('This unchanged allocation can be recorded.'),
        findsNothing,
      );
      expect(actions, 0);
    },
  );
  testWidgets('stale private detail is cleared after denied refresh', (
    tester,
  ) async {
    var denied = false;
    final repo = SpinaTreasuryRepository(
      session: session(),
      deviceId: 'external',
      journal: MemoryTreasuryJournal(),
      images: EmptySubmittedFiles(),
      client: MockClient((r) async {
        if (denied) return http.Response('{}', 403);
        if (r.url.path.endsWith('/workspace')) {
          return jsonResponse(staffWorkspace());
        }
        return jsonResponse({
          'id': event,
          'version': 1,
          'account_id': account,
          'amount': '20.01',
          'reference': 'Synthetic private reference',
          'remaining_amount': '20.01',
        });
      }),
    );
    await pumpAndroidRoleFixture(
      tester,
      home: TreasuryRecordPage(
        repository: repo,
        kind: TreasuryListKind.receipts,
        id: event,
      ),
      size: const Size(360, 900),
      textScaler: TextScaler.linear(1),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('Synthetic private reference'), findsOneWidget);
    denied = true;
    await tester.tap(find.byTooltip('Refresh selected record'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Synthetic private reference'), findsNothing);
    expect(repo.workspace, isNull);
  });
}
