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

class _RouteLoader implements CollectorRouteLoader {
  _RouteLoader({required this.isFromCache});

  final bool isFromCache;

  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async {
    return CollectorRouteLoadResult(
      route: CollectorRoute(
        routeDate: DateTime(2026, 8, 1),
        collectorName: 'Test Collector',
        areas: const <String>['Cardona'],
        expectedTotal: 200,
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
            status: 'Pending',
            passCount: 0,
            routeRevision: 'revision-1',
          ),
        ],
      ),
      syncedAt: DateTime.utc(2026, 8, 1, 3),
      isFromCache: isFromCache,
    );
  }
}