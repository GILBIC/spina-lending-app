import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_grouping.dart';

void main() {
  test('groups one client with multiple loan types under one area', () {
    final groups = groupCollectorRoute(
      const CollectorRoute(
        routeDate: null,
        collectorName: 'Collector One',
        areas: <String>['Cardona', 'Taytay'],
        expectedTotal: 325,
        entries: <CollectorRouteEntry>[
          CollectorRouteEntry(
            id: 'loan-7x7',
            clientId: 'client-1',
            loanId: 'loan-7x7',
            clientName: 'Ana Client',
            area: 'Cardona',
            loanType: '7x7',
            dailyAmount: 75,
            balance: 3000,
            status: 'Desktop only',
            passCount: 0,
          ),
          CollectorRouteEntry(
            id: 'loan-regular',
            clientId: 'client-1',
            loanId: 'loan-regular',
            clientName: 'Ana Client',
            area: 'Cardona',
            loanType: 'Regular',
            dailyAmount: 200,
            balance: 4800,
            status: 'Pending',
            passCount: 0,
          ),
          CollectorRouteEntry(
            id: 'loan-taytay',
            clientId: 'client-2',
            loanId: 'loan-taytay',
            clientName: 'Ben Client',
            area: 'Taytay',
            loanType: 'Regular',
            dailyAmount: 50,
            balance: 1200,
            status: 'Recorded today',
            passCount: 0,
            processedToday: true,
          ),
        ],
      ),
    );

    expect(groups.map((group) => group.area), <String>['Cardona', 'Taytay']);
    expect(groups.first.clientCount, 1);
    expect(groups.first.loanCount, 2);
    expect(groups.first.expectedTotal, 275);
    expect(groups.first.clients.single.clientName, 'Ana Client');
    expect(
      groups.first.clients.single.loans.map((loan) => loan.loanType),
      <String>['Regular', '7x7'],
    );
    expect(groups.last.clients.single.processedLoanCount, 1);
  });

  test('appends areas missing from the saved area order', () {
    final groups = groupCollectorRoute(
      const CollectorRoute(
        routeDate: null,
        collectorName: 'Collector One',
        areas: <String>['Cardona'],
        expectedTotal: 100,
        entries: <CollectorRouteEntry>[
          CollectorRouteEntry(
            id: 'loan-1',
            clientId: 'client-1',
            loanId: 'loan-1',
            clientName: 'Ana Client',
            area: 'Morong',
            loanType: 'Regular',
            dailyAmount: 100,
            balance: 1000,
            status: 'Pending',
            passCount: 0,
          ),
        ],
      ),
    );

    expect(groups.map((group) => group.area), <String>['Morong']);
  });

  test('builds an arbitrary-depth Area tree and renders a deep client once', () {
    const route = CollectorRoute(
      routeDate: null,
      collectorName: 'Collector One',
      areas: <String>['Cardona › Calahan'],
      areaNodes: <CollectorRouteAreaNode>[
        CollectorRouteAreaNode(
          areaUid: 'level-1',
          parentAreaUid: null,
          name: 'Cardona',
          fullPath: 'Cardona',
          depth: 0,
          sortOrder: 0,
          isLegacyUnmapped: false,
        ),
        CollectorRouteAreaNode(
          areaUid: 'level-2',
          parentAreaUid: 'level-1',
          name: 'Calahan',
          fullPath: 'Cardona › Calahan',
          depth: 1,
          sortOrder: 0,
          isLegacyUnmapped: false,
        ),
        CollectorRouteAreaNode(
          areaUid: 'level-3',
          parentAreaUid: 'level-2',
          name: 'Balayong',
          fullPath: 'Cardona › Calahan › Balayong',
          depth: 2,
          sortOrder: 0,
          isLegacyUnmapped: false,
        ),
        CollectorRouteAreaNode(
          areaUid: 'level-4',
          parentAreaUid: 'level-3',
          name: 'Mabini St.',
          fullPath: 'Cardona › Calahan › Balayong › Mabini St.',
          depth: 3,
          sortOrder: 0,
          isLegacyUnmapped: false,
        ),
        CollectorRouteAreaNode(
          areaUid: 'level-5',
          parentAreaUid: 'level-4',
          name: 'Purok 2',
          fullPath: 'Cardona › Calahan › Balayong › Mabini St. › Purok 2',
          depth: 4,
          sortOrder: 0,
          isLegacyUnmapped: false,
        ),
        CollectorRouteAreaNode(
          areaUid: 'level-6',
          parentAreaUid: 'level-5',
          name: 'Riverside',
          fullPath:
              'Cardona › Calahan › Balayong › Mabini St. › Purok 2 › Riverside',
          depth: 5,
          sortOrder: 0,
          isLegacyUnmapped: false,
        ),
        CollectorRouteAreaNode(
          areaUid: 'level-7',
          parentAreaUid: 'level-6',
          name: 'Block A',
          fullPath:
              'Cardona › Calahan › Balayong › Mabini St. › Purok 2 › Riverside › Block A',
          depth: 6,
          sortOrder: 0,
          isLegacyUnmapped: false,
        ),
      ],
      expectedTotal: 275,
      entries: <CollectorRouteEntry>[
        CollectorRouteEntry(
          id: 'loan-7x7',
          clientId: 'client-deep',
          loanId: 'loan-7x7',
          clientName: 'Deep Client',
          area:
              'Cardona › Calahan › Balayong › Mabini St. › Purok 2 › Riverside › Block A',
          areaUid: 'level-7',
          loanType: '7x7',
          dailyAmount: 75,
          balance: 3000,
          status: 'Pending',
          passCount: 0,
        ),
        CollectorRouteEntry(
          id: 'loan-regular',
          clientId: 'client-deep',
          loanId: 'loan-regular',
          clientName: 'Deep Client',
          area:
              'Cardona › Calahan › Balayong › Mabini St. › Purok 2 › Riverside › Block A',
          areaUid: 'level-7',
          loanType: 'Regular',
          dailyAmount: 200,
          balance: 4800,
          status: 'Pending',
          passCount: 0,
        ),
      ],
    );

    final tree = buildCollectorRouteTree(route);

    expect(tree, hasLength(1));
    const expectedNames = <String>[
      'Cardona',
      'Calahan',
      'Balayong',
      'Mabini St.',
      'Purok 2',
      'Riverside',
      'Block A',
    ];
    var current = tree.single;
    for (var index = 0; index < expectedNames.length; index += 1) {
      expect(current.name, expectedNames[index]);
      expect(current.subtreeClientCount, 1);
      if (index < expectedNames.length - 1) {
        expect(current.clients, isEmpty);
        expect(current.children, hasLength(1));
        current = current.children.single;
      }
    }

    expect(current.children, isEmpty);
    expect(current.clients, hasLength(1));
    expect(current.clients.single.clientId, 'client-deep');
    expect(
      current.clients.single.loans.map((loan) => loan.loanType),
      <String>['Regular', '7x7'],
    );

    final renderedClientIds = <String>[];
    void collectDirectClients(CollectorRouteTreeNode node) {
      renderedClientIds.addAll(node.clients.map((client) => client.clientId));
      for (final child in node.children) {
        collectDirectClients(child);
      }
    }

    collectDirectClients(tree.single);
    expect(renderedClientIds, <String>['client-deep']);
  });

  test('preserves server sibling order and safely falls back to a legacy group', () {
    const hierarchicalRoute = CollectorRoute(
      routeDate: null,
      collectorName: 'Collector One',
      areas: <String>['Cardona'],
      areaNodes: <CollectorRouteAreaNode>[
        CollectorRouteAreaNode(
          areaUid: 'cardona',
          parentAreaUid: null,
          name: 'Cardona',
          fullPath: 'Cardona',
          depth: 0,
          sortOrder: 0,
          isLegacyUnmapped: false,
        ),
        CollectorRouteAreaNode(
          areaUid: 'balayong',
          parentAreaUid: 'cardona',
          name: 'Balayong',
          fullPath: 'Cardona › Balayong',
          depth: 1,
          sortOrder: 0,
          isLegacyUnmapped: false,
        ),
        CollectorRouteAreaNode(
          areaUid: 'nia',
          parentAreaUid: 'cardona',
          name: 'NIA',
          fullPath: 'Cardona › NIA',
          depth: 1,
          sortOrder: 1,
          isLegacyUnmapped: false,
        ),
        CollectorRouteAreaNode(
          areaUid: 'main-calahan',
          parentAreaUid: 'cardona',
          name: 'Main Calahan',
          fullPath: 'Cardona › Main Calahan',
          depth: 1,
          sortOrder: 2,
          isLegacyUnmapped: false,
        ),
      ],
      expectedTotal: 0,
      entries: <CollectorRouteEntry>[],
    );

    final hierarchy = buildCollectorRouteTree(hierarchicalRoute);
    expect(
      hierarchy.single.children.map((node) => node.name),
      <String>['Balayong', 'NIA', 'Main Calahan'],
    );

    const legacyRoute = CollectorRoute(
      routeDate: null,
      collectorName: 'Collector One',
      areas: <String>['Morong'],
      areaNodes: <CollectorRouteAreaNode>[],
      expectedTotal: 100,
      entries: <CollectorRouteEntry>[
        CollectorRouteEntry(
          id: 'legacy-loan',
          clientId: 'legacy-client',
          loanId: 'legacy-loan',
          clientName: 'Legacy Client',
          area: 'Morong',
          loanType: 'Regular',
          dailyAmount: 100,
          balance: 1000,
          status: 'Pending',
          passCount: 0,
        ),
      ],
    );

    final legacyTree = buildCollectorRouteTree(legacyRoute);
    expect(legacyTree, hasLength(1));
    expect(legacyTree.single.areaUid, isNull);
    expect(legacyTree.single.name, 'Morong');
    expect(legacyTree.single.clients.single.clientId, 'legacy-client');
    expect(legacyTree.single.subtreeClientCount, 1);
  });
}
