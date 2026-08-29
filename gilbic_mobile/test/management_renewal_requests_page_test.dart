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
      await tester.binding.setSurfaceSize(const Size(360, 640));
      addTearDown(() async => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(
        MaterialApp(
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(
              context,
            ).copyWith(textScaler: const TextScaler.linear(1.3)),
            child: child!,
          ),
          home: ManagementRenewalRequestsPage(
            session: _session,
            deviceIdentityProvider: _deviceIdentityProvider(),
            repository: repository,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Renewal Requests'), findsOneWidget);

      final termsButton = find.byKey(
        const Key('review-renewal-terms-request-1'),
      );
      await tester.dragUntilVisible(
        termsButton,
        find.byType(ListView),
        const Offset(0, -220),
      );
      await tester.pumpAndSettle();
      expect(find.text('TEST CLIENT REGULAR'), findsOneWidget);
      expect(find.text('Recommend'), findsOneWidget);
      expect(find.text('₱6,000.00'), findsWidgets);
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

      expect(
        find.byKey(const Key('management-review-renewal-workflow')),
        findsOneWidget,
      );
      expect(
        find.text(
          'The approved terms will be saved for the renewal workflow only. '
          'This does not release cash or activate a new loan.',
        ),
        findsOneWidget,
      );
      expect(repository.submittedDraft, isNull);

      await tester.tap(find.byKey(const Key('confirm-renewal-workflow')));
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
      expect(
        repository.submittedDraft?.signers.first.userId,
        'borrower-user-1',
      );
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

      final termsButton = find.byKey(
        const Key('review-renewal-terms-request-1'),
      );
      await tester.dragUntilVisible(
        termsButton,
        find.byType(ListView),
        const Offset(0, -220),
      );
      await tester.pumpAndSettle();
      await tester.tap(termsButton);
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('renewal-override-reason')), findsOneWidget);
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
        find.byKey(const Key('management-review-renewal-workflow')),
        findsOneWidget,
      );
      expect(repository.submittedDraft, isNull);
      await tester.tap(find.byKey(const Key('confirm-renewal-workflow')));
      await tester.pumpAndSettle();

      expect(
        repository.submittedDraft?.overrideReason,
        'Management approved after documented capacity review',
      );
    },
  );

  testWidgets('renewal rejection review can cancel and sends exact reason', (
    tester,
  ) async {
    final repository = _FakeManagementRenewalWorkflowRepository();
    await _pumpWorkflow(tester, repository);
    final action = find.byKey(const Key('reject-renewal-request-1'));
    await _showAction(tester, action);

    await tester.tap(action);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('renewal-rejection-note')),
      'Current capacity is not sufficient',
    );
    await tester.tap(find.byKey(const Key('confirm-renewal-rejection')));
    await tester.pumpAndSettle();
    expect(find.text('Pending Management decision'), findsOneWidget);
    await tester.tap(find.byKey(const Key('cancel-renewal-workflow')));
    await tester.pumpAndSettle();
    expect(repository.submitTermsCalls, 0);

    await tester.tap(action);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('renewal-rejection-note')),
      'Current capacity is not sufficient',
    );
    await tester.tap(find.byKey(const Key('confirm-renewal-rejection')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('confirm-renewal-workflow')));
    await tester.pumpAndSettle();

    expect(repository.submitTermsCalls, 1);
    expect(repository.submittedRequestId, 'request-1');
    expect(repository.submittedDraft?.decision, 'rejected');
    expect(
      repository.submittedDraft?.reviewNote,
      'Current capacity is not sufficient',
    );
  });

  testWidgets('cash-release review can cancel and sends exact request', (
    tester,
  ) async {
    final repository = _FakeManagementRenewalWorkflowRepository(
      workflowState: 'release',
    );
    await _pumpWorkflow(tester, repository);
    final action = find.byKey(const Key('release-renewal-request-1'));
    await _showAction(tester, action);

    await tester.tap(action);
    await tester.pumpAndSettle();
    expect(
      find.text('Cash has not been released to the Collector'),
      findsOneWidget,
    );
    expect(find.text('Client decision'), findsWidgets);
    expect(find.text('Accepted by Client'), findsOneWidget);
    await tester.tap(find.byKey(const Key('cancel-renewal-workflow')));
    await tester.pumpAndSettle();
    expect(repository.releaseCalls, 0);

    await tester.tap(action);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('confirm-renewal-workflow')));
    await tester.pumpAndSettle();

    expect(repository.releaseCalls, 1);
    expect(repository.releasedRequestId, 'request-1');
  });

  testWidgets('proof review maps its decision and sends exact note', (
    tester,
  ) async {
    final repository = _FakeManagementRenewalWorkflowRepository(
      workflowState: 'proof',
    );
    await _pumpWorkflow(tester, repository);
    final action = find.byKey(const Key('request-photo-request-1'));
    await _showAction(tester, action);

    Future<void> prepareReview() async {
      await tester.tap(action);
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('renewal-proof-review-note')),
        'Photo does not show the complete handover',
      );
      await tester.tap(find.byKey(const Key('confirm-renewal-proof-review')));
      await tester.pumpAndSettle();
    }

    await prepareReview();
    expect(find.text('Require a new handover photo'), findsOneWidget);
    expect(find.text('request_new_photo'), findsNothing);
    expect(
      find.text('Submitted proof awaiting Management review'),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const Key('cancel-renewal-workflow')));
    await tester.pumpAndSettle();
    expect(repository.proofCalls, 0);

    await prepareReview();
    await tester.tap(find.byKey(const Key('confirm-renewal-workflow')));
    await tester.pumpAndSettle();

    expect(repository.proofCalls, 1);
    expect(repository.proofRequestId, 'request-1');
    expect(repository.proofDecision, 'request_new_photo');
    expect(repository.proofNote, 'Photo does not show the complete handover');
  });

  testWidgets('activation review can cancel and sends exact request', (
    tester,
  ) async {
    final repository = _FakeManagementRenewalWorkflowRepository(
      workflowState: 'activation',
    );
    await _pumpWorkflow(tester, repository);
    final action = find.byKey(const Key('activate-renewal-request-1'));
    await _showAction(tester, action);

    await tester.tap(action);
    await tester.pumpAndSettle();
    expect(
      find.text('Released renewal awaiting Management activation'),
      findsOneWidget,
    );
    expect(find.text('Handover proof approved'), findsWidgets);
    expect(find.text('Signing requirements are complete'), findsOneWidget);
    await tester.tap(find.byKey(const Key('cancel-renewal-workflow')));
    await tester.pumpAndSettle();
    expect(repository.activateCalls, 0);

    await tester.tap(action);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('confirm-renewal-workflow')));
    await tester.pumpAndSettle();

    expect(repository.activateCalls, 1);
    expect(repository.activatedRequestId, 'request-1');
  });
}

