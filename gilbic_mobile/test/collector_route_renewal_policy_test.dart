import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_header_cards.dart';

void main() {
  testWidgets('collector route keeps renewal policy out of field header', (tester) async {
    const route = CollectorRoute(
      routeDate: null,
      collectorName: 'Collector One',
      areas: <String>['Cardona'],
      entries: <CollectorRouteEntry>[],
      expectedTotal: 0,
    );
    final result = CollectorRouteLoadResult(
      route: route,
      syncedAt: DateTime.utc(2026, 8, 18, 6),
      isFromCache: false,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: CollectorRouteHeaderCard(
            result: result,
            route: route,
            clientCount: 0,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Collector: Collector One'), findsOneWidget);
    expect(find.textContaining('Online route'), findsOneWidget);
    expect(find.byKey(const Key('collector-renewal-policy')), findsNothing);
    expect(find.textContaining('Remote renewal:'), findsNothing);
    expect(find.textContaining('renewal must be completed at the office'), findsNothing);
  });
}
