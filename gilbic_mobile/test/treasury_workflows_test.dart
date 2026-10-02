import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_repository.dart';
import 'package:gilbic_mobile/src/features/treasury/treasury_workspace_page.dart';
import 'package:gilbic_mobile/src/features/treasury/treasury_command_page.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';
import 'package:http/testing.dart';
import 'support/treasury_fixture.dart';

void main() {
  Future<void> mount(
    WidgetTester tester, {
    bool private = true,
    bool enabled = true,
    double width = 360,
    double scale = 1,
  }) async {
    tester.view.physicalSize = Size(width, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final repo = SpinaTreasuryRepository(
      session: session(),
      deviceId: 'external',
      journal: MemoryTreasuryJournal(),
      client: MockClient(
        (r) async => jsonResponse(
          r.url.path.endsWith('/workspace')
              ? workspace(private: private, enabled: enabled)
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
        key: ObjectKey(repo),
        theme: SpinaTheme.light,
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(
            context,
          ).copyWith(textScaler: TextScaler.linear(scale)),
          child: child!,
        ),
        home: TreasuryWorkspacePage(session: session(), repository: repo),
      ),
    );
    await tester.pumpAndSettle();
  }

  tearDown(() {});
  testWidgets(
    'missing opening is unavailable and scoped staff cannot see wallet history',
    (tester) async {
      await mount(tester, private: false);
      expect(find.text('Account balance'), findsNothing);
      expect(find.text('Movements'), findsNothing);
      expect(find.text('Reconciliations'), findsNothing);
      expect(find.text('Payment proofs'), findsOneWidget);
      expect(find.text('Synthetic instructions'), findsOneWidget);
      await mount(tester);
      expect(find.text('Opening required'), findsOneWidget);
      expect(find.text('PHP 0.00'), findsNothing);
    },
  );
  testWidgets(
    'disabled setup retains truthful read state without command buttons',
    (tester) async {
      await mount(tester, enabled: false);
      expect(find.textContaining('disabled or not configured'), findsOneWidget);
      expect(find.text('Classify movement'), findsNothing);
      expect(find.text('Submit payment proof'), findsNothing);
    },
  );
  testWidgets('all narrow views retain amount and actions at large text', (
    tester,
  ) async {
    for (final width in [320.0, 360.0, 412.0]) {
      for (final scale in [1.0, 1.3, 2.0]) {
        await mount(tester, width: width, scale: scale);
        expect(tester.takeException(), isNull);
        expect(find.text('Cash and GCash Control'), findsOneWidget);
        expect(find.text('Opening required'), findsOneWidget);
        await tester.scrollUntilVisible(
          find.text('Classify movement'),
          200,
          scrollable: find.byType(Scrollable).first,
        );
        await tester.ensureVisible(find.text('Classify movement'));
        await tester.tap(find.text('Classify movement'));
        await tester.pumpAndSettle();
        expect(
          find.byType(TreasuryCommandPage),
          findsOneWidget,
          reason: 'Command opened at $width/$scale',
        );
        await tester.scrollUntilVisible(
          find.text('Reason'),
          200,
          scrollable: find.byType(Scrollable).first,
        );
        expect(find.text('Reason'), findsOneWidget);
        expect(tester.takeException(), isNull);
        await tester.pageBack();
        await tester.pumpAndSettle();
      }
    }
    tester.view.resetPhysicalSize();
    tester.view.resetDevicePixelRatio();
  });
  testWidgets('page does not treat proof review as recorded payment', (
    tester,
  ) async {
    final claim = {
      'id': event,
      'account_id': account,
      'client_id': user,
      'version': 1,
      'status': 'pending_verification',
      'current_version': {
        'version': 1,
        'amount': '90071992547409.91',
        'reference': 'Synthetic recipient reference',
        'loan_ids': [ledger],
        'media_type': 'image/png',
      },
      'receipt': null,
      'official_payment_posted': false,
    };
    final repo = SpinaTreasuryRepository(
      session: session(),
      deviceId: 'external',
      journal: MemoryTreasuryJournal(),
      client: MockClient((r) async {
        if (r.url.path.endsWith('/workspace')) return jsonResponse(workspace());
        if (r.url.path.endsWith('/claims/$event')) return jsonResponse(claim);
        return jsonResponse({
          'items': [claim],
          'total_count': 1,
          'limit': 50,
          'offset': 0,
          'has_more': false,
          'totals': null,
        });
      }),
    );
    await tester.pumpWidget(
      MaterialApp(
        theme: SpinaTheme.light,
        home: TreasuryWorkspacePage(session: session(), repository: repo),
      ),
    );
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Open payment proof').first);
    await tester.tap(find.text('Open payment proof').first);
    await tester.pumpAndSettle();
    expect(find.text('PHP 90071992547409.91'), findsOneWidget);
    expect(
      find.textContaining('Proof review does not record a loan payment'),
      findsOneWidget,
    );
    expect(find.text('Recorded'), findsNothing);
    expect(jsonEncode(claim).contains('verified_balance'), isFalse);
  });
}
