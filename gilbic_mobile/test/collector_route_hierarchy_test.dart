import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_page.dart';

void main() {
  testWidgets(
    'Collector opens the Area hierarchy to one compact deep Client row',
    (tester) async {
      await _usePhoneSurface(tester);
      await tester.pumpWidget(
        MaterialApp(
          home: CollectorRoutePage(
            session: _session,
            loader: _HierarchyRouteLoader(combinedDeepClient: true),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('route-area-cardona')), findsOneWidget);
      expect(find.byKey(const Key('route-area-calahan')), findsOneWidget);
      expect(find.byKey(const Key('route-area-balayong')), findsNothing);
      expect(find.text('Deep Client'), findsNothing);

      await tester.tap(find.byKey(const Key('route-area-calahan')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('route-area-balayong')), findsOneWidget);
      expect(find.byKey(const Key('route-area-nia')), findsOneWidget);
      expect(find.byKey(const Key('route-area-nia-east')), findsNothing);
      expect(find.text('Deep Client'), findsNothing);

      await tester.tap(find.byKey(const Key('route-area-balayong')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('route-area-mabini')), findsOneWidget);
      expect(find.text('Deep Client'), findsOneWidget);
      expect(
        find.byKey(const Key('record-client-client-deep')),
        findsOneWidget,
      );

      expect(find.textContaining('National ID 123'), findsNothing);
      expect(find.textContaining('Meralco bill'), findsNothing);
      expect(find.textContaining('Residential address'), findsNothing);
      expect(find.textContaining('Location photo evidence'), findsNothing);
    },
  );

  testWidgets(
    'payment and refresh never auto-expand an untouched Area branch',
    (tester) async {
      await _usePhoneSurface(tester);
      final loader = _HierarchyRouteLoader(combinedDeepClient: false);
      final payments = _RecordingPaymentRepository();
      await tester.pumpWidget(
        MaterialApp(
          home: CollectorRoutePage(
            session: _session,
            loader: loader,
            paymentRepository: payments,
            deviceIdentityProvider: _deviceIdentityProvider(),
            deviceSequence: MemoryCollectionDeviceSequence(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('route-area-calahan')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('route-area-balayong')));
      await tester.pumpAndSettle();

      expect(find.text('Deep Client'), findsOneWidget);
      expect(find.byKey(const Key('route-area-nia')), findsOneWidget);
      expect(find.byKey(const Key('route-area-nia-east')), findsNothing);

      await tester.tap(
        find.byKey(const Key('record-collection-deep-regular')),
      );
      await tester.pumpAndSettle();

      expect(payments.drafts, hasLength(1));
      expect(loader.loadCount, 2);
      expect(find.byKey(const Key('route-area-nia-east')), findsNothing);

      await tester.tap(find.byTooltip('Refresh route'));
      await tester.pumpAndSettle();

      expect(loader.loadCount, 3);
      expect(find.byKey(const Key('route-area-nia-east')), findsNothing);
    },
  );

  testWidgets(
    'offline cached hierarchy stays visible while collection writes stay disabled',
    (tester) async {
      await _usePhoneSurface(tester);
      await tester.pumpWidget(
        MaterialApp(
          home: CollectorRoutePage(
            session: _session,
            loader: _HierarchyRouteLoader(
              combinedDeepClient: false,
              isFromCache: true,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('collector-offline-read-only')),
        findsOneWidget,
      );
      expect(find.byKey(const Key('route-area-cardona')), findsOneWidget);
      expect(find.byKey(const Key('route-area-calahan')), findsOneWidget);

      await tester.tap(find.byKey(const Key('route-area-calahan')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('route-area-balayong')));
      await tester.pumpAndSettle();

      expect(find.text('Deep Client'), findsOneWidget);
      final payButton = tester.widget<FilledButton>(
        find.byKey(const Key('record-collection-deep-regular')),
      );
      expect(payButton.onPressed, isNull);
    },
  );
}

Future<void> _usePhoneSurface(WidgetTester tester) async {
  await tester.binding.setSurfaceSize(const Size(430, 1100));
  addTearDown(() async {
    await tester.binding.setSurfaceSize(null);
  });
}

const UserSession _session = UserSession(
  userId: 'collector-hierarchy',
  username: 'collector.hierarchy',
  displayName: 'Hierarchy Collector',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'hierarchy-token',
  permissions: <String>['route.view', 'collection.create'],
);

class _HierarchyRouteLoader implements CollectorRouteLoader {
  _HierarchyRouteLoader({
    required this.combinedDeepClient,
    this.isFromCache = false,
  });

  final bool combinedDeepClient;
  final bool isFromCache;
  int loadCount = 0;

  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async {
    loadCount += 1;
    final entries = <CollectorRouteEntry>[
      const CollectorRouteEntry(
        id: 'deep-regular',
        clientId: 'client-deep',
        loanId: 'loan-deep-regular',
        clientName: 'Deep Client',
        area: 'Cardona › Calahan › Balayong › Mabini St.',
        areaUid: 'mabini',
        loanType: 'Regular',
        dailyAmount: 100,
        balance: 4800,
        status: 'Pending',
        passCount: 0,
        routeRevision: 'loan:deep-regular:v1',
        note:
            'National ID 123 • Meralco bill • Residential address 1 Main St • Location photo evidence',
      ),
      if (combinedDeepClient)
        const CollectorRouteEntry(
          id: 'deep-7x7',
          clientId: 'client-deep',
          loanId: 'loan-deep-7x7',
          clientName: 'Deep Client',
          area: 'Cardona › Calahan › Balayong › Mabini St.',
          areaUid: 'mabini',
          loanType: '7x7',
          dailyAmount: 50,
          balance: 3000,
          status: 'Pending',
          passCount: 0,
          routeRevision: 'loan:deep-7x7:v1',
          sevenBySevenMobileEnabled: true,
        ),
      const CollectorRouteEntry(
        id: 'nia-regular',
        clientId: 'client-nia',
        loanId: 'loan-nia-regular',
        clientName: 'NIA Client',
        area: 'Cardona › Calahan › NIA › NIA East',
        areaUid: 'nia-east',
        loanType: 'Regular',
        dailyAmount: 80,
        balance: 1200,
        status: 'Pending',
        passCount: 0,
        routeRevision: 'loan:nia-regular:v1',
      ),
    ];

    return CollectorRouteLoadResult(
      route: CollectorRoute(
        routeDate: DateTime(2026, 9, 9),
        collectorName: 'Hierarchy Collector',
        areas: const <String>['Cardona › Calahan'],
        areaNodes: _areaNodes,
        entries: entries,
        expectedTotal: entries.fold<double>(
          0,
          (total, entry) => total + entry.dailyAmount,
        ),
      ),
      syncedAt: DateTime.utc(2026, 9, 9, 1),
      isFromCache: isFromCache,
    );
  }
}

const List<CollectorRouteAreaNode> _areaNodes = <CollectorRouteAreaNode>[
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
    areaUid: 'calahan',
    parentAreaUid: 'cardona',
    name: 'Calahan',
    fullPath: 'Cardona › Calahan',
    depth: 1,
    sortOrder: 0,
    isLegacyUnmapped: false,
  ),
  CollectorRouteAreaNode(
    areaUid: 'balayong',
    parentAreaUid: 'calahan',
    name: 'Balayong',
    fullPath: 'Cardona › Calahan › Balayong',
    depth: 2,
    sortOrder: 0,
    isLegacyUnmapped: false,
  ),
  CollectorRouteAreaNode(
    areaUid: 'mabini',
    parentAreaUid: 'balayong',
    name: 'Mabini St.',
    fullPath: 'Cardona › Calahan › Balayong › Mabini St.',
    depth: 3,
    sortOrder: 0,
    isLegacyUnmapped: false,
  ),
  CollectorRouteAreaNode(
    areaUid: 'nia',
    parentAreaUid: 'calahan',
    name: 'NIA',
    fullPath: 'Cardona › Calahan › NIA',
    depth: 2,
    sortOrder: 1,
    isLegacyUnmapped: false,
  ),
  CollectorRouteAreaNode(
    areaUid: 'nia-east',
    parentAreaUid: 'nia',
    name: 'NIA East',
    fullPath: 'Cardona › Calahan › NIA › NIA East',
    depth: 3,
    sortOrder: 0,
    isLegacyUnmapped: false,
  ),
];

DeviceIdentityProvider _deviceIdentityProvider() {
  return DeviceIdentityProvider(
    store: MemoryDeviceIdentityStore(),
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
    randomByteGenerator: (length) => List<int>.filled(length, 3),
  );
}

class _RecordingPaymentRepository implements PaymentSubmissionRepository {
  final List<PaymentSubmissionDraft> drafts = <PaymentSubmissionDraft>[];

  @override
  Future<PaymentSubmissionResult> submit(
    UserSession session,
    PaymentSubmissionDraft draft,
  ) async {
    drafts.add(draft);
    return PaymentSubmissionResult(
      disposition: PaymentSubmissionDisposition.accepted,
      idempotencyKey: draft.idempotencyKey,
      message: 'Payment saved.',
      receiptNumber: 'R-HIERARCHY',
      officialBalance: 4700,
    );
  }
}
