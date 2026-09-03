import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/renewals/client_renewal_workflow_repository.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow.dart';
import 'package:gilbic_mobile/src/core/renewals/renewal_repository.dart';
import 'package:gilbic_mobile/src/core/renewals/renewal_request.dart';
import 'package:gilbic_mobile/src/features/client/client_renewal_page.dart';
import 'package:gilbic_mobile/src/features/client/client_renewal_workflow_page.dart';

void main() {
  testWidgets('client can submit and monitor a renewal request',
      (tester) async {
    final repository = _FakeClientRenewalRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ClientRenewalPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Renewal'), findsOneWidget);
    expect(find.text('TEST CLIENT REGULAR'), findsOneWidget);
    expect(find.text('TEST-REG-001'), findsOneWidget);
    expect(find.text('Regular'), findsWidgets);
    expect(find.text('₱4,900.00'), findsWidgets);

    final requestButton =
        find.byKey(const Key('request-renewal-regular-loan'));
    await tester.scrollUntilVisible(
      requestButton,
      250,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(requestButton);
    await tester.pumpAndSettle();
    expect(find.text('Request loan renewal'), findsOneWidget);

    await tester.enterText(
      find.byKey(const Key('renewal-request-amount')),
      '6000',
    );
    await tester.enterText(
      find.byKey(const Key('renewal-request-message')),
      'Requesting a higher renewal amount',
    );
    await tester.tap(find.byKey(const Key('submit-renewal-request')));
    await tester.pumpAndSettle();

    expect(repository.submittedLoanId, 'regular-loan');
    expect(repository.submittedAmount, 6000);
    expect(
      repository.submittedMessage,
      'Requesting a higher renewal amount',
    );
    expect(repository.deviceId, 'client-device');

    await tester.scrollUntilVisible(
      find.text('Request history'),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('Request history'), findsOneWidget);
    expect(find.text('Pending Collector / Management review'), findsOneWidget);
  });

  testWidgets('approved request continues into renewal workflow',
      (tester) async {
    final repository = _FakeClientRenewalRepository(status: 'approved');
    final workflowRepository = _FakeClientRenewalWorkflowRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ClientRenewalPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
          workflowRepository: workflowRepository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    final continueButton = find.byKey(const Key('open-renewal-workflow'));
    expect(continueButton, findsOneWidget);
    await tester.tap(continueButton);
    await tester.pumpAndSettle();

    expect(find.byType(ClientRenewalWorkflowPage), findsOneWidget);
    expect(find.text('Renewal Progress'), findsOneWidget);
    expect(
      find.text('You do not have an active renewal workflow.'),
      findsOneWidget,
    );
    expect(workflowRepository.listCalls, 1);
    expect(workflowRepository.deviceId, 'client-device');
  });
}

const UserSession _session = UserSession(
  userId: 'client-1',
  username: 'testregular1',
  displayName: 'TEST CLIENT REGULAR',
  role: AppRole.client,
  rawRole: 'Client',
  accessToken: 'client-token',
  permissions: <String>[],
);

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'client-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

class _FakeClientRenewalRepository implements ClientRenewalRepository {
  _FakeClientRenewalRepository({this.status = 'pending'});

  final String status;
  String? deviceId;
  String? submittedLoanId;
  double? submittedAmount;
  String? submittedMessage;

  @override
  Future<ClientRenewalPortal> loadPortal(
    UserSession session, {
    required String deviceId,
  }) async {
    this.deviceId = deviceId;
    return ClientRenewalPortal(
      clientId: 'client-record-1',
      clientCode: 'TEST-REG-001',
      clientName: 'TEST CLIENT REGULAR',
      notice:
          'Submitting a renewal request does not create or release a new loan.',
      loans: <RenewalLoanOption>[
        RenewalLoanOption(
          loanId: 'regular-loan',
          loanNumber: 'TEST-REG-20260802',
          loanTypeName: 'Regular',
          calculationMode: 'fixed_daily',
          principal: 5000,
          contractualTotal: 6000,
          remainingBalance: 4900,
          paidAmount: 100,
          paidPercent: 1.7,
          dailyAmount: 50,
          dateReleased: DateTime(2026, 8, 1),
          dueDate: DateTime(2026, 11, 29),
          status: 'active',
          eligible: true,
          eligibilityMessage:
              'Management will review this request before office processing.',
          pendingRequestId: status == 'approved' ? 'request-1' : null,
          blockingRequestStatus: status == 'approved' ? 'approved' : null,
        ),
      ],
      requests: <RenewalRequestItem>[
        _request(status: status),
      ],
    );
  }

  @override
  Future<RenewalRequestItem> submit(
    UserSession session, {
    required String deviceId,
    required String loanId,
    required double requestedAmount,
    required String message,
  }) async {
    this.deviceId = deviceId;
    submittedLoanId = loanId;
    submittedAmount = requestedAmount;
    submittedMessage = message;
    return _request(status: 'pending');
  }

  @override
  Future<RenewalRequestItem> cancel(
    UserSession session, {
    required String deviceId,
    required String requestId,
  }) async {
    return _request(status: 'cancelled');
  }
}

class _FakeClientRenewalWorkflowRepository
    implements ClientRenewalWorkflowRepository {
  int listCalls = 0;
  String? deviceId;

  @override
  Future<List<CollectorRenewalRequest>> list(
    UserSession session, {
    required String deviceId,
  }) async {
    listCalls += 1;
    this.deviceId = deviceId;
    return const <CollectorRenewalRequest>[];
  }

  @override
  Future<CollectorRenewalRequest> decide(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required String decision,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<CollectorRenewalRequest> sign(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required String signerId,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<CollectorRenewalRequest> confirmCashReceived(
    UserSession session, {
    required String deviceId,
    required String requestId,
  }) {
    throw UnimplementedError();
  }
}

RenewalRequestItem _request({required String status}) {
  return RenewalRequestItem(
    requestId: 'request-1',
    clientId: 'client-record-1',
    clientCode: 'TEST-REG-001',
    clientName: 'TEST CLIENT REGULAR',
    loanId: 'old-loan',
    loanNumber: 'TEST-REG-OLD',
    loanTypeName: 'Regular',
    currentPrincipal: 5000,
    remainingBalance: 1000,
    requestedAmount: 5000,
    clientMessage: 'Please review my renewal.',
    status: status,
    submittedAt: DateTime.utc(2026, 8, 6, 12, 45),
    reviewNote: '',
  );
}
