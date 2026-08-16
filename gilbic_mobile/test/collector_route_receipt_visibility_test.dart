import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_page.dart';

void main() {
  test('route payload parses every same-day receipt', () {
    final route = CollectorRoute.fromPayload(<String, Object?>{
      'route_date': '2026-08-16',
      'collector_name': 'Assigned Collector',
      'areas': <String>['Cardona'],
      'expected_total': '200.00',
      'entries': <Object?>[
        <String, Object?>{
          'route_entry_id': 'loan-1',
          'client_id': 'client-1',
          'loan_id': 'loan-1',
          'client_name': 'Ana Client',
          'area': 'Cardona',
          'loan_type': 'Regular',
          'daily_amount': '200.00',
          'remaining_balance': '4850.00',
          'status': 'Recorded today',
          'pass_count': 0,
          'today_receipts': <Object?>[
            <String, Object?>{
              'transaction_id': 'tx-a',
              'receipt_number': 'R-A100',
              'amount': '100.00',
              'entry_type': 'payment',
              'collector_user_id': 'collector-a',
              'collector_name': 'Collector A',
              'is_locked': false,
              'covered_dates': <String>['2026-08-16'],
            },
            <String, Object?>{
              'transaction_id': 'tx-b',
              'receipt_number': 'R-B050',
              'amount': '50.00',
              'entry_type': 'payment',
              'collector_user_id': 'collector-b',
              'collector_name': 'Collector B',
              'is_locked': true,
              'covered_dates': <String>['2026-08-16'],
            },
          ],
        },
      ],
    });

    final receipts = route.entries.single.todayReceipts;
    expect(receipts, hasLength(2));
    expect(receipts.first.receiptNumber, 'R-A100');
    expect(receipts.first.amount, 100);
    expect(receipts.first.collectorName, 'Collector A');
    expect(receipts.last.receiptNumber, 'R-B050');
    expect(receipts.last.amount, 50);
    expect(receipts.last.collectorName, 'Collector B');
    expect(receipts.last.isLocked, isTrue);
  });

  testWidgets('expanded route shows all receipts and authoritative lacking amount', (
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
          loader: _ReceiptRouteLoader(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Lacking'), findsOneWidget);
    expect(find.textContaining('R-A100'), findsNothing);

    await tester.tap(find.byKey(const Key('route-client-client-1')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('today-receipts')), findsOneWidget);
    expect(find.text("Today's receipts • 2 • ₱150.00"), findsOneWidget);
    expect(
      find.text('Receipt R-A100 • ₱100.00 • Collector A'),
      findsOneWidget,
    );
    expect(
      find.text('Receipt R-B050 • ₱50.00 • Collector B • Locked'),
      findsOneWidget,
    );
    expect(find.text('Still due today: ₱50.00'), findsOneWidget);
  });
}

const UserSession _session = UserSession(
  userId: 'collector-owner',
  username: 'collector.owner',
  displayName: 'Assigned Collector',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'test-token',
  permissions: <String>[
    'route.view',
    'collection.create',
    'collection.correct.own_unremitted',
  ],
);

class _ReceiptRouteLoader implements CollectorRouteLoader {
  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async {
    return CollectorRouteLoadResult(
      route: CollectorRoute(
        routeDate: DateTime(2026, 8, 16),
        collectorName: 'Assigned Collector',
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
            balance: 4850,
            status: 'Recorded today',
            passCount: 0,
            routeRevision: 'loan:loan-1:v2',
            canCollectMobile: true,
            canEnterPayment: true,
            contractAllocationEnabled: true,
            contractScheduleVerified: true,
            contractDpdStatus: 'ready',
            contractBalanceReconciled: true,
            contractScheduleReady: true,
            contractCollectionReady: true,
            contractTodayScheduledAmount: 200,
            contractTodayUnpaidAmount: 50,
            processedToday: true,
            todayEntryType: 'payment',
            todayCollectorName: 'Collector B',
            todayTransactionId: 'tx-b',
            todayAmount: 50,
            todayIsLocked: false,
            canEditToday: false,
            todayReceipts: <CollectorRouteReceipt>[
              CollectorRouteReceipt(
                transactionId: 'tx-a',
                receiptNumber: 'R-A100',
                amount: 100,
                entryType: 'payment',
                collectorUserId: 'collector-a',
                collectorName: 'Collector A',
                isLocked: false,
                coveredDates: <DateTime>[DateTime(2026, 8, 16)],
              ),
              CollectorRouteReceipt(
                transactionId: 'tx-b',
                receiptNumber: 'R-B050',
                amount: 50,
                entryType: 'payment',
                collectorUserId: 'collector-b',
                collectorName: 'Collector B',
                isLocked: true,
                coveredDates: <DateTime>[DateTime(2026, 8, 16)],
              ),
            ],
          ),
        ],
      ),
      syncedAt: DateTime.utc(2026, 8, 16, 1),
      isFromCache: false,
    );
  }
}
