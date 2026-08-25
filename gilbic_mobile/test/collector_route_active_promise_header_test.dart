import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_header_cards.dart';

void main() {
  testWidgets('route header reuses the single active promise reminder', (tester) async {
    final route = CollectorRoute(
      routeDate: DateTime(2026, 8, 25),
      collectorName: 'Collector One',
      areas: const <String>['Cardona'],
      expectedTotal: 100,
      entries: const <CollectorRouteEntry>[
        CollectorRouteEntry(
          id: 'entry-1',
          clientId: 'client-1',
          loanId: 'loan-1',
          clientName: 'Promise Client',
          area: 'Cardona',
          loanType: 'Regular',
          dailyAmount: 100,
          balance: 900,
          status: 'Pending',
          passCount: 1,
          collectionMessage:
              'Ready for mobile collection. Promise: 2026-08-28 · ₱200.00 remaining · Pending.',
        ),
      ],
    );
    final result = CollectorRouteLoadResult(
      route: route,
      syncedAt: DateTime(2026, 8, 25, 10),
      isFromCache: false,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: CollectorRouteHeaderCard(
            result: result,
            route: route,
            clientCount: 1,
          ),
        ),
      ),
    );

    expect(
      find.text('Promise: 2026-08-28 · ₱200.00 remaining · Pending.'),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('collector-header-active-promise')),
      findsOneWidget,
    );
  });

  testWidgets('route header stays compact when several clients have promises', (
    tester,
  ) async {
    final route = CollectorRoute(
      routeDate: DateTime(2026, 8, 25),
      collectorName: 'Collector One',
      areas: const <String>['Cardona'],
      expectedTotal: 200,
      entries: const <CollectorRouteEntry>[
        CollectorRouteEntry(
          id: 'entry-1',
          clientId: 'client-1',
          loanId: 'loan-1',
          clientName: 'Promise Client One',
          area: 'Cardona',
          loanType: 'Regular',
          dailyAmount: 100,
          balance: 900,
          status: 'Pending',
          passCount: 1,
          collectionMessage:
              'Ready. Promise: 2026-08-28 · ₱200.00 remaining · Pending.',
        ),
        CollectorRouteEntry(
          id: 'entry-2',
          clientId: 'client-2',
          loanId: 'loan-2',
          clientName: 'Promise Client Two',
          area: 'Cardona',
          loanType: 'Regular',
          dailyAmount: 100,
          balance: 800,
          status: 'Pending',
          passCount: 1,
          collectionMessage:
              'Ready. Promise: 2026-08-29 · ₱150.00 remaining · Pending.',
        ),
      ],
    );
    final result = CollectorRouteLoadResult(
      route: route,
      syncedAt: DateTime(2026, 8, 25, 10),
      isFromCache: false,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: CollectorRouteHeaderCard(
            result: result,
            route: route,
            clientCount: 2,
          ),
        ),
      ),
    );

    expect(find.textContaining('2 active promises'), findsOneWidget);
    expect(
      find.byKey(const Key('collector-header-active-promises')),
      findsOneWidget,
    );
  });
}
