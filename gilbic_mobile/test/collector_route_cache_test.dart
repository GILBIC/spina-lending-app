import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache.dart';

void main() {
  test('stores and clears a route snapshot per authenticated user', () async {
    final cache = MemoryCollectorRouteCache();
    final route = _route();
    final syncedAt = DateTime.utc(2026, 7, 31, 5, 10);

    await cache.writeForUser('collector-1', route, syncedAt);

    final saved = await cache.readForUser('collector-1');
    expect(saved, isNotNull);
    expect(saved!.route.collectorName, 'Collector One');
    expect(saved.route.entries.single.clientName, 'Ana Client');
    expect(saved.syncedAt, syncedAt);
    expect(await cache.readForUser('collector-2'), isNull);

    await cache.clearForUser('collector-1');
    expect(await cache.readForUser('collector-1'), isNull);
  });

  test('route serialization preserves offline display fields', () {
    final original = _route();
    final restored = CollectorRoute.fromPayload(original.toJson());

    expect(restored.routeDate, original.routeDate);
    expect(restored.areas, original.areas);
    expect(restored.expectedTotal, original.expectedTotal);
    expect(restored.entries.single.balance, 4800);
    expect(restored.entries.single.passCount, 2);
    expect(restored.entries.single.advanceUntil, DateTime.utc(2026, 8, 2));
    expect(restored.entries.single.note, 'Call before visiting');
  });
}

CollectorRoute _route() {
  return CollectorRoute(
    routeDate: DateTime.utc(2026, 7, 31),
    collectorName: 'Collector One',
    areas: const <String>['Cardona'],
    expectedTotal: 200,
    entries: <CollectorRouteEntry>[
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
        passCount: 2,
        lastPaymentDate: DateTime.utc(2026, 7, 30),
        advanceUntil: DateTime.utc(2026, 8, 2),
        note: 'Call before visiting',
      ),
    ],
  );
}
