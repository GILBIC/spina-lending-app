import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/features/collector/collector_master_review_page.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

void main() {
  testWidgets('Master Review summarizes every assigned area and unresolved client', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(430, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        theme: SpinaTheme.light,
        home: CollectorMasterReviewPage(
          session: _session,
          loader: _MasterReviewLoader(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('collector-master-review-page')), findsOneWidget);
    expect(find.text('All-area collection check'), findsOneWidget);
    expect(find.text('AREA: BALAYONG'), findsOneWidget);
    expect(find.text('AREA: CALAHAN'), findsOneWidget);
    expect(find.text('Who still needs action'), findsOneWidget);
    expect(find.byKey(const Key('master-review-client-client-ana')), findsOneWidget);
    expect(find.text('MISSED 1'), findsOneWidget);
    expect(find.text('DPD 1'), findsOneWidget);
    expect(find.text('GCASH NOTE'), findsOneWidget);
    expect(find.textContaining('Regular note: Pays by GCash'), findsOneWidget);
    expect(find.text('Cora Garcia'), findsOneWidget);
    expect(find.textContaining('ADV / advance coverage'), findsOneWidget);
  });
}

const UserSession _session = UserSession(
  userId: 'collector-1',
  username: 'collector.one',
  displayName: 'Collector One',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'token',
  permissions: <String>['route.view', 'collection.create'],
);

class _MasterReviewLoader implements CollectorRouteLoader {
  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async {
    return CollectorRouteLoadResult(
      route: CollectorRoute(
        routeDate: DateTime(2026, 8, 15),
        collectorName: 'Collector One',
        areas: const <String>['BALAYONG', 'CALAHAN'],
        expectedTotal: 350,
        entries: <CollectorRouteEntry>[
          CollectorRouteEntry(
            id: 'ana-reg',
            clientId: 'client-ana',
            loanId: 'loan-ana-reg',
            clientName: 'Ana Dela Cruz',
            area: 'BALAYONG',
            loanType: 'Regular',
            dailyAmount: 100,
            balance: 4200,
            status: 'Missed payment',
            passCount: 1,
            note: 'Pays by GCash after work.',
            contractDaysPastDue: 1,
            contractTodayScheduledAmount: 100,
            contractTodayUnpaidAmount: 100,
            contractNextUnpaidDate: DateTime(2026, 8, 14),
            contractNextUnpaidAmount: 100,
          ),
          const CollectorRouteEntry(
            id: 'ana-7x7',
            clientId: 'client-ana',
            loanId: 'loan-ana-7x7',
            clientName: 'Ana Dela Cruz',
            area: 'BALAYONG',
            loanType: '7x7',
            dailyAmount: 50,
            balance: 950,
            status: 'Pending',
            passCount: 0,
            contractTodayScheduledAmount: 50,
            contractTodayUnpaidAmount: 50,
          ),
          const CollectorRouteEntry(
            id: 'ben-reg',
            clientId: 'client-ben',
            loanId: 'loan-ben-reg',
            clientName: 'Ben Santos',
            area: 'BALAYONG',
            loanType: 'Regular',
            dailyAmount: 100,
            balance: 3000,
            status: 'Recorded today',
            passCount: 0,
            processedToday: true,
            todayEntryType: 'payment',
            todayAmount: 100,
          ),
          CollectorRouteEntry(
            id: 'cora-reg',
            clientId: 'client-cora',
            loanId: 'loan-cora-reg',
            clientName: 'Cora Garcia',
            area: 'CALAHAN',
            loanType: 'Regular',
            dailyAmount: 100,
            balance: 2200,
            status: 'Covered',
            passCount: 0,
            advanceUntil: DateTime(2026, 8, 17),
            contractTodayAlreadyCovered: true,
          ),
        ],
      ),
      syncedAt: DateTime(2026, 8, 15, 10, 30),
      isFromCache: false,
    );
  }
}
