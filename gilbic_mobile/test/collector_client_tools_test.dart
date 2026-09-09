import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_page.dart';

void main() {
  testWidgets(
    'tapping a Client opens privacy-safe Client Tools instead of full profile data',
    (tester) async {
      await _usePhoneSurface(tester);
      await tester.pumpWidget(
        MaterialApp(
          home: CollectorRoutePage(
            session: _session,
            loader: _ClientToolsRouteLoader(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('route-client-client-tools')));
      await tester.pumpAndSettle();

      expect(find.text('Client Tools'), findsOneWidget);
      expect(find.text('Payment details / other amount'), findsOneWidget);
      expect(find.text('Schedule'), findsOneWidget);
      expect(find.text('Collection location'), findsOneWidget);

      expect(find.textContaining('National ID 123'), findsNothing);
      expect(find.textContaining('TIN 456'), findsNothing);
      expect(find.textContaining('Meralco bill'), findsNothing);
      expect(find.textContaining('Residential address'), findsNothing);
      expect(find.textContaining('Location photo evidence'), findsNothing);

      expect(find.text('Rename Area'), findsNothing);
      expect(find.text('Move Area'), findsNothing);
      expect(find.text('Assign Collector'), findsNothing);
      expect(find.text('Retire Area'), findsNothing);
    },
  );

  testWidgets(
    'Client Tools delegates Payment details to the existing collection flow',
    (tester) async {
      await _usePhoneSurface(tester);
      await tester.pumpWidget(
        MaterialApp(
          home: CollectorRoutePage(
            session: _session,
            loader: _ClientToolsRouteLoader(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('route-client-client-tools')));
      await tester.pumpAndSettle();
      expect(find.text('Client Tools'), findsOneWidget);

      await tester.tap(find.text('Payment details / other amount'));
      await tester.pumpAndSettle();

      expect(find.text('Record Collection'), findsOneWidget);
      expect(find.byKey(const Key('collection-amount')), findsOneWidget);
    },
  );

  testWidgets(
    'Correction appears only for currently allowed own-unremitted collection',
    (tester) async {
      await _usePhoneSurface(tester);
      await tester.pumpWidget(
        MaterialApp(
          home: CollectorRoutePage(
            session: _session,
            loader: _ClientToolsRouteLoader(correctionAllowed: true),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('route-client-client-tools')));
      await tester.pumpAndSettle();
      expect(find.text('Correction'), findsOneWidget);

      Navigator.of(tester.element(find.text('Client Tools'))).pop();
      await tester.pumpAndSettle();

      // Fully unmount the first route so its already-loaded correctionAllowed
      // state cannot be reused by Flutter when the second scenario is pumped.
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpAndSettle();

      await tester.pumpWidget(
        MaterialApp(
          home: CollectorRoutePage(
            session: _session,
            loader: _ClientToolsRouteLoader(correctionAllowed: false),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('route-client-client-tools')));
      await tester.pumpAndSettle();
      expect(find.text('Correction'), findsNothing);
    },
  );
}

Future<void> _usePhoneSurface(WidgetTester tester) async {
  await tester.binding.setSurfaceSize(const Size(430, 900));
  addTearDown(() async {
    await tester.binding.setSurfaceSize(null);
  });
}

const UserSession _session = UserSession(
  userId: 'collector-client-tools',
  username: 'collector.tools',
  displayName: 'Collector Tools',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'collector-tools-token',
  permissions: <String>[
    'route.view',
    'collection.create',
    'collection.correct.own_unremitted',
  ],
);

class _ClientToolsRouteLoader implements CollectorRouteLoader {
  _ClientToolsRouteLoader({this.correctionAllowed = false});

  final bool correctionAllowed;

  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async {
    return CollectorRouteLoadResult(
      route: CollectorRoute(
        routeDate: DateTime(2026, 9, 9),
        collectorName: 'Collector Tools',
        areas: const <String>['Cardona › Calahan'],
        entries: <CollectorRouteEntry>[
          CollectorRouteEntry(
            id: 'tools-regular',
            clientId: 'client-tools',
            loanId: 'loan-tools-regular',
            clientName: 'Tools Client',
            area: 'Cardona › Calahan',
            loanType: 'Regular',
            dailyAmount: 100,
            balance: 4200,
            status: 'Pending',
            passCount: 0,
            routeRevision: 'loan:tools-regular:v1',
            note:
                'National ID 123 • TIN 456 • Meralco bill • Residential address 1 Main St • Location photo evidence',
            processedToday: correctionAllowed,
            todayEntryType: correctionAllowed ? 'payment' : '',
            todayCollectorName: correctionAllowed ? 'Collector Tools' : '',
            todayTransactionId: correctionAllowed ? 'tx-tools-1' : null,
            todayIsLocked: false,
            canEditToday: correctionAllowed,
            todayAmount: correctionAllowed ? 100 : 0,
          ),
        ],
        expectedTotal: 100,
      ),
      syncedAt: DateTime.utc(2026, 9, 9, 2),
      isFromCache: false,
    );
  }
}
