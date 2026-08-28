import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/combined_payment_submission.dart';
import 'package:gilbic_mobile/src/core/payments/combined_payment_submission_repository.dart';
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
    expect(
      find.textContaining('Offline route copies are read-only'),
      findsNothing,
    );

    await tester.tap(find.byKey(const Key('route-client-client-1')));
    await tester.pumpAndSettle();

    expect(
      find.textContaining('Offline route copies are read-only'),
      findsOneWidget,
    );
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
    expect(find.byKey(const Key('collection-details-entry-1')), findsOneWidget);
  });

  testWidgets('7x7 stays desktop-only when server gate is false', (
    tester,
  ) async {
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

  testWidgets(
    'a partial contractual receipt leaves Pay active for the lacking amount',
    (tester) async {
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

      expect(find.text('LACKING'), findsOneWidget);
      final button = tester.widget<FilledButton>(
        find.byKey(const Key('record-collection-entry-partial')),
      );
      expect(button.onPressed, isNotNull);
      expect(find.text('Pay'), findsOneWidget);

      await tester.tap(
        find.byKey(const Key('record-collection-entry-partial')),
      );
      await tester.pumpAndSettle();

      expect(repository.drafts, hasLength(1));
      expect(repository.drafts.single.amount, 100);
    },
  );

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

  testWidgets(
    'combined Pay previews one total on the server before atomic save',
    (tester) async {
      final repository = _CombinedRecordingRepository();
      await tester.binding.setSurfaceSize(const Size(430, 1100));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        MaterialApp(
          home: CollectorRoutePage(
            session: _session,
            loader: _CombinedRouteLoader(),
            combinedPaymentRepository: repository,
            deviceIdentityProvider: _deviceIdentityProvider(),
            deviceSequence: MemoryCollectionDeviceSequence(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('record-client-client-combined')));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 500));
      await tester.pump();

      expect(find.byKey(const Key('combined-payment-total')), findsOneWidget);
      expect(find.text('Server allocation preview'), findsOneWidget);
      expect(find.text('7x7 scheduled'), findsOneWidget);
      expect(find.text('Regular scheduled'), findsOneWidget);
      expect(find.text('₱50.00'), findsOneWidget);
      expect(find.text('₱100.00'), findsOneWidget);
      expect(repository.previews, hasLength(1));
      expect(repository.previews.single.cashReceivedAmount, 150);
      expect(
        repository.previews.single.legs.any(
          (leg) => leg.toJson().containsKey('amount'),
        ),
        isFalse,
      );

      await tester.tap(find.byKey(const Key('combined-confirm-payment')));
      await tester.pumpAndSettle();

      expect(repository.submissions, hasLength(1));
      expect(
        repository.submissions.single.reviewedAllocationHash,
        _allocationHash,
      );
    },
  );

  testWidgets(
    'combined Pay ignores a preview that completed after the cash total changed',
    (tester) async {
      final repository = _DelayedCombinedRepository();
      await tester.binding.setSurfaceSize(const Size(430, 1100));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        MaterialApp(
          home: CollectorRoutePage(
            session: _session,
            loader: _CombinedRouteLoader(),
            combinedPaymentRepository: repository,
            deviceIdentityProvider: _deviceIdentityProvider(),
            deviceSequence: MemoryCollectionDeviceSequence(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('record-client-client-combined')));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 500));
      expect(repository.requests, hasLength(1));

      await tester.enterText(
        find.byKey(const Key('combined-payment-total')),
        '140',
      );
      repository.completers.first.complete(_exactCombinedPreview);
      await tester.pump();
      expect(find.text('Server allocation preview'), findsNothing);

      await tester.tap(find.byKey(const Key('combined-preview-allocation')));
      await tester.pump();
      expect(repository.requests, hasLength(2));
      expect(repository.requests.last.cashReceivedAmount, 140);
      repository.completers.last.complete(_shortCombinedPreview);
      await tester.pump();

      expect(find.text('Short preview for the updated total.'), findsOneWidget);
      expect(find.text('Exact Regular + 7x7 amount.'), findsNothing);
    },
  );

  testWidgets(
    'combined Pay surfaces a server cash custody review instead of generic success',
    (tester) async {
      final repository = _CombinedCustodyReviewRepository();
      await tester.binding.setSurfaceSize(const Size(430, 1100));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        MaterialApp(
          home: CollectorRoutePage(
            session: _session,
            loader: _CombinedRouteLoader(),
            combinedPaymentRepository: repository,
            deviceIdentityProvider: _deviceIdentityProvider(),
            deviceSequence: MemoryCollectionDeviceSequence(),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('record-client-client-combined')));
      await _pumpCombinedSheet(tester);
      await tester.tap(find.byKey(const Key('combined-confirm-payment')));
      await _pumpCombinedSheet(tester);

      expect(
        find.textContaining('CASH CUSTODY REVIEW REQUIRED'),
        findsOneWidget,
      );
      expect(find.textContaining('10.00 remains unallocated'), findsOneWidget);
      expect(find.textContaining('saved • Receipts'), findsNothing);
    },
  );

  testWidgets(
    'combined Pay recovers from a rejected extra choice and shows 7x7 advance dates',
    (tester) async {
      final repository = _RecoverableExtraChoiceRepository();
      await tester.binding.setSurfaceSize(const Size(430, 1100));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        MaterialApp(
          home: CollectorRoutePage(
            session: _session,
            loader: _CombinedRouteLoader(),
            combinedPaymentRepository: repository,
            deviceIdentityProvider: _deviceIdentityProvider(),
            deviceSequence: MemoryCollectionDeviceSequence(),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('record-client-client-combined')));
      await _pumpCombinedSheet(tester);

      await tester.enterText(
        find.byKey(const Key('combined-payment-total')),
        '170',
      );
      await tester.tap(find.byKey(const Key('combined-preview-allocation')));
      await _pumpCombinedSheet(tester);
      expect(find.byKey(const Key('combined-extra-choice')), findsOneWidget);

      await tester.tap(find.byKey(const Key('combined-extra-choice')));
      await tester.pump(const Duration(milliseconds: 500));
      await tester.tap(find.text('Regular Principal Reduction').last);
      await _pumpCombinedSheet(tester);
      expect(find.textContaining('not available'), findsOneWidget);
      expect(find.byKey(const Key('combined-extra-choice')), findsNothing);

      await tester.tap(find.byKey(const Key('combined-preview-allocation')));
      await _pumpCombinedSheet(tester);
      expect(find.byKey(const Key('combined-extra-choice')), findsOneWidget);
      await tester.tap(find.byKey(const Key('combined-extra-choice')));
      await tester.pump(const Duration(milliseconds: 500));
      await tester.tap(find.text('7x7 Advance').last);
      await _pumpCombinedSheet(tester);

      expect(
        find.byKey(const Key('combined-seven-advance-dates')),
        findsOneWidget,
      );
      expect(find.textContaining('2026-08-02, 2026-08-03'), findsOneWidget);
    },
  );

  testWidgets(
    'combined Pay stays gated when the backend preview capability is unavailable',
    (tester) async {
      final repository = _UnavailableCombinedRepository();
      await tester.binding.setSurfaceSize(const Size(430, 1100));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        MaterialApp(
          home: CollectorRoutePage(
            session: _session,
            loader: _CombinedRouteLoader(),
            combinedPaymentRepository: repository,
            deviceIdentityProvider: _deviceIdentityProvider(),
            deviceSequence: MemoryCollectionDeviceSequence(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('record-client-client-combined')));
      await _pumpCombinedSheet(tester);

      expect(repository.previewCount, 1);
      expect(find.textContaining('backend update is required'), findsOneWidget);
      final confirm = tester.widget<FilledButton>(
        find.byKey(const Key('combined-confirm-payment')),
      );
      expect(confirm.onPressed, isNull);
      expect(repository.submitCount, 0);
    },
  );
}

