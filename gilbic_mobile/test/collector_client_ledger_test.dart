import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_grouping.dart';
import 'package:gilbic_mobile/src/features/collector/collector_client_ledger.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

void main() {
  testWidgets('real ledger uses one atomic Pay for Regular plus 7x7', (tester) async {
    final recorded = <CollectorRouteEntry>[];
    final combined = <CollectorRouteClientGroup>[];
    final group = CollectorRouteAreaGroup(
      area: 'Balayong',
      clients: <CollectorRouteClientGroup>[
        CollectorRouteClientGroup(
          clientId: 'client-1',
          clientName: 'Ana Dela Cruz',
          area: 'Balayong',
          loans: const <CollectorRouteEntry>[
            CollectorRouteEntry(
              id: 'regular-1',
              clientId: 'client-1',
              loanId: 'loan-r',
              clientName: 'Ana Dela Cruz',
              area: 'Balayong',
              loanType: 'Regular',
              dailyAmount: 100,
              balance: 4800,
              status: 'Pending',
              passCount: 0,
              routeRevision: 'loan:r:v1',
            ),
            CollectorRouteEntry(
              id: 'seven-1',
              clientId: 'client-1',
              loanId: 'loan-7',
              clientName: 'Ana Dela Cruz',
              area: 'Balayong',
              loanType: '7x7',
              dailyAmount: 50,
              balance: 3000,
              status: 'Pending',
              passCount: 0,
              routeRevision: 'loan:7:v1',
              sevenBySevenMobileEnabled: true,
            ),
          ],
        ),
      ],
    );

    await tester.binding.setSurfaceSize(const Size(430, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        theme: SpinaTheme.light,
        home: Scaffold(
          body: CollectorClientLedgerSection(
            group: group,
            expandedClients: const <String>{},
            directPayBlockedReasonFor: (_) => null,
            payingLoanIds: const <String>{},
            pendingDirectLoanIds: const <String>{},
            onToggleClient: (_) {},
            onRecord: recorded.add,
            onRecordCombined: combined.add,
            detailsBuilder: (_) => const SizedBox.shrink(),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('AREA: BALAYONG'), findsOneWidget);
    expect(find.text('CLIENT / STATUS'), findsOneWidget);
    expect(find.text('REG'), findsOneWidget);
    expect(find.text('7x7'), findsOneWidget);
    expect(find.text('TODAY'), findsOneWidget);
    expect(find.text('Ana Dela Cruz'), findsOneWidget);
    expect(find.text('₱100'), findsOneWidget);
    expect(find.text('₱50'), findsOneWidget);
    expect(find.text('₱150'), findsOneWidget);
    expect(find.text('NOT COLLECTED'), findsOneWidget);
    expect(find.text('Pay'), findsOneWidget);

    await tester.tap(find.byKey(const Key('record-client-client-1')));
    await tester.pumpAndSettle();
    expect(recorded, isEmpty,
        reason: 'The combined tap must never become two independent mobile calls.');
    expect(combined, hasLength(1));
    expect(combined.single.clientId, 'client-1');
  });

  testWidgets('single payable loan keeps one-tap Pay on the client row', (
    tester,
  ) async {
    final recorded = <CollectorRouteEntry>[];
    final combined = <CollectorRouteClientGroup>[];
    const entry = CollectorRouteEntry(
      id: 'regular-only',
      clientId: 'client-2',
      loanId: 'loan-2',
      clientName: 'Ben Santos',
      area: 'Balayong',
      loanType: 'Regular',
      dailyAmount: 100,
      balance: 4700,
      status: 'Pending',
      passCount: 0,
      routeRevision: 'loan:2:v1',
    );
    final group = CollectorRouteAreaGroup(
      area: 'Balayong',
      clients: <CollectorRouteClientGroup>[
        const CollectorRouteClientGroup(
          clientId: 'client-2',
          clientName: 'Ben Santos',
          area: 'Balayong',
          loans: <CollectorRouteEntry>[entry],
        ),
      ],
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: SpinaTheme.light,
        home: Scaffold(
          body: CollectorClientLedgerSection(
            group: group,
            expandedClients: const <String>{},
            directPayBlockedReasonFor: (_) => null,
            payingLoanIds: const <String>{},
            pendingDirectLoanIds: const <String>{},
            onToggleClient: (_) {},
            onRecord: recorded.add,
            onRecordCombined: combined.add,
            detailsBuilder: (_) => const SizedBox.shrink(),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Pay'), findsOneWidget);
    expect(find.text('₱100'), findsWidgets);
    await tester.tap(find.byKey(const Key('record-collection-regular-only')));
    await tester.pump();
    expect(recorded, <CollectorRouteEntry>[entry]);
    expect(combined, isEmpty);
  });
}