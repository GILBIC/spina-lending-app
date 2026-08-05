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
}