Future<void> _pumpCombinedSheet(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 500));
  await tester.pump();
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

class _CombinedRouteLoader implements CollectorRouteLoader {
  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async {
    return CollectorRouteLoadResult(
      route: CollectorRoute(
        routeDate: DateTime(2026, 8, 1),
        collectorName: 'Test Collector',
        areas: const <String>['Cardona'],
        expectedTotal: 150,
        entries: const <CollectorRouteEntry>[
          CollectorRouteEntry(
            id: 'regular-combined',
            clientId: 'client-combined',
            loanId: 'loan-regular',
            clientName: 'Combined Client',
            area: 'Cardona',
            loanType: 'Regular',
            dailyAmount: 100,
            balance: 4800,
            status: 'Pending',
            passCount: 0,
            routeRevision: 'loan:loan-regular:v0',
          ),
          CollectorRouteEntry(
            id: 'seven-combined',
            clientId: 'client-combined',
            loanId: 'loan-seven',
            clientName: 'Combined Client',
            area: 'Cardona',
            loanType: '7x7',
            dailyAmount: 50,
            balance: 3000,
            status: 'Pending',
            passCount: 0,
            routeRevision: 'loan:loan-seven:v0',
            sevenBySevenMobileEnabled: true,
          ),
        ],
      ),
      syncedAt: DateTime.utc(2026, 8, 1, 3),
      isFromCache: false,
    );
  }
}

