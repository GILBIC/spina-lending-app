import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_page.dart';

void main() {
  testWidgets(
    'Schedule opens a dedicated read-only Client Schedule surface',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(430, 900));
      addTearDown(() async {
        await tester.binding.setSurfaceSize(null);
      });

      await tester.pumpWidget(
        MaterialApp(
          home: CollectorRoutePage(
            session: _session,
            loader: _ScheduleRouteLoader(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('route-client-client-schedule')));
      await tester.pumpAndSettle();
      expect(find.text('Client Tools'), findsOneWidget);

      await tester.tap(find.text('Schedule'));
      await tester.pumpAndSettle();

      expect(find.text('Client Schedule'), findsOneWidget);
      expect(
        find.textContaining(
          'connected in the next Area Management step',
        ),
        findsNothing,
      );
      expect(find.text('Edit'), findsNothing);
      expect(find.text('Save'), findsNothing);
      expect(find.text('Change Maturity'), findsNothing);
    },
  );
}

const UserSession _session = UserSession(
  userId: 'collector-schedule',
  username: 'collector.schedule',
  displayName: 'Collector Schedule',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'collector-schedule-token',
  permissions: <String>[
    'route.view',
    'collection.create',
  ],
);

class _ScheduleRouteLoader implements CollectorRouteLoader {
  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async {
    return CollectorRouteLoadResult(
      route: CollectorRoute(
        routeDate: DateTime(2026, 9, 9),
        collectorName: 'Collector Schedule',
        areas: const <String>['Cardona › Calahan'],
        entries: <CollectorRouteEntry>[
          const CollectorRouteEntry(
            id: 'schedule-regular',
            clientId: 'client-schedule',
            loanId: 'loan-schedule-regular',
            clientName: 'Schedule Client',
            area: 'Cardona › Calahan',
            loanType: 'Regular',
            dailyAmount: 100,
            balance: 4200,
            status: 'Pending',
            passCount: 0,
            routeRevision: 'loan:schedule-regular:v1',
          ),
        ],
        expectedTotal: 100,
      ),
      syncedAt: DateTime.utc(2026, 9, 9, 2),
      isFromCache: false,
    );
  }
}
