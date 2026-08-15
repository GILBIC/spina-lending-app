import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_page.dart';

void main() {
  testWidgets('offline route keeps collection button disabled', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: CollectorRoutePage(
          session: _session,
          loader: _RouteLoader(isFromCache: true),
        ),
      ),
    );
    await tester.pumpAndSettle();

    final button = tester.widget<FilledButton>(
      find.byKey(const Key('record-collection-entry-1')),
    );
    expect(button.onPressed, isNull);
    expect(find.textContaining('Offline route copies are read-only'), findsNothing);

    await tester.tap(find.byKey(const Key('route-client-client-1')));
    await tester.pumpAndSettle();

    expect(find.textContaining('Offline route copies are read-only'), findsOneWidget);
  });

  testWidgets('online ready route enables collection button', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: CollectorRoutePage(
          session: _session,
          loader: _RouteLoader(isFromCache: false),
        ),
      ),
    );
    await tester.pumpAndSettle();

    final button = tester.widget<FilledButton>(
      find.byKey(const Key('record-collection-entry-1')),
    );
    expect(button.onPressed, isNotNull);
    expect(find.text('Pay'), findsOneWidget);
  });

  testWidgets('expanded route shows contractual readiness guidance', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: CollectorRoutePage(
          session: _session,
          loader: _RouteLoader(isFromCache: false),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('signed-contract verification'), findsNothing);
    await tester.tap(find.byKey(const Key('route-client-client-1')));
    await tester.pumpAndSettle();

    expect(
      find.textContaining('Contract schedule: signed-contract verification'),
      findsOneWidget,
    );
  });

  testWidgets('7x7 stays desktop-only when server gate is false', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: CollectorRoutePage(
          session: _session,
          loader: _RouteLoader(
            isFromCache: false,
            entry: _sevenBySevenEntry(enabled: false),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    final button = tester.widget<FilledButton>(
      find.byKey(const Key('record-collection-entry-7x7')),
    );
    expect(button.onPressed, isNull);
    expect(find.text('Desk'), findsOneWidget);

    await tester.tap(find.byKey(const Key('route-client-client-7x7')));
    await tester.pumpAndSettle();
    expect(
      find.textContaining('protected server allocator explicitly enables'),
      findsOneWidget,
    );
  });

  testWidgets('server-enabled 7x7 exposes Pay and opens collection form', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(800, 1400));
    addTearDown(() async {
      await tester.binding.setSurfaceSize(null);
    });

    await tester.pumpWidget(
      MaterialApp(
        home: CollectorRoutePage(
          session: _session,
          loader: _RouteLoader(
            isFromCache: false,
            entry: _sevenBySevenEntry(enabled: true),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    final button = tester.widget<FilledButton>(
      find.byKey(const Key('record-collection-entry-7x7')),
    );
    expect(button.onPressed, isNotNull);
    expect(find.text('Pay'), findsOneWidget);

    await tester.tap(find.byKey(const Key('record-collection-entry-7x7')));
    await tester.pumpAndSettle();
    expect(find.text('Record Collection'), findsOneWidget);
    expect(find.byKey(const Key('collection-amount')), findsOneWidget);
    expect(find.textContaining('7x7 mobile collection is disabled'), findsNothing);
  });
}

const UserSession _session = UserSession(
  userId: 'collector-1',
  username: 'collector.one',
  displayName: 'Test Collector',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'test-token',
  permissions: <String>['route.view', 'collection.create'],
);

const CollectorRouteEntry _regularEntry = CollectorRouteEntry(
  id: 'entry-1',
  clientId: 'client-1',
  loanId: 'loan-1',
  clientName: 'Ana Client',
  area: 'Cardona',
  loanType: 'Regular',
  dailyAmount: 200,
  balance: 4800,
  status: 'Pending',
  passCount: 0,
  routeRevision: 'revision-1',
  collectionMessage:
      'Ready for mobile collection. Contract schedule: signed-contract verification is still required.',
  contractReadinessMessage:
      'Contract schedule: signed-contract verification is still required.',
);

CollectorRouteEntry _sevenBySevenEntry({required bool enabled}) {
  return CollectorRouteEntry(
    id: 'entry-7x7',
    clientId: 'client-7x7',
    loanId: 'loan-7x7',
    clientName: 'Seven Client',
    area: 'Cardona',
    loanType: '7x7',
    dailyAmount: 35,
    balance: 5000,
    status: 'Pending',
    passCount: 0,
    routeRevision: 'loan:loan-7x7:v0',
    canCollectMobile: enabled,
    canEnterPayment: enabled,
    sevenBySevenMobileEnabled: enabled,
    collectionMessage: enabled
        ? 'Ready for protected 7x7 mobile collection.'
        : 'Use SPINA desktop for this 7x7 loan.',
  );
}

class _RouteLoader implements CollectorRouteLoader {
  _RouteLoader({required this.isFromCache, this.entry = _regularEntry});

  final bool isFromCache;
  final CollectorRouteEntry entry;

  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async {
    return CollectorRouteLoadResult(
      route: CollectorRoute(
        routeDate: DateTime(2026, 8, 1),
        collectorName: 'Test Collector',
        areas: const <String>['Cardona'],
        expectedTotal: entry.dailyAmount,
        entries: <CollectorRouteEntry>[entry],
      ),
      syncedAt: DateTime.utc(2026, 8, 1, 3),
      isFromCache: isFromCache,
    );
  }
}