Future<void> _pumpWorkflow(
  WidgetTester tester,
  _FakeManagementRenewalWorkflowRepository repository,
) async {
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
}

Future<void> _showAction(WidgetTester tester, Finder action) async {
  await tester.dragUntilVisible(
    action,
    find.byType(ListView),
    const Offset(0, -260),
  );
  await tester.pumpAndSettle();
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
  _FakeManagementRenewalWorkflowRepository({
    this.recommendation = 'recommend',
    this.workflowState = 'terms',
  });

  final String recommendation;
  final String workflowState;
  String? deviceId;
  String? submittedRequestId;
  ManagementRenewalTermsDraft? submittedDraft;
  int submitTermsCalls = 0;
  int releaseCalls = 0;
  int proofCalls = 0;
  int activateCalls = 0;
  String? releasedRequestId;
  String? proofRequestId;
  String? proofDecision;
  String? proofNote;
  String? activatedRequestId;

  @override
  Future<List<ManagementRenewalWorkflowItem>> list(
    UserSession session, {
    required String deviceId,
    required String status,
  }) async {
    this.deviceId = deviceId;
    return <ManagementRenewalWorkflowItem>[
      ManagementRenewalWorkflowItem(
        request: _requestForState(status),
        borrowerUserId: 'borrower-user-1',
      ),
    ];
  }

  CollectorRenewalRequest _requestForState(String status) =>
      switch (workflowState) {
        'release' => _request(
          status: 'approved',
          recommendation: recommendation,
          approvedPrincipal: 6000,
          clientDecision: 'accepted',
          officeProcessingRequired: false,
          netReleaseAmount: 3000,
          amountLockedAt: DateTime.utc(2026, 8, 23, 8),
        ),
        'proof' => _request(
          status: 'approved',
          recommendation: recommendation,
          approvedPrincipal: 6000,
          clientDecision: 'accepted',
          officeProcessingRequired: false,
          netReleaseAmount: 3000,
          cashGivenToClientAt: DateTime.utc(2026, 8, 23, 10),
          handoverProofStatus: 'under_review',
        ),
        'activation' => _request(
          status: 'approved',
          recommendation: recommendation,
          approvedPrincipal: 6000,
          clientDecision: 'accepted',
          officeProcessingRequired: false,
          netReleaseAmount: 3000,
          clientCashConfirmedAt: DateTime.utc(2026, 8, 23, 11),
          signerReadinessStatus: 'ready',
          handoverProofStatus: 'approved',
          activationStatus: 'released_pending_management',
          newLoanId: 'new-loan-1',
          readyForActivation: true,
        ),
        _ => _request(status: status, recommendation: recommendation),
      };

  @override
  Future<CollectorRenewalRequest> submitTerms(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required ManagementRenewalTermsDraft draft,
  }) async {
    this.deviceId = deviceId;
    submitTermsCalls += 1;
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
    releaseCalls += 1;
    releasedRequestId = requestId;
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
    proofCalls += 1;
    proofRequestId = requestId;
    proofDecision = decision;
    proofNote = note;
    return _request(status: 'approved', recommendation: recommendation);
  }

  @override
  Future<CollectorRenewalRequest> activate(
    UserSession session, {
    required String deviceId,
    required String requestId,
  }) async {
    this.deviceId = deviceId;
    activateCalls += 1;
    activatedRequestId = requestId;
    return _request(status: 'approved', recommendation: recommendation);
  }
}

