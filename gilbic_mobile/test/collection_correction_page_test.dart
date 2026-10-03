import 'support/android_workflow_capture.dart';
import 'support/android_role_fixture.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/collection_correction.dart';
import 'package:gilbic_mobile/src/core/payments/collection_correction_history_repository.dart';
import 'package:gilbic_mobile/src/core/payments/collection_correction_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collection_correction_page.dart';

void main() {
  testWidgets(
    'A8 saved correction receipt balance audit version remain reachable',
    (tester) async {
      final repository = _SuccessfulCorrectionRepository();
      await pumpAndroidRoleFixture(
        tester,
        size: const Size(320, 640),
        textScaler: TextScaler.linear(2),
        viewInsets: const EdgeInsets.only(bottom: 220),
        home: Scaffold(
          body: Builder(
            builder: (context) => FilledButton(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => CollectionCorrectionPage(
                    session: _session,
                    entry: _entry,
                    collectionDate: DateTime(2026, 8, 2),
                    repository: repository,
                    historyRepository: _FakeHistoryRepository(),
                    deviceIdentityProvider: _deviceIdentityProvider(),
                  ),
                ),
              ),
              child: const Text('Open synthetic correction'),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Open synthetic correction'));
      await tester.pumpAndSettle();
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      expect(find.text('Open synthetic correction'), findsOneWidget);
      expect(repository.calls, 0);
      await tester.tap(find.text('Open synthetic correction'));
      await tester.pumpAndSettle();
      final reason = find.byKey(const Key('correction-reason'));
      await tester.scrollUntilVisible(
        reason,
        180,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      await tester.enterText(reason, 'Correct amount');
      final submit = find.byKey(const Key('submit-collection-correction'));
      await tester.ensureVisible(submit);
      await tester.pumpAndSettle();
      expect(repository.calls, 0);
      await tester.tap(submit);
      await tester.pumpAndSettle();
      await expectAndroidDialogConsequenceVisible(tester, 'audit history.');
      expect(repository.calls, 0);
      await tester.tap(find.byKey(const Key('confirm-collection-correction')));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      expect(repository.calls, 1);
      expect(repository.deviceId, 'device-one');
      expect(repository.draft!.transactionId, 'transaction-1');
      expect(repository.draft!.expectedRouteRevision, _entry.routeRevision);
      expect(find.text('Correction saved'), findsOneWidget);
      expect(
        find.textContaining('Receipt: CORRECTED-TEST-00000002'),
        findsOneWidget,
      );
      expect(find.textContaining('Official balance: ₱4900.00'), findsOneWidget);
      await expectAndroidDialogConsequenceVisible(tester, 'Audit version: 2');
      await captureAndroidWorkflowScroll(tester, 'C5-saved-result-dialog');
      final semantics = tester.ensureSemantics();
      await checkAndroidWorkflowSemantics(tester);
      semantics.dispose();
      await tester.tap(find.text('Done'));
      await tester.pumpAndSettle();
      expect(find.text('Open synthetic correction'), findsOneWidget);
      expect(repository.calls, 1);
    },
  );
  testWidgets(
    'shows allocation first and keeps covered dates plus audit history under details',
    (tester) async {
      final history = _FakeHistoryRepository();
      await pumpAndroidRoleFixture(
        tester,
        size: const Size(320, 640),
        textScaler: TextScaler.linear(2),
        viewInsets: const EdgeInsets.only(bottom: 220),
        home: CollectionCorrectionPage(
          session: _session,
          entry: _entry,
          collectionDate: DateTime(2026, 8, 2),
          repository: _FakeCorrectionRepository(),
          historyRepository: history,
          deviceIdentityProvider: _deviceIdentityProvider(),
        ),
      );
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('Edit Collection'), findsOneWidget);
      expect(find.text('Recorded by: Test Collector'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.text('Allocation'),
        180,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      expect(find.text('Allocation'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.byKey(const Key('correction-covered-obligations-details')),
        180,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      expect(find.text('Exact covered dates'), findsNothing);
      expect(
        find.byKey(const Key('correction-add-covered-date')),
        findsNothing,
      );
      expect(
        find.byKey(const Key('correction-covered-obligations-details')),
        findsOneWidget,
      );
      expect(find.text('2026-08-04'), findsNothing);
      expect(find.text('Reason: Wrong amount'), findsNothing);

      await tester.ensureVisible(
        find.byKey(const Key('correction-covered-obligations-details')),
      );
      await tester.pumpAndSettle();
      await tester.tap(
        find.byKey(const Key('correction-covered-obligations-details')),
      );
      await tester.pumpAndSettle();

      expect(find.text('• 2026-08-04'), findsOneWidget);
      await tester.ensureVisible(find.text('• 2026-08-04'));
      await tester.pumpAndSettle();
      await captureAndroidWorkflow(tester, 'C5-expanded-covered-dates-visible');
      await tester.scrollUntilVisible(
        find.byKey(const Key('correction-audit-history-title')),
        180,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('correction-audit-history-title')),
        findsOneWidget,
      );
      expect(find.text('Version 1 · Test Collector'), findsOneWidget);
      expect(find.text('Reason: Wrong amount'), findsOneWidget);
      await tester.ensureVisible(find.text('Reason: Wrong amount'));
      await tester.pumpAndSettle();
      await captureAndroidWorkflow(
        tester,
        'C5-expanded-audit-version-reason-visible',
      );
      await tester.scrollUntilVisible(
        find.text('Before: Advance · ₱120.00'),
        180,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      expect(find.text('Before: Advance · ₱120.00'), findsOneWidget);
      expect(find.text('After: Advance · ₱100.00'), findsOneWidget);
      await tester.ensureVisible(find.text('After: Advance · ₱100.00'));
      await tester.pumpAndSettle();
      await captureAndroidWorkflow(
        tester,
        'C5-expanded-audit-exact-after-visible',
      );
      expect(history.requestedTransactionId, 'transaction-1');
      expect(history.requestedDeviceId, 'device-one');

      await tester.scrollUntilVisible(
        find.byKey(const Key('correction-reason')),
        300,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('correction-reason')), findsOneWidget);
      expect(
        find.byKey(const Key('submit-collection-correction')),
        findsOneWidget,
      );
      await captureAndroidWorkflowScroll(tester, 'C5-correction-form');
    },
  );

  testWidgets('correction history failure gives safe retry guidance', (
    tester,
  ) async {
    await pumpAndroidRoleFixture(
      tester,
      size: const Size(320, 640),
      textScaler: TextScaler.linear(2),
      viewInsets: const EdgeInsets.only(bottom: 220),
      home: CollectionCorrectionPage(
        session: _session,
        entry: _entry,
        collectionDate: DateTime(2026, 8, 2),
        repository: _FakeCorrectionRepository(),
        historyRepository: const _FailingHistoryRepository(),
        deviceIdentityProvider: _deviceIdentityProvider(),
      ),
    );
    await tester.pumpAndSettle();

    await tester.scrollUntilVisible(
      find.byKey(const Key('correction-covered-obligations-details')),
      180,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    await tester.tap(
      find.byKey(const Key('correction-covered-obligations-details')),
    );
    await tester.pumpAndSettle();

    expect(
      find.text(
        'SPINA could not load correction history. Check your connection, then tap Retry.',
      ),
      findsOneWidget,
    );
    expect(find.textContaining('10.0.2.2'), findsNothing);
    await captureAndroidWorkflowScroll(tester, 'C5-history-error');
  });

  testWidgets('stale correction gives refresh and review guidance', (
    tester,
  ) async {
    await pumpAndroidRoleFixture(
      tester,
      size: const Size(320, 640),
      textScaler: TextScaler.linear(2),
      viewInsets: const EdgeInsets.only(bottom: 220),
      home: CollectionCorrectionPage(
        session: _session,
        entry: _entry,
        collectionDate: DateTime(2026, 8, 2),
        repository: const _FailingCorrectionRepository(),
        deviceIdentityProvider: _deviceIdentityProvider(),
      ),
    );
    await tester.pumpAndSettle();

    final reason = find.byKey(const Key('correction-reason'));
    await tester.scrollUntilVisible(
      reason,
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.enterText(reason, 'Correct amount');
    await tester.scrollUntilVisible(
      find.byKey(const Key('submit-collection-correction')),
      180,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('submit-collection-correction')));
    await tester.pumpAndSettle();
    await captureAndroidWorkflowScroll(
      tester,
      'C5-correction-confirmation-keyboard',
    );
    expect(
      find.descendant(
        of: find.byType(AlertDialog),
        matching: find.byType(Scrollable),
      ),
      findsOneWidget,
      reason: 'Full correction consequences must be scroll-reachable',
    );
    await expectAndroidDialogConsequenceVisible(tester, 'audit history.');
    await captureAndroidWorkflow(tester, 'C5-confirmation-consequence-end');
    await tester.tap(find.byKey(const Key('confirm-collection-correction')));
    await tester.pumpAndSettle();

    expect(
      find.text(
        'This route changed after you opened it. Refresh the route, review the client, then try again.',
      ),
      findsOneWidget,
    );
    expect(find.text('Internal route revision conflict.'), findsNothing);
    await captureAndroidWorkflowScroll(tester, 'C5-stale-correction');
  });
}

const UserSession _session = UserSession(
  userId: 'collector-1',
  username: 'collector.one',
  displayName: 'Test Collector',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'token',
  permissions: <String>['collection.correct.own_unremitted'],
);

final CollectorRouteEntry _entry = CollectorRouteEntry(
  id: 'loan-1',
  clientId: 'client-1',
  loanId: 'loan-1',
  clientName: 'Ana Client',
  area: 'Cardona',
  loanType: 'Regular',
  dailyAmount: 50,
  balance: 4900,
  status: 'Recorded today',
  passCount: 0,
  processedToday: true,
  todayEntryType: 'advance',
  todayCollectorName: 'Test Collector',
  todayTransactionId: 'transaction-1',
  canEditToday: true,
  todayAmount: 100,
  todayNote: 'Two selected dates',
  routeRevision: 'route-revision-1',
  todayCoveredDates: <DateTime>[DateTime(2026, 8, 2), DateTime(2026, 8, 4)],
);

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'device-one';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

class _FakeCorrectionRepository implements CollectionCorrectionRepository {
  @override
  Future<CollectionCorrectionResult> correct(
    UserSession session, {
    required String deviceId,
    required CollectionCorrectionDraft draft,
  }) {
    throw UnimplementedError();
  }
}

class _SuccessfulCorrectionRepository
    implements CollectionCorrectionRepository {
  int calls = 0;
  String? deviceId;
  CollectionCorrectionDraft? draft;
  @override
  Future<CollectionCorrectionResult> correct(
    UserSession session, {
    required String deviceId,
    required CollectionCorrectionDraft draft,
  }) async {
    calls++;
    this.deviceId = deviceId;
    this.draft = draft;
    return CollectionCorrectionResult(
      transactionId: draft.transactionId,
      entryType: 'advance',
      amount: 100,
      coveredDates: [DateTime(2026, 8, 2), DateTime(2026, 8, 4)],
      note: 'Two selected dates',
      officialBalance: 4900,
      receiptNumber: 'CORRECTED-TEST-00000002',
      editVersion: 2,
      routeRevision: 'corrected-synthetic-revision',
      editedAt: DateTime.utc(2026, 8, 25),
    );
  }
}

class _FakeHistoryRepository implements CollectionCorrectionHistoryRepository {
  String? requestedTransactionId;
  String? requestedDeviceId;

  @override
  Future<List<CollectionCorrectionHistoryEntry>> list(
    UserSession session, {
    required String deviceId,
    required String transactionId,
  }) async {
    requestedTransactionId = transactionId;
    requestedDeviceId = deviceId;
    return <CollectionCorrectionHistoryEntry>[
      CollectionCorrectionHistoryEntry(
        editVersion: 1,
        reason: 'Wrong amount',
        previousSnapshot: const <String, dynamic>{
          'entry_type': 'advance',
          'amount': '120.00',
        },
        replacementSnapshot: const <String, dynamic>{
          'entry_type': 'advance',
          'amount': '100.00',
        },
        previousCoveredDates: <DateTime>[
          DateTime(2026, 8, 2),
          DateTime(2026, 8, 3),
        ],
        replacementCoveredDates: <DateTime>[
          DateTime(2026, 8, 2),
          DateTime(2026, 8, 4),
        ],
        editedByName: 'Test Collector',
        editedAt: DateTime.utc(2026, 8, 25, 1, 30),
      ),
    ];
  }
}

class _FailingHistoryRepository
    implements CollectionCorrectionHistoryRepository {
  const _FailingHistoryRepository();

  @override
  Future<List<CollectionCorrectionHistoryEntry>> list(
    UserSession session, {
    required String deviceId,
    required String transactionId,
  }) {
    throw StateError('SocketException: connection refused at 10.0.2.2');
  }
}

class _FailingCorrectionRepository implements CollectionCorrectionRepository {
  const _FailingCorrectionRepository();

  @override
  Future<CollectionCorrectionResult> correct(
    UserSession session, {
    required String deviceId,
    required CollectionCorrectionDraft draft,
  }) {
    throw const SpinaApiException(
      'Internal route revision conflict.',
      statusCode: 409,
      code: 'route_revision_changed',
    );
  }
}
