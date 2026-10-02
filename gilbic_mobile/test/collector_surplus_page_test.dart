import 'package:gilbic_mobile/src/core/media/private_image_store.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:gilbic_mobile/src/core/treasury/collector_surplus_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/features/treasury/collector_surplus_page.dart';
import 'support/collector_surplus_fixture.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_repository.dart';
import 'package:gilbic_mobile/src/features/treasury/treasury_workspace_page.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';
import 'package:http/testing.dart';
import 'support/treasury_fixture.dart';

void main() {
  testWidgets(
    'own return requires reviewed deliberate phase and preserves amount without claiming paid',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(800, 1600));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      var posts = 0;
      final repo = SpinaTreasuryRepository(
        session: session(),
        deviceId: 'external',
        journal: MemoryTreasuryJournal(),
        client: MockClient((r) async {
          if (r.url.path.endsWith('/workspace')) {
            return jsonResponse(surplusWorkspace());
          }
          if (r.url.path.contains('/credits/')) {
            return jsonResponse(surplusCredit());
          }
          posts++;
          final body = jsonDecode(r.body) as Map;
          expect(body.containsKey('account_id'), false);
          expect(body['amount'], '40.00');
          final row = {
            'id': surplusRequest,
            'version': 1,
            'credit_id': event,
            'collector_user_id': user,
            'ledger_context_id': ledger,
            'amount': '40.00',
            'status': 'requested',
            'destination': body['destination'],
          };
          final response = surplusOutcome(
            action: 'collector_surplus_return_request',
            slot: 'request',
            principal: row,
            disposition: 'requested',
            extra: {'credit': surplusCredit()},
          )..['request_id'] = body['request_id'];
          return jsonResponse(response);
        }),
      );
      await repo.loadCollectorSurplus(mode: 'own');
      await tester.pumpWidget(
        MaterialApp(
          theme: SpinaTheme.light,
          home: CollectorSurplusActionForm(
            repository: repo,
            action: TreasuryAction.collectorSurplusReturnRequest,
            initial: {'credit_id': event, 'credit_version': 1},
          ),
        ),
      );
      await tester.enterText(
        find.byKey(const Key('collector-field-amount')),
        '40.00',
      );
      await tester.enterText(
        find.byKey(const Key('collector-field-reason')),
        'Return requested',
      );
      await tester.tap(find.text('Review and confirm phase'));
      await tester.pumpAndSettle();
      expect(posts, 0);
      await tester.tap(find.byType(CheckboxListTile).last);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Review and confirm phase'));
      await tester.pumpAndSettle();
      expect(posts, 0);
      expect(find.textContaining('amount: PHP 40.00'), findsOneWidget);
      await tester.tap(find.text('Confirm this phase'));
      await tester.pumpAndSettle();
      expect(posts, 1);
      expect(
        find.textContaining('Request recorded - approval'),
        findsOneWidget,
      );
      expect(find.text('Collector return paid'), findsNothing);
      expect(
        tester
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, 'Review and confirm phase'),
            )
            .onPressed,
        isNull,
      );
      repo.dispose();
    },
  );
  testWidgets('denied private form cannot reopen camera or file tasks', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(800, 1600));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final repo = SpinaTreasuryRepository(
      session: session(),
      deviceId: 'external',
      images: _EmptyPrivateFiles(),
      journal: MemoryTreasuryJournal(),
      client: MockClient((_) async => http.Response('{}', 403)),
    );
    await tester.runAsync(() async {
      await expectLater(repo.loadCollectorSurplus(), throwsA(anything));
    });
    expect(repo.denied, true);
    await tester.pumpWidget(
      MaterialApp(
        home: CollectorSurplusActionForm(
          repository: repo,
          action: TreasuryAction.collectorCountRecord,
          account: CollectorSurplusAccount(
            (surplusWorkspace(own: false)['accounts'] as List).single,
          ),
          initial: {
            'remittance_id': surplusRemittance,
            'source_digest': 'a' * 64,
          },
        ),
      ),
    );
    await tester.pumpAndSettle();
    for (final label in ['Select private evidence', 'Camera evidence']) {
      expect(
        tester
            .widget<OutlinedButton>(find.widgetWithText(OutlinedButton, label))
            .onPressed,
        isNull,
      );
    }
    repo.dispose();
  });

  testWidgets(
    'existing Treasury workspace opens local Collector Excess without another role workspace',
    (tester) async {
      final repo = SpinaTreasuryRepository(
        session: session(),
        deviceId: 'external',
        journal: MemoryTreasuryJournal(),
        client: MockClient(
          (r) async => jsonResponse(
            r.url.path.endsWith('/workspace')
                ? workspace()
                : {
                    'items': [],
                    'total_count': 0,
                    'limit': 50,
                    'offset': 0,
                    'has_more': false,
                    'totals': null,
                  },
          ),
        ),
      );
      await tester.pumpWidget(
        MaterialApp(
          theme: SpinaTheme.light,
          home: TreasuryWorkspacePage(session: session(), repository: repo),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.byTooltip('Collector Excess'), findsOneWidget);
    },
  );
}

class _EmptyPrivateFiles extends PrivateImageStore {
  @override
  Future<void> cleanup({String? keepPath}) async {}
}
