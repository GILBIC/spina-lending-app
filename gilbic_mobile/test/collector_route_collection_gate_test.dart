import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_page.dart';

void main() {
  testWidgets('offline route keeps collection button disabled', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: CollectorRoutePage(
          session: _session,
          loader: _RouteLoader(isFromCache: true),
        ),
      ),
    );
    await tester.pumpAndSettle();

    final button = tester.widget<FilledButton>(
      find.byKey(const Key('record-collection-entry-1')),
    );
    expect(button.onPressed, isNull);
    expect(find.textContaining('Offline route copies are read-only'), findsNothing);

    await tester.tap(find.byKey(const Key('route-client-client-1')));
    await tester.pumpAndSettle();

    expect(find.textContaining('Offline route copies are read-only'), findsOneWidget);
  });

  testWidgets('one tap Pay posts the scheduled amount without opening a form', (
    tester,
  ) async {
    final repository = _RecordingRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: CollectorRoutePage(
          session: _session,
          loader: _RouteLoader(isFromCache: false),
          paymentRepository: repository,
          deviceIdentityProvider: _deviceIdentityProvider(),
          deviceSequence: MemoryCollectionDeviceSequence(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    final button = tester.widget<FilledButton>(
      find.byKey(const Key('record-collection-entry-1')),
    );
    expect(button.onPressed, isNotNull);
    expect(find.text('Pay'), findsOneWidget);

    await tester.tap(find.byKey(const Key('record-collection-entry-1')));
    await tester.pumpAndSettle();

    expect(find.text('Record Collection'), findsNothing);
    expect(repository.drafts, hasLength(1));
    expect(repository.drafts.single.entryType, CollectionEntryType.payment);
    expect(repository.drafts.single.amount, 200);
    expect(repository.drafts.single.coveredDates, hasLength(1));
  });

  testWidgets('expanded route keeps special payment details available', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(800, 1200));
    addTearDown(() async {
      await tester.binding.setSurfaceSize(null);
    });

    await tester.pumpWidget(
      MaterialApp(
        home: CollectorRoutePage(
          session: _session,
          loader: _RouteLoader(isFromCache: false),
          paymentRepository: _RecordingRepository(),
          deviceIdentityProvider: _deviceIdentityProvider(),
          deviceSequence: MemoryCollectionDeviceSequence(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('signed-contract verification'), findsNothing);
    await tester.tap(find.byKey(const Key('route-client-client-1')));
    await tester.pumpAndSettle();

    expect(
      find.textContaining('Contract schedule: signed-contract verification'),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('collection-details-entry-1')),
      findsOneWidget,
    );
  });

  testWidgets('7x7 stays desktop-only when server gate is false', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: CollectorRoutePage(
          session: _session,
          loader: _RouteLoader(
            isFromCache: false,
            entry: _sevenBySevenEntry(enabled: false),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    final button = tester.widget<FilledButton>(
      find.byKey(const Key('record-collection-entry-7x7')),
    );
    expect(button.onPressed, isNull);
    expect(find.text('Desk'), findsOneWidget);

    await tester.tap(find.byKey(const Key('route-client-client-7x7')));
    await tester.pumpAndSettle();
    expect(
      find.textContaining('protected server allocator explicitly enables'),
      findsOneWidget,
    );
  });

  testWidgets('server-enabled 7x7 Pay posts directly from the route', (
    tester,
  ) async {
    final repository = _RecordingRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: CollectorRoutePage(
          session: _session,
          loader: _RouteLoader(
            isFromCache: false,
            entry: _sevenBySevenEntry(enabled: true),
          ),
          paymentRepository: repository,
          deviceIdentityProvider: _deviceIdentityProvider(),
          deviceSequence: MemoryCollectionDeviceSequence(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    final button = tester.widget<FilledButton>(
      find.byKey(const Key('record-collection-entry-7x7')),
    );
    expect(button.onPressed, isNotNull);
    expect(find.text('Pay'), findsOneWidget);

    await tester.tap(find.byKey(const Key('record-collection-entry-7x7')));
    await tester.pumpAndSettle();

    expect(find.text('Record Collection'), findsNothing);
    expect(repository.drafts, hasLength(1));
    expect(repository.drafts.single.amount, 35);
  });

  testWidgets('a partial contractual receipt leaves Pay active for the lacking amount', (
    tester,
  ) async {
    final repository = _RecordingRepository();
    const entry = CollectorRouteEntry(
      id: 'entry-partial',
      clientId: 'client-partial',
      loanId: 'loan-partial',
      clientName: 'Partial Client',
      area: 'Cardona',
      loanType: 'Regular',
      dailyAmount: 200,
      balance: 4700,
      status: 'Recorded today',
      passCount: 0,
      routeRevision: 'loan:loan-partial:v2',
      contractAllocationEnabled: true,
      contractScheduleVerified: true,
      contractDpdStatus: 'ready',
      contractBalanceReconciled: true,
      contractScheduleReady: true,
      contractCollectionReady: true,
      contractTodayScheduledAmount: 200,
      contractTodayUnpaidAmount: 100,
      processedToday: true,
      todayEntryType: 'payment',
      todayAmount: 100,
      todayCollectorName: 'Other Collector',
      todayTransactionId: 'tx-partial',
    );

    await tester.pumpWidget(
      MaterialApp(
        home: CollectorRoutePage(
          session: _session,
          loader: _RouteLoader(isFromCache: false, entry: entry),
          paymentRepository: repository,
          deviceIdentityProvider: _deviceIdentityProvider(),
          deviceSequence: MemoryCollectionDeviceSequence(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Lacking'), findsOneWidget);
    final button = tester.widget<FilledButton>(
      find.byKey(const Key('record-collection-entry-partial')),
    );
    expect(button.onPressed, isNotNull);
    expect(find.text('Pay'), findsOneWidget);

    await tester.tap(find.byKey(const Key('record-collection-entry-partial')));
    await tester.pumpAndSettle();

    expect(repository.drafts, hasLength(1));
    expect(repository.drafts.single.amount, 100);
  });

  testWidgets('a fully satisfied contractual day disables another normal Pay', (
    tester,
  ) async {
    const entry = CollectorRouteEntry(
      id: 'entry-paid',
      clientId: 'client-paid',
      loanId: 'loan-paid',
      clientName: 'Paid Client',
      area: 'Cardona',
      loanType: 'Regular',
      dailyAmount: 200,
      balance: 4600,
      status: 'Recorded today',
      passCount: 0,
      routeRevision: 'loan:loan-paid:v2',
      contractAllocationEnabled: true,
      contractScheduleVerified: true,
      contractDpdStatus: 'ready',
      contractBalanceReconciled: true,
      contractScheduleReady: true,
      contractCollectionReady: true,
      contractTodayScheduledAmount: 200,
      contractTodayUnpaidAmount: 0,
      processedToday: true,
      todayEntryType: 'payment',
      todayAmount: 200,
      todayTransactionId: 'tx-paid',
    );

    await tester.pumpWidget(
      MaterialApp(
        home: CollectorRoutePage(
          session: _session,
          loader: _RouteLoader(isFromCache: false, entry: entry),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Paid'), findsOneWidget);
    final button = tester.widget<FilledButton>(
      find.byKey(const Key('record-collection-entry-paid')),
    );
    expect(button.onPressed, isNull);
  });

  testWidgets('route retry reuses the exact payment key and device sequence', (
    tester,
  ) async {
    final repository = _RetryRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: CollectorRoutePage(
          session: _session,
          loader: _RouteLoader(isFromCache: false),
          paymentRepository: repository,
          deviceIdentityProvider: _deviceIdentityProvider(),
          deviceSequence: MemoryCollectionDeviceSequence(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    final pay = find.byKey(const Key('record-collection-entry-1'));
    await tester.tap(pay);
    await tester.pumpAndSettle();

    expect(repository.drafts, hasLength(1));
    expect(find.text('Retry'), findsOneWidget);
    expect(find.textContaining('not confirmed'), findsOneWidget);

    await tester.tap(pay);
    await tester.pumpAndSettle();

    expect(repository.drafts, hasLength(2));
    expect(
      repository.drafts.first.idempotencyKey,
      repository.drafts.last.idempotencyKey,
    );
    expect(repository.drafts.first.deviceSequence, 1);
    expect(repository.drafts.last.deviceSequence, 1);
  });
}

const UserSession _session = UserSession(
  userId: 'collector-1',
  username: 'collector.one',
  displayName: 'Test Collector',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'test-token',
  permissions: <String>['route.view', 'collection.create'],
);

const CollectorRouteEntry _regularEntry = CollectorRouteEntry(
  id: 'entry-1',
  clientId: 'client-1',
  loanId: 'loan-1',
  clientName: 'Ana Client',
  area: 'Cardona',
  loanType: 'Regular',
  dailyAmount: 200,
  balance: 4800,
  status: 'Pending',
  passCount: 0,
  routeRevision: 'revision-1',
  collectionMessage:
      'Ready for mobile collection. Contract schedule: signed-contract verification is still required.',
  contractReadinessMessage:
      'Contract schedule: signed-contract verification is still required.',
);

CollectorRouteEntry _sevenBySevenEntry({required bool enabled}) {
  return CollectorRouteEntry(
    id: 'entry-7x7',
    clientId: 'client-7x7',
    loanId: 'loan-7x7',
    clientName: 'Seven Client',
    area: 'Cardona',
    loanType: '7x7',
    dailyAmount: 35,
    balance: 5000,
    status: 'Pending',
    passCount: 0,
    routeRevision: 'loan:loan-7x7:v0',
    canCollectMobile: enabled,
    canEnterPayment: enabled,
    sevenBySevenMobileEnabled: enabled,
    collectionMessage: enabled
        ? 'Ready for protected 7x7 mobile collection.'
        : 'Use SPINA desktop for this 7x7 loan.',
  );
}

DeviceIdentityProvider _deviceIdentityProvider() {
  return DeviceIdentityProvider(
    store: MemoryDeviceIdentityStore(),
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
    randomByteGenerator: (length) => List<int>.filled(length, 7),
  );
}

class _RouteLoader implements CollectorRouteLoader {
  _RouteLoader({required this.isFromCache, this.entry = _regularEntry});

  final bool isFromCache;
  final CollectorRouteEntry entry;

  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async {
    return CollectorRouteLoadResult(
      route: CollectorRoute(
        routeDate: DateTime(2026, 8, 1),
        collectorName: 'Test Collector',
        areas: const <String>['Cardona'],
        expectedTotal: entry.dailyAmount,
        entries: <CollectorRouteEntry>[entry],
      ),
      syncedAt: DateTime.utc(2026, 8, 1, 3),
      isFromCache: isFromCache,
    );
  }
}

class _RecordingRepository implements PaymentSubmissionRepository {
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
      receiptNumber: 'R-2001',
      officialBalance: 4600,
    );
  }
}

class _RetryRepository implements PaymentSubmissionRepository {
  final List<PaymentSubmissionDraft> drafts = <PaymentSubmissionDraft>[];

  @override
  Future<PaymentSubmissionResult> submit(
    UserSession session,
    PaymentSubmissionDraft draft,
  ) async {
    drafts.add(draft);
    if (drafts.length == 1) {
      throw const SpinaApiException(
        'The collection could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }
    return PaymentSubmissionResult(
      disposition: PaymentSubmissionDisposition.duplicate,
      idempotencyKey: draft.idempotencyKey,
      message: 'Already recorded.',
      receiptNumber: 'R-2001',
      officialBalance: 4600,
    );
  }
}