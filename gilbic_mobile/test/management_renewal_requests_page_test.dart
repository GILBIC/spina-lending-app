import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow.dart';
import 'package:gilbic_mobile/src/core/renewals/management_renewal_workflow.dart';
import 'package:gilbic_mobile/src/core/renewals/management_renewal_workflow_repository.dart';
import 'package:gilbic_mobile/src/features/management/management_renewal_requests_page.dart';

void main() {
  testWidgets(
    'Management records approved principal through workflow and keeps remote identity fail-closed',
    (tester) async {
      final repository = _FakeManagementRenewalWorkflowRepository();

      await tester.pumpWidget(
        MaterialApp(
          home: ManagementRenewalRequestsPage(
            session: _session,
            deviceIdentityProvider: _deviceIdentityProvider(),
            repository: repository,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Renewal Requests'), findsOneWidget);
      expect(find.text('TEST CLIENT REGULAR'), findsOneWidget);
      expect(find.text('Recommend'), findsOneWidget);
      expect(find.text('₱6,000.00'), findsWidgets);

      final termsButton =
          find.byKey(const Key('review-renewal-terms-request-1'));
      await tester.dragUntilVisible(
        termsButton,
        find.byType(ListView),
        const Offset(0, -220),
      );
      await tester.pumpAndSettle();
      await tester.tap(termsButton);
      await tester.pumpAndSettle();

      expect(find.text('Set Management renewal terms'), findsOneWidget);
      expect(
        find.textContaining('Remote signing stays fail-closed'),
        findsOneWidget,
      );

      await tester.enterText(
        find.byKey(const Key('renewal-approved-principal')),
        '7000',
      );
      await tester.enterText(
        find.byKey(const Key('renewal-management-note')),
        'Approved based on current capacity',
      );
      await tester.tap(find.byKey(const Key('confirm-renewal-terms')));
      await tester.pumpAndSettle();

      expect(repository.deviceId, 'management-device');
      expect(repository.submittedRequestId, 'request-1');
      expect(repository.submittedDraft?.decision, 'approved');
      expect(repository.submittedDraft?.approvedPrincipal, 7000);
      expect(
        repository.submittedDraft?.reviewNote,
        'Approved based on current capacity',
      );
      expect(repository.submittedDraft?.officeProcessingRequired, isTrue);
      expect(repository.submittedDraft?.signers, hasLength(1));
      expect(repository.submittedDraft?.signers.first.partyRole, 'borrower');
      expect(repository.submittedDraft?.signers.first.userId, 'borrower-user-1');
      expect(
        repository.submittedDraft?.signers.first.governmentIdVerified,
        isFalse,
      );
      expect(repository.submittedDraft?.signers.first.selfieVerified, isFalse);
    },
  );

  testWidgets(
    'Management override reason is mandatory after Collector Do Not Recommend',
    (tester) async {
      final repository = _FakeManagementRenewalWorkflowRepository(
        recommendation: 'do_not_recommend',
      );

      await tester.pumpWidget(
        MaterialApp(
          home: ManagementRenewalRequestsPage(
            session: _session,
            deviceIdentityProvider: _deviceIdentityProvider(),
            repository: repository,
          ),
        ),
      );
      await tester.pumpAndSettle();

      final termsButton =
          find.byKey(const Key('review-renewal-terms-request-1'));
      await tester.dragUntilVisible(
        termsButton,
        find.byType(ListView),
        const Offset(0, -220),
      );
      await tester.pumpAndSettle();
      await tester.tap(termsButton);
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('renewal-override-reason')),
        findsOneWidget,
      );
      await tester.tap(find.byKey(const Key('confirm-renewal-terms')));
      await tester.pumpAndSettle();
      expect(
        find.text(
          'Management override reason is required after Do Not Recommend.',
        ),
        findsOneWidget,
      );
      expect(repository.submittedDraft, isNull);

      await tester.enterText(
        find.byKey(const Key('renewal-override-reason')),
        'Management approved after documented capacity review',
      );
      await tester.tap(find.byKey(const Key('confirm-renewal-terms')));
      await tester.pumpAndSettle();

      expect(
        repository.submittedDraft?.overrideReason,
        'Management approved after documented capacity review',
      );
    },
  );
}

const UserSession _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>['renewal.manage'],
);

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'management-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