const String _allocationHash =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';

const CombinedPaymentAllocationPreview _exactCombinedPreview =
    CombinedPaymentAllocationPreview(
      status: 'exact',
      requiresReview: false,
      allocationHash: _allocationHash,
      cashReceivedAmount: 150,
      expectedTotalAmount: 150,
      shortAmount: 0,
      extraAmount: 0,
      extraChoiceRequired: false,
      regularPastDueFollowupRequired: false,
      message: 'Exact Regular + 7x7 amount.',
      legs: <CombinedPaymentAllocationLeg>[
        CombinedPaymentAllocationLeg(
          loanId: 'loan-seven',
          loanType: 'seven_by_seven',
          scheduledAmount: 50,
          extraAmount: 0,
          totalAmount: 50,
        ),
        CombinedPaymentAllocationLeg(
          loanId: 'loan-regular',
          loanType: 'regular',
          scheduledAmount: 100,
          extraAmount: 0,
          totalAmount: 100,
        ),
      ],
    );

const CombinedPaymentAllocationPreview _shortCombinedPreview =
    CombinedPaymentAllocationPreview(
      status: 'short',
      requiresReview: true,
      allocationHash:
          'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
      cashReceivedAmount: 140,
      expectedTotalAmount: 150,
      shortAmount: 10,
      extraAmount: 0,
      extraChoiceRequired: false,
      regularPastDueFollowupRequired: true,
      message: 'Short preview for the updated total.',
      legs: <CombinedPaymentAllocationLeg>[
        CombinedPaymentAllocationLeg(
          loanId: 'loan-seven',
          loanType: 'seven_by_seven',
          scheduledAmount: 50,
          extraAmount: 0,
          totalAmount: 50,
        ),
        CombinedPaymentAllocationLeg(
          loanId: 'loan-regular',
          loanType: 'regular',
          scheduledAmount: 90,
          extraAmount: 0,
          totalAmount: 90,
        ),
      ],
    );

const CombinedPaymentAllocationPreview _extraChoicePreview =
    CombinedPaymentAllocationPreview(
      status: 'extra_choice_required',
      requiresReview: true,
      allocationHash:
          'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
      cashReceivedAmount: 170,
      expectedTotalAmount: 150,
      shortAmount: 0,
      extraAmount: 20,
      extraChoiceRequired: true,
      regularPastDueFollowupRequired: false,
      message: 'Choose how the true extra should be allocated.',
      legs: <CombinedPaymentAllocationLeg>[
        CombinedPaymentAllocationLeg(
          loanId: 'loan-seven',
          loanType: 'seven_by_seven',
          scheduledAmount: 50,
          extraAmount: 0,
          totalAmount: 50,
        ),
        CombinedPaymentAllocationLeg(
          loanId: 'loan-regular',
          loanType: 'regular',
          scheduledAmount: 100,
          extraAmount: 0,
          totalAmount: 100,
        ),
      ],
    );

const CombinedPaymentAllocationPreview _sevenAdvancePreview =
    CombinedPaymentAllocationPreview(
      status: 'allocated',
      requiresReview: true,
      allocationHash:
          'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd',
      cashReceivedAmount: 170,
      expectedTotalAmount: 150,
      shortAmount: 0,
      extraAmount: 20,
      extraChoiceRequired: false,
      regularPastDueFollowupRequired: false,
      message: '7x7 advance allocation ready for review.',
      legs: <CombinedPaymentAllocationLeg>[
        CombinedPaymentAllocationLeg(
          loanId: 'loan-seven',
          loanType: 'seven_by_seven',
          scheduledAmount: 50,
          extraAmount: 20,
          totalAmount: 70,
          projectedCoveredDates: <String>['2026-08-02', '2026-08-03'],
        ),
        CombinedPaymentAllocationLeg(
          loanId: 'loan-regular',
          loanType: 'regular',
          scheduledAmount: 100,
          extraAmount: 0,
          totalAmount: 100,
        ),
      ],
    );

class _DelayedCombinedRepository
    implements CombinedPaymentSubmissionRepository {
  final List<CombinedPaymentSubmissionDraft> requests =
      <CombinedPaymentSubmissionDraft>[];
  final List<Completer<CombinedPaymentAllocationPreview>> completers =
      <Completer<CombinedPaymentAllocationPreview>>[];

  @override
  Future<CombinedPaymentAllocationPreview> preview(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  ) {
    requests.add(draft);
    final completer = Completer<CombinedPaymentAllocationPreview>();
    completers.add(completer);
    return completer.future;
  }

  @override
  Future<CombinedPaymentSubmissionResult> submit(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  ) {
    throw UnimplementedError('The stale-preview test never submits.');
  }
}

