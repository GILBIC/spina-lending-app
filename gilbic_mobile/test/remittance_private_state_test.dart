import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/remittance/cross_remittance.dart';
import 'package:gilbic_mobile/src/core/remittance/cross_remittance_repository.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collector_remittance_page.dart';
import 'package:gilbic_mobile/src/features/collector/cross_collector_remittance_page.dart';

const _digest =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
UserSession _session([String id = 'collector']) => UserSession(
  userId: id,
  username: id,
  displayName: id,
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'token-$id',
  permissions: const ['remittance.create'],
);
RemittanceSummary _summary([String name = 'Private borrower']) =>
    RemittanceSummary(
      reviewDigest: _digest,
      collectionDate: DateTime(2026, 10, 6),
      collectorName: 'Collector',
      transactionCount: 1,
      paymentCount: 1,
      unableToPayCount: 0,
      coveredPaymentCount: 0,
      clientCount: 1,
      totalAmount: 100,
      items: [
        RemittanceItem(
          transactionId: 'receipt',
          clientName: name,
          loanType: 'Regular',
          entryType: 'payment',
          amount: 100,
          receiptNumber: 'Private receipt',
          coveredDates: const [],
          note: 'Private receipt note',
        ),
      ],
    );

class _Repository extends Fake
    implements RemittanceRepository, CrossRemittanceRepository {
  SpinaApiException? readFailure;
  bool failPreview = false;
  SpinaApiException? submitFailure;
  final reads = <Completer<RemittanceSummary>>[];
  int writes = 0;
  Completer<RemittanceRecord>? pendingWrite;
  Future<void> _recipientRead() async {
    if (!failPreview && readFailure != null) throw readFailure!;
  }

  @override
  Future<List<RemittanceRecipient>> loadRecipients(
    UserSession session, {
    required String deviceId,
  }) async {
    await _recipientRead();
    return const [
      RemittanceRecipient(
        userId: 'recipient',
        fullName: 'Private recipient',
        roleName: 'Management',
      ),
    ];
  }

  @override
  Future<List<CrossRemittanceTarget>> loadTargets(
    UserSession session, {
    required String deviceId,
    required DateTime collectionDate,
  }) async {
    await _recipientRead();
    return const [
      CrossRemittanceTarget(
        recipientUserId: 'recipient',
        recipientName: 'Private recipient',
        recipientCapacity: CrossRemittanceRecipientCapacity.management,
        roleName: 'Management',
        transactionCount: 1,
        clientCount: 1,
        totalAmount: 100,
      ),
    ];
  }

  @override
  Future<RemittanceSummary> loadPreview(
    UserSession session, {
    required String deviceId,
    required DateTime collectionDate,
    String? recipientUserId,
    CrossRemittanceRecipientCapacity recipientCapacity =
        CrossRemittanceRecipientCapacity.assignedCollector,
  }) async {
    if (session.userId == 'other') return _summary('New account borrower');
    if (reads.isNotEmpty) return reads.removeAt(0).future;
    if (failPreview && readFailure != null) throw readFailure!;
    return _summary();
  }

  @override
  Future<RemittanceRecord> submit(
    UserSession session, {
    required String deviceId,
    required String expectedReviewDigest,
    required String recipientUserId,
    required DateTime collectionDate,
    CrossRemittanceRecipientCapacity recipientCapacity =
        CrossRemittanceRecipientCapacity.assignedCollector,
    String note = '',
  }) async {
    writes++;
    if (pendingWrite != null) return pendingWrite!.future;
    if (submitFailure != null) throw submitFailure!;
    throw StateError('This test never confirms a write');
  }
}

