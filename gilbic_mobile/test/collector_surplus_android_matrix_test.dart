import 'package:flutter/material.dart';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/treasury/collector_surplus_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_repository.dart';
import 'package:gilbic_mobile/src/features/treasury/collector_surplus_page.dart';
import 'package:http/testing.dart';
import 'support/treasury_fixture.dart' as t;
import 'support/collector_surplus_fixture.dart';
import 'support/android_role_fixture.dart';

void main() {
  testWidgets('surplus-count-keyboard-320-text-2.0', (tester) async {
    final repo = SpinaTreasuryRepository(
      session: t.session(),
      deviceId: 'external',
      journal: MemoryTreasuryJournal(),
      client: MockClient(
        (_) async => t.jsonResponse(surplusWorkspace(own: false)),
      ),
    );
    await repo.loadCollectorSurplus();
    final page = CollectorSurplusActionForm(
      repository: repo,
      action: TreasuryAction.collectorCountRecord,
      account: repo.surplusWorkspace!.accounts.single,
      reviewLabel: 'Synthetic REM-1 / Oct 2, 2026',
      initial: {'remittance_id': surplusRemittance, 'source_digest': 'a' * 64},
    );
    await pumpAndroidRoleFixture(
      tester,
      home: page,
      size: const Size(320, 900),
      textScaler: TextScaler.linear(2),
      viewInsets: const EdgeInsets.only(bottom: 300),
    );
    await tester.pumpAndSettle();
    final amount = find.byKey(const Key('collector-field-counted_amount'));
    await tester.ensureVisible(amount);
    await tester.enterText(amount, '90071992547409.91');
    await tester.pump(const Duration(milliseconds: 100));
    tester.testTextInput.hide();
    FocusManager.instance.primaryFocus?.unfocus();
    await tester.pumpAndSettle();
    expect(
      tester.widget<TextField>(amount).controller!.text,
      '90071992547409.91',
    );
    expect(tester.takeException(), isNull);
    await _capture(tester, 'surplus-count-keyboard-320-text-2.0');
    repo.dispose();
  });
  testWidgets('surplus-unknown-phase-320-text-2.0', (tester) async {
    final repo = SpinaTreasuryRepository(
      session: t.session(),
      deviceId: 'external',
      journal: MemoryTreasuryJournal(),
      client: MockClient((r) async {
        if (r.url.path.endsWith('/workspace')) {
          return t.jsonResponse(surplusWorkspace());
        }
        if (r.url.path.contains('/credits/')) {
          return t.jsonResponse(surplusCredit());
        }
        throw Exception('Synthetic interrupted response');
      }),
    );
    final command = TreasuryCommand(
      TreasuryAction.collectorSurplusReturnRequest,
      requestId: t.requestId,
      fields: {
        'credit_id': t.event,
        'credit_version': 1,
        'amount': '40.00',
        'destination': {'kind': 'physical_cash', 'recipient_reference': null},
        'reason': 'Synthetic return',
      },
    );
    await expectLater(repo.execute(command), throwsA(isA<TreasuryUncertain>()));
    await pumpAndroidRoleFixture(
      tester,
      home: CollectorSurplusActionForm(
        repository: repo,
        action: TreasuryAction.collectorSurplusReturnRequest,
        initial: {'credit_id': t.event, 'credit_version': 1},
      ),
      size: const Size(320, 900),
      textScaler: TextScaler.linear(2),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('new submission locked'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await _capture(tester, 'surplus-unknown-phase-320-text-2.0');
    repo.dispose();
  });

  for (final view in ['count', 'own-credit', 'return']) {
    for (final width in [320.0, 360.0, 412.0]) {
      for (final scale in [1.0, 1.3, 2.0]) {
        final name = 'surplus-$view-${width.toInt()}-text-$scale';
        testWidgets(name, (tester) async {
          final semantics = tester.ensureSemantics();
          try {
            final own = view != 'count';
            final repo = SpinaTreasuryRepository(
              session: t.session(),
              deviceId: 'external',
              journal: MemoryTreasuryJournal(),
              client: MockClient(
                (r) async => t.jsonResponse(surplusWorkspace(own: own)),
              ),
            );
            await repo.loadCollectorSurplus();
            final page = view == 'own-credit'
                ? CollectorSurplusRecordPage(
                    repository: repo,
                    kind: CollectorSurplusKind.credits,
                    record: surplusCredit(),
                  )
                : view == 'return'
                ? CollectorSurplusRecordPage(
                    repository: repo,
                    kind: CollectorSurplusKind.actions,
                    record: surplusActionRow(),
                  )
                : CollectorSurplusActionForm(
                    repository: repo,
                    action: TreasuryAction.collectorCountRecord,
                    reviewLabel: 'Synthetic REM-1 / 2026-10-02',
                    account: repo.surplusWorkspace!.accounts.single,
                    initial: {
                      'remittance_id': surplusRemittance,
                      'source_digest': 'a' * 64,
                    },
                  );
            await pumpAndroidRoleFixture(
              tester,
              home: page,
              size: Size(width, 900),
              textScaler: TextScaler.linear(scale),
            );
            await tester.pumpAndSettle();
            final themed = Theme.of(tester.element(find.byType(AppBar)));
            expect(themed.appBarTheme.titleTextStyle?.fontFamily, 'Roboto');
            expect(
              themed.appBarTheme.titleTextStyle?.fontWeight,
              FontWeight.w700,
            );
            expect(tester.takeException(), isNull);
            if (view == 'own-credit') {
              expect(
                find.textContaining('outstanding amount: PHP 100.00'),
                findsOneWidget,
              );
              expect(
                find.textContaining('available amount: PHP 60.00'),
                findsOneWidget,
              );
              expect(find.textContaining('wallet balance'), findsNothing);
            }
            await expectLater(
              tester,
              meetsGuideline(androidTapTargetGuideline),
            );
            await _capture(tester, name);
            repo.dispose();
          } finally {
            semantics.dispose();
          }
        });
      }
    }
  }
}

Future<void> _capture(WidgetTester tester, String name) async {
  final folder = Platform.environment['SPINA_SURPLUS_CAPTURE_DIR'];
  if (folder == null) return;
  final boundary = tester.renderObject<RenderRepaintBoundary>(
    find.byKey(const Key('android-role-capture')),
  );
  await tester.runAsync(() async {
    final capture = await boundary.toImage(pixelRatio: 1);
    try {
      final data = await capture.toByteData(format: ui.ImageByteFormat.png);
      if (data == null) throw StateError('Synthetic capture unavailable');
      await Directory(folder).create(recursive: true);
      await File(
        '$folder/$name.png',
      ).writeAsBytes(data.buffer.asUint8List(), flush: true);
    } finally {
      capture.dispose();
    }
  });
}