class _FakeManagementRenewalWorkflowRepository
    implements ManagementRenewalWorkflowRepository {
  _FakeManagementRenewalWorkflowRepository({this.recommendation = 'recommend'});

  final String recommendation;
  String? deviceId;
  String? submittedRequestId;
  ManagementRenewalTermsDraft? submittedDraft;

  @override
  Future<List<ManagementRenewalWorkflowItem>> list(
    UserSession session, {
    required String deviceId,
    required String status,
  }) async {
    this.deviceId = deviceId;
    return <ManagementRenewalWorkflowItem>[
      ManagementRenewalWorkflowItem(
        request: _request(
          status: status,
          recommendation: recommendation,
        ),
        borrowerUserId: 'borrower-user-1',
      ),
    ];
  }

  @override
  Future<CollectorRenewalRequest> submitTerms(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required ManagementRenewalTermsDraft draft,
  }) async {
    this.deviceId = deviceId;
    submittedRequestId = requestId;
    submittedDraft = draft;
    return _request(
      status: draft.decision,
      recommendation: recommendation,
      approvedPrincipal: draft.approvedPrincipal,
      reviewNote: draft.reviewNote,
      overrideReason: draft.overrideReason,
    );
  }

  @override
  Future<CollectorRenewalRequest> releaseToCollector(
    UserSession session, {
    required String deviceId,
    required String requestId,
  }) async {
    this.deviceId = deviceId;
    return _request(status: 'approved', recommendation: recommendation);
  }

  @override
  Future<CollectorRenewalRequest> reviewProof(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required String decision,
    required String note,
  }) async {
    this.deviceId = deviceId;
    return _request(status: 'approved', recommendation: recommendation);
  }

  @override
  Future<CollectorRenewalRequest> activate(
    UserSession session, {
    required String deviceId,
    required String requestId,
  }) async {
    this.deviceId = deviceId;
    return _request(status: 'approved', recommendation: recommendation);
  }
}

CollectorRenewalRequest _request({
  required String status,
  required String recommendation,
  double? approvedPrincipal,
  String reviewNote = '',
  String overrideReason = '',
}) {
  return CollectorRenewalRequest(
    requestId: 'request-1',
    clientId: 'client-record-1',
    clientCode: 'TEST-REG-001',
    clientName: 'TEST CLIENT REGULAR',
    area: 'TEST AREA',
    loanId: 'regular-loan',
    loanNumber: 'TEST-REG-20260802',
    loanTypeName: 'Regular',
    isSevenBySeven: false,
    currentPrincipal: 5000,
    remainingBalance: 3000,
    contractualTotal: 10000,
    paidCash: 5000,
    paidPercent: 50,
    regular50PercentEligible: true,
    requestedAmount: 6000,
    clientMessage: 'Requesting a higher renewal amount',
    status: status,
    submittedAt: DateTime.utc(2026, 8, 22, 9),
    collectorRecommendation: recommendation,
    collectorReasonCode: recommendation == 'recommend'
        ? 'good_payment_record'
        : 'capacity_concern',
    collectorComment: recommendation == 'recommend'
        ? 'Route record supports renewal.'
        : 'Current capacity needs Management review.',
    recommendedAt: DateTime.utc(2026, 8, 22, 10),
    approvedPrincipal: approvedPrincipal,
    reviewNote: reviewNote,
    managementOverrideReason: overrideReason,
    reviewedAt: approvedPrincipal == null ? null : DateTime.utc(2026, 8, 22, 11),
    clientDecision: null,
    clientDecidedAt: null,
    signerReadinessStatus: 'pending',
    officeProcessingRequired: approvedPrincipal != null,
    signers: const <CollectorRenewalSigner>[],
    renewalOffsetAmount: null,
    netReleaseAmount: null,
    amountLockedAt: null,
    cashReleasedToCollectorAt: null,
    collectorCashReceivedAt: null,
    cashGivenToClientAt: null,
    clientCashConfirmedAt: null,
    handoverProofStatus: 'pending',
    activationStatus: 'pending',
    newLoanId: null,
    readyForActivation: false,
  );
}