void main() {
  for (final cross in [false, true]) {
    final label = cross ? 'Cross' : 'Normal';
    final submitKey = Key(
      cross ? 'submit-cross-remittance' : 'submit-remittance',
    );
    final confirmKey = Key(
      cross ? 'confirm-cross-remittance' : 'confirm-remittance-submission',
    );
    final noteKey = Key(cross ? 'cross-remittance-note' : 'remittance-note');
    Finder refresh() => find.byWidgetPredicate(
      (w) =>
          w is IconButton &&
          w.tooltip == (cross ? 'Refresh' : 'Refresh summary'),
    );
    DeviceIdentityProvider device() => DeviceIdentityProvider(
      store: MemoryDeviceIdentityStore()..value = 'device',
      platformResolver: () => 'android',
      appVersionResolver: () async => 'test',
    );
    Widget page(
      _Repository repo,
      UserSession session,
      DeviceIdentityProvider identity,
    ) => MaterialApp(
      home: cross
          ? CrossCollectorRemittancePage(
              key: const Key('same-page'),
              session: session,
              deviceIdentityProvider: identity,
              repository: repo,
              collectionDate: DateTime(2026, 10, 6),
            )
          : CollectorRemittancePage(
              key: const Key('same-page'),
              session: session,
              deviceIdentityProvider: identity,
              repository: repo,
              collectionDate: DateTime(2026, 10, 6),
            ),
    );
    Future<void> mount(WidgetTester tester, _Repository repo) async {
      await tester.binding.setSurfaceSize(const Size(900, 1800));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(page(repo, _session(), device()));
      await tester.pumpAndSettle();
    }

    testWidgets('$label malformed HTTP 200 keeps reviewed command frozen', (
      tester,
    ) async {
      final repo = _Repository()
        ..submitFailure = const SpinaApiException(
          'Invalid JSON',
          statusCode: 200,
          code: 'invalid_server_response',
        );
      await mount(tester, repo);
      await tester.enterText(find.byKey(noteKey), 'Private handover');
      await tester.tap(find.byKey(submitKey));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(confirmKey));
      await tester.pumpAndSettle();
      expect(repo.writes, 1);
      expect(find.text('Private handover'), findsOneWidget);
      expect(tester.widget<IconButton>(refresh()).onPressed, isNull);
      expect(
        tester.widget<FilledButton>(find.byKey(submitKey)).onPressed,
        isNull,
      );
      expect(find.textContaining('check remittance history'), findsOneWidget);
    });
    for (final status in [401, 403, 426]) {
      for (final preview in [false, true]) {
        testWidgets(
          '$label $status denied ${preview ? 'preview' : 'recipients'} clears all private state',
          (tester) async {
            final repo = _Repository();
            await mount(tester, repo);
            await tester.enterText(find.byKey(noteKey), 'Private handover');
            final controller = tester
                .widget<TextField>(find.byKey(noteKey))
                .controller!;
            repo
              ..readFailure = SpinaApiException(
                'Access unavailable',
                statusCode: status,
              )
              ..failPreview = preview;
            await tester.tap(refresh());
            await tester.pumpAndSettle();
            expect(controller.text, isEmpty);
            expect(find.text('Private borrower'), findsNothing);
            expect(find.textContaining('Private recipient'), findsNothing);
            expect(find.text('Private handover'), findsNothing);
            expect(find.byKey(submitKey), findsNothing);
            expect(repo.writes, 0);
          },
        );
      }
    }
    testWidgets(
      '$label late success cannot restore state after a concurrent denial',
      (tester) async {
        final repo = _Repository();
        await mount(tester, repo);
        final deny = Completer<RemittanceSummary>(),
            late = Completer<RemittanceSummary>();
        repo.reads.addAll([deny, late]);
        final refreshAction = tester.widget<IconButton>(refresh()).onPressed!;
        refreshAction();
        await tester.pump();
        refreshAction();
        await tester.pump();
        deny.completeError(
          const SpinaApiException('Access unavailable', statusCode: 403),
        );
        await tester.pump();
        late.complete(_summary());
        await tester.pumpAndSettle();
        expect(find.text('Private borrower'), findsNothing);
        expect(find.textContaining('Private recipient'), findsNothing);
        expect(find.byKey(submitKey), findsNothing);
      },
    );
    testWidgets('$label identity change clears notes and ignores old preview', (
      tester,
    ) async {
      final repo = _Repository(), identity = device();
      await tester.binding.setSurfaceSize(const Size(900, 1800));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(page(repo, _session(), identity));
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(noteKey), 'Private handover');
      final late = Completer<RemittanceSummary>();
      repo.reads.add(late);
      await tester.tap(refresh());
      await tester.pump();
      await tester.pumpWidget(page(repo, _session('other'), identity));
      await tester.pump();
      late.complete(_summary());
      await tester.pumpAndSettle();
      expect(find.text('Private borrower'), findsNothing);
      expect(find.text('Private handover'), findsNothing);
      expect(find.text('New account borrower'), findsOneWidget);
    });
    testWidgets(
      '$label temporary failed read preserves still-authorized review',
      (tester) async {
        final repo = _Repository();
        await mount(tester, repo);
        await tester.enterText(find.byKey(noteKey), 'Private handover');
        repo.readFailure = const SpinaApiException(
          'Temporary outage',
          statusCode: 503,
        );
        await tester.tap(refresh());
        await tester.pumpAndSettle();
        expect(find.text('Private borrower'), findsOneWidget);
        expect(find.text('Private handover'), findsOneWidget);
        expect(repo.writes, 0);
      },
    );
    testWidgets(
      '$label account switch dismisses private confirmation before a write',
      (tester) async {
        final repo = _Repository(), identity = device();
        await tester.binding.setSurfaceSize(const Size(900, 1800));
        addTearDown(() => tester.binding.setSurfaceSize(null));
        await tester.pumpWidget(page(repo, _session(), identity));
        await tester.pumpAndSettle();
        await tester.enterText(find.byKey(noteKey), 'Private handover');
        await tester.tap(find.byKey(submitKey));
        await tester.pumpAndSettle();
        expect(find.byKey(confirmKey), findsOneWidget);
        await tester.pumpWidget(page(repo, _session('other'), identity));
        await tester.pumpAndSettle();
        expect(find.byKey(confirmKey), findsNothing);
        expect(find.text('Private handover'), findsNothing);
        expect(find.text('New account borrower'), findsOneWidget);
        expect(repo.writes, 0);
      },
    );
    testWidgets(
      '$label late submitted result cannot enter a different account',
      (tester) async {
        final repo = _Repository()
          ..pendingWrite = Completer<RemittanceRecord>();
        final identity = device();
        await tester.binding.setSurfaceSize(const Size(900, 1800));
        addTearDown(() => tester.binding.setSurfaceSize(null));
        await tester.pumpWidget(page(repo, _session(), identity));
        await tester.pumpAndSettle();
        await tester.tap(find.byKey(submitKey));
        await tester.pumpAndSettle();
        await tester.tap(find.byKey(confirmKey));
        await tester.pump();
        await tester.pumpWidget(page(repo, _session('other'), identity));
        await tester.pumpAndSettle();
        repo.pendingWrite!.complete(
          RemittanceRecord.fromPayload({
            'remittance_id': 'old',
            'remittance_number': 'PRIVATE-OLD-SUBMISSION',
            'items': [],
          })!,
        );
        await tester.pumpAndSettle();
        expect(find.text('PRIVATE-OLD-SUBMISSION'), findsNothing);
        expect(find.text('New account borrower'), findsOneWidget);
        expect(repo.writes, 1);
      },
    );
  }
}