CollectorRenewalRequest _request({
  required String status,
  required String recommendation,
  double? approvedPrincipal,
  String reviewNote = '',
  String overrideReason = '',
  String? clientDecision,
  String signerReadinessStatus = 'pending',
  bool? officeProcessingRequired,
  double? netReleaseAmount,
  DateTime? amountLockedAt,
  DateTime? cashGivenToClientAt,
  DateTime? clientCashConfirmedAt,
  String handoverProofStatus = 'pending',
  String activationStatus = 'pending',
  String? newLoanId,
  bool readyForActivation = false,
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
    reviewedAt: approvedPrincipal == null
        ? null
        : DateTime.utc(2026, 8, 22, 11),
    clientDecision: clientDecision,
    clientDecidedAt: null,
    signerReadinessStatus: signerReadinessStatus,
    officeProcessingRequired:
        officeProcessingRequired ?? approvedPrincipal != null,
    signers: const <CollectorRenewalSigner>[],
    renewalOffsetAmount: null,
    netReleaseAmount: netReleaseAmount,
    amountLockedAt: amountLockedAt,
    cashReleasedToCollectorAt: null,
    collectorCashReceivedAt: null,
    cashGivenToClientAt: cashGivenToClientAt,
    clientCashConfirmedAt: clientCashConfirmedAt,
    handoverProofStatus: handoverProofStatus,
    activationStatus: activationStatus,
    newLoanId: newLoanId,
    readyForActivation: readyForActivation,
  );
}
