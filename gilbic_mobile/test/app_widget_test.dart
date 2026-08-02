import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/app.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/auth_repository.dart';
import 'package:gilbic_mobile/src/core/auth/session_store.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_page.dart';

void main() {
  testWidgets('opens compact ledger and expands collector audit details',
      (tester) async {
    await tester.pumpWidget(
      GilbicApp(
        sessionStore: MemorySessionStore(),
        authRepository: _FakeAuthRepository(),
        collectorRouteRepository: _FakeCollectorRouteRepository(),
        collectorRouteCache: MemoryCollectorRouteCache(),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byKey(const Key('username-field')),
      'collector.one',
    );
    await tester.enterText(
      find.byKey(const Key('password-field')),
      'secret',
    );
    await tester.tap(find.byKey(const Key('sign-in-button')));
    await tester.pumpAndSettle();

    expect(find.text('Collector Dashboard'), findsOneWidget);
    await tester.tap(find.byKey(const Key('daily-route')));
    await tester.pumpAndSettle();

    expect(find.text('Daily Route'), findsOneWidget);
    expect(find.text('Online route'), findsOneWidget);
    expect(find.text('AREA: CARDONA'), findsOneWidget);
    expect(find.text('Ana Client'), findsOneWidget);
    expect(find.text('Regular'), findsOneWidget);
    expect(find.text('7x7'), findsOneWidget);
    expect(find.text('Recorded by: Collector Two'), findsNothing);

    await tester.tap(find.byKey(const Key('route-client-client-1')));
    await tester.pumpAndSettle();

    expect(find.text('Recorded by: Collector Two'), findsOneWidget);
    expect(find.text('Reason / note: Paid at the route'), findsOneWidget);

    final footer = find.textContaining('Tap a client to show notes');
    await tester.dragUntilVisible(
      footer,
      find.byType(ListView),
      const Offset(0, -250),
    );
    expect(footer, findsOneWidget);
  });

  testWidgets('labels cached route data as an offline copy', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: CollectorRoutePage(
          session: _session,
          loader: _OfflineRouteLoader(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Offline copy'), findsOneWidget);
    expect(find.text('Ana Client'), findsOneWidget);
    expect(find.textContaining('Offline copy shown'), findsOneWidget);
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

class _FakeAuthRepository implements AuthRepository {
  @override
  Future<UserSession> signIn({
    required String username,
    required String password,
  }) async {
    expect(username, 'collector.one');
    expect(password, 'secret');
    return _session;
  }

  @override
  Future<void> signOut(UserSession session) async {}
}

class _FakeCollectorRouteRepository implements CollectorRouteRepository {
  @override
  Future<CollectorRoute> fetchToday(UserSession session) async => _route();
}

class _OfflineRouteLoader implements CollectorRouteLoader {
  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async {
    return CollectorRouteLoadResult(
      route: _route(),
      syncedAt: DateTime.utc(2026, 7, 31, 4, 30),
      isFromCache: true,
      warning: 'Offline copy shown because the SPINA server could not be reached.',
    );
  }
}

CollectorRoute _route() {
  return CollectorRoute(
    routeDate: DateTime.utc(2026, 7, 31),
    collectorName: 'Test Collector',
    areas: const <String>['Cardona'],
    expectedTotal: 275,
    entries: const <CollectorRouteEntry>[
      CollectorRouteEntry(
        id: 'entry-1',
        clientId: 'client-1',
        loanId: 'loan-1',
        clientName: 'Ana Client',
        area: 'Cardona',
        loanType: 'Regular',
        dailyAmount: 200,
        balance: 4800,
        status: 'Recorded today',
        passCount: 0,
        note: 'Paid at the route',
        processedToday: true,
        todayEntryType: 'payment',
        todayCollectorName: 'Collector Two',
      ),
      CollectorRouteEntry(
        id: 'entry-2',
        clientId: 'client-1',
        loanId: 'loan-2',
        clientName: 'Ana Client',
        area: 'Cardona',
        loanType: '7x7',
        dailyAmount: 75,
        balance: 3000,
        status: 'Desktop only',
        passCount: 0,
        canCollectMobile: false,
        canEnterPayment: false,
        collectionMessage: 'Use SPINA desktop for this loan.',
      ),
    ],
  );
}