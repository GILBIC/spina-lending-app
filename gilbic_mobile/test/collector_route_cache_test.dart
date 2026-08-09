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
    final entry = restored.entries.single;

    expect(restored.routeDate, original.routeDate);
    expect(restored.areas, original.areas);
    expect(restored.expectedTotal, original.expectedTotal);
    expect(entry.balance, 4800);
    expect(entry.passCount, 2);
    expect(entry.advanceUntil, DateTime.utc(2026, 8, 2));
    expect(entry.note, 'Call before visiting');
    expect(entry.contractScheduleVerified, isTrue);
    expect(entry.contractDpdStatus, 'ready');
    expect(entry.contractPaymentFrequency, 'weekly');
    expect(entry.contractReference, 'CTR-2026-001');
    expect(entry.contractScheduleVersion, 2);
    expect(entry.contractBalanceReconciled, isTrue);
    expect(entry.contractScheduleReady, isTrue);
    expect(entry.contractCollectionReady, isFalse);
    expect(entry.contractTodayScheduledAmount, 200);
    expect(entry.contractTodayUnpaidAmount, 0);
    expect(entry.contractTodayAlreadyCovered, isTrue);
    expect(entry.contractNextUnpaidDate, DateTime.utc(2026, 8, 8));
    expect(entry.contractNextUnpaidAmount, 200);
    expect(entry.contractDaysPastDue, 0);
    expect(entry.contractReadinessMessage, contains('already covered by advance'));
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
        contractScheduleVerified: true,
        contractDpdStatus: 'ready',
        contractPaymentFrequency: 'weekly',
        contractReference: 'CTR-2026-001',
        contractScheduleVersion: 2,
        contractBalanceReconciled: true,
        contractScheduleReady: true,
        contractCollectionReady: false,
        contractDaysPastDue: 0,
        contractTodayScheduledAmount: 200,
        contractTodayUnpaidAmount: 0,
        contractTodayAlreadyCovered: true,
        contractNextUnpaidDate: DateTime.utc(2026, 8, 8),
        contractNextUnpaidAmount: 200,
        contractReadinessMessage:
            'Today is already covered by advance. Next unpaid installment: 2026-08-08.',
      ),
    ],
  );
}
