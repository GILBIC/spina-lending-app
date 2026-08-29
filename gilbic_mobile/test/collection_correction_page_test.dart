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
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

void main() {
  testWidgets(
    'shows allocation first and keeps covered dates plus audit history under details',
    (tester) async {
      final history = _FakeHistoryRepository();
      await tester.pumpWidget(
        MaterialApp(
          theme: SpinaTheme.light,
          home: CollectionCorrectionPage(
            session: _session,
            entry: _entry,
            collectionDate: DateTime(2026, 8, 2),
            repository: _FakeCorrectionRepository(),
            historyRepository: history,
            deviceIdentityProvider: _deviceIdentityProvider(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('Edit Collection'), findsOneWidget);
      expect(find.text('Recorded by: Test Collector'), findsOneWidget);
      expect(find.text('Allocation'), findsOneWidget);
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

      await tester.tap(
        find.byKey(const Key('correction-covered-obligations-details')),
      );
      await tester.pumpAndSettle();

      expect(find.text('• 2026-08-04'), findsOneWidget);
      expect(
        find.byKey(const Key('correction-audit-history-title')),
        findsOneWidget,
      );
      expect(find.text('Version 1 · Test Collector'), findsOneWidget);
      expect(find.text('Reason: Wrong amount'), findsOneWidget);
      expect(find.text('Before: Advance · ₱120.00'), findsOneWidget);
      expect(find.text('After: Advance · ₱100.00'), findsOneWidget);
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
    },
  );

  testWidgets('correction history failure gives safe retry guidance', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: SpinaTheme.light,
        home: CollectionCorrectionPage(
          session: _session,
          entry: _entry,
          collectionDate: DateTime(2026, 8, 2),
          repository: _FakeCorrectionRepository(),
          historyRepository: const _FailingHistoryRepository(),
          deviceIdentityProvider: _deviceIdentityProvider(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(
      find.byKey(const Key('correction-covered-obligations-details')),
    );
    await tester.pumpAndSettle();

    expect(
      find.text(
        'Gilbic could not load correction history. Check your connection, then tap Retry.',
      ),
      findsOneWidget,
    );
    expect(find.textContaining('10.0.2.2'), findsNothing);
  });

  testWidgets('stale correction gives refresh and review guidance', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(800, 1400));
    addTearDown(() async => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        theme: SpinaTheme.light,
        home: CollectionCorrectionPage(
          session: _session,
          entry: _entry,
          collectionDate: DateTime(2026, 8, 2),
          repository: const _FailingCorrectionRepository(),
          deviceIdentityProvider: _deviceIdentityProvider(),
        ),
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
    await tester.tap(find.byKey(const Key('submit-collection-correction')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('confirm-collection-correction')));
    await tester.pumpAndSettle();

    expect(
      find.text(
        'This route changed after you opened it. Refresh the route, review the client, then try again.',
      ),
      findsOneWidget,
    );
    expect(find.text('Internal route revision conflict.'), findsNothing);
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
