import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/combined_payment_submission.dart';
import 'package:gilbic_mobile/src/core/payments/combined_payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_page.dart';

void main() {
  testWidgets(
    'exact Regular + 7x7 Pay previews and saves atomically with one user tap',
    (tester) async {
      final repository = _RecordingCombinedRepository();
      await tester.binding.setSurfaceSize(const Size(430, 1100));
      addTearDown(() async => tester.binding.setSurfaceSize(null));

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

      expect(repository.previews, hasLength(1));
      expect(repository.previews.single.cashReceivedAmount, 150);
      expect(repository.submissions, hasLength(1));
      expect(
        repository.submissions.single.reviewedAllocationHash,
        _allocationHash,
      );
      expect(find.byKey(const Key('combined-payment-total')), findsNothing);
      expect(find.textContaining('saved • Receipts'), findsOneWidget);
    },
  );
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

DeviceIdentityProvider _deviceIdentityProvider() {
  return DeviceIdentityProvider(
    store: MemoryDeviceIdentityStore(),
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
    randomByteGenerator: (length) => List<int>.filled(length, 7),
  );
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

const CombinedPaymentAllocationPreview _exactPreview =
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

class _RecordingCombinedRepository
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
    return _exactPreview;
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
          officialBalance: 2950,
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