class _CombinedRecordingRepository
    implements CombinedPaymentSubmissionRepository {
  final List<CombinedPaymentSubmissionDraft> previews =
      <CombinedPaymentSubmissionDraft>[];
  final List<CombinedPaymentSubmissionDraft> submissions =
      <CombinedPaymentSubmissionDraft>[];

  @override
  Future<CombinedPaymentAllocationPreview> preview(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  ) async {
    previews.add(draft);
    return _exactCombinedPreview;
  }

  @override
  Future<CombinedPaymentSubmissionResult> submit(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  ) async {
    submissions.add(draft);
    return const CombinedPaymentSubmissionResult(
      status: 'accepted',
      duplicate: false,
      idempotencyKey: 'combined-test',
      clientId: 'client-combined',
      totalAmount: 150,
      appliedTotalAmount: 150,
      unallocatedTotalAmount: 0,
      cashAllocationState: 'fully_allocated',
      legs: <CombinedPaymentLegResult>[
        CombinedPaymentLegResult(
          loanId: 'loan-seven',
          transactionId: 'tx-seven',
          receiptNumber: 'R-7',
          officialBalance: 3000,
          appliedAmount: 50,
          unallocatedAmount: 0,
          allocationState: 'fully_allocated',
          protectedResult: <String, dynamic>{},
        ),
        CombinedPaymentLegResult(
          loanId: 'loan-regular',
          transactionId: 'tx-regular',
          receiptNumber: 'R-R',
          officialBalance: 4700,
          appliedAmount: 100,
          unallocatedAmount: 0,
          allocationState: 'fully_allocated',
          protectedResult: <String, dynamic>{},
        ),
      ],
      message: 'Saved atomically.',
    );
  }
}

class _UnavailableCombinedRepository
    implements CombinedPaymentSubmissionRepository {
  int previewCount = 0;
  int submitCount = 0;

  @override
  Future<CombinedPaymentAllocationPreview> preview(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  ) async {
    previewCount += 1;
    throw const SpinaApiException(
      'Combined Pay is unavailable because a backend update is required.',
      statusCode: 404,
      code: 'combined_preview_unavailable',
    );
  }

  @override
  Future<CombinedPaymentSubmissionResult> submit(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  ) {
    submitCount += 1;
    throw StateError('Submit must stay disabled without a server preview.');
  }
}

class _CombinedCustodyReviewRepository
    implements CombinedPaymentSubmissionRepository {
  @override
  Future<CombinedPaymentAllocationPreview> preview(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  ) async => _exactCombinedPreview;

  @override
  Future<CombinedPaymentSubmissionResult> submit(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  ) async {
    return const CombinedPaymentSubmissionResult(
      status: 'accepted',
      duplicate: false,
      idempotencyKey: 'combined-custody-test',
      clientId: 'client-combined',
      totalAmount: 150,
      appliedTotalAmount: 140,
      unallocatedTotalAmount: 10,
      cashAllocationState: 'needs_review',
      legs: <CombinedPaymentLegResult>[
        CombinedPaymentLegResult(
          loanId: 'loan-regular',
          transactionId: 'tx-regular',
          receiptNumber: 'R-REVIEW',
          officialBalance: 0,
          appliedAmount: 140,
          unallocatedAmount: 10,
          allocationState: 'partially_allocated',
          protectedResult: <String, dynamic>{},
        ),
      ],
      message: '10.00 remains unallocated and needs custody review.',
    );
  }
}

class _RecoverableExtraChoiceRepository
    implements CombinedPaymentSubmissionRepository {
  @override
  Future<CombinedPaymentAllocationPreview> preview(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  ) async {
    if (draft.cashReceivedAmount != 170) {
      return _exactCombinedPreview;
    }
    switch (draft.extraAllocationChoice) {
      case null:
        return _extraChoicePreview;
      case CombinedExtraAllocationChoice.regularPrincipalReduction:
        throw const SpinaApiException(
          'Regular Principal Reduction is not available for this schedule.',
          statusCode: 422,
          code: 'combined_extra_choice_unavailable',
        );
      case CombinedExtraAllocationChoice.sevenBySevenAdvance:
        return _sevenAdvancePreview;
      case CombinedExtraAllocationChoice.sevenBySevenExtraPrincipal:
      case CombinedExtraAllocationChoice.regularAdvance:
        throw const SpinaApiException(
          'That extra choice is not available for this test.',
          statusCode: 422,
          code: 'combined_extra_choice_unavailable',
        );
    }
  }

  @override
  Future<CombinedPaymentSubmissionResult> submit(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  ) {
    throw UnimplementedError('The recoverable-choice test never submits.');
  }
}
