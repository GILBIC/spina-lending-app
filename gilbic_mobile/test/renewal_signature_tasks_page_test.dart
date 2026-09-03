import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/renewals/renewal_signature_tasks_repository.dart';
import 'package:gilbic_mobile/src/features/renewals/renewal_signature_tasks_page.dart';

void main() {
  testWidgets('assigned signer can sign only from their own ready task',
      (tester) async {
    final repository = _FakeRenewalSignatureTasksRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: RenewalSignatureTasksPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('My Renewal Signatures'), findsOneWidget);
    expect(find.text('Guarantor'), findsOneWidget);
    expect(find.text('TEST BORROWER'), findsOneWidget);
    expect(find.text('TEST-LOAN-001'), findsOneWidget);
    expect(find.text('Ready'), findsOneWidget);

    await tester.tap(find.byKey(const Key('sign-renewal-signer-1')));
    await tester.pumpAndSettle();

    expect(find.text('Sign renewal?'), findsOneWidget);
    expect(
      find.textContaining('Do not sign for another person.'),
      findsOneWidget,
    );

    await tester.tap(find.byKey(const Key('confirm-renewal-signature')));
    await tester.pumpAndSettle();

    expect(repository.signedRequestId, 'request-1');
    expect(repository.signedSignerId, 'signer-1');
    expect(repository.deviceId, 'signature-device');
    expect(find.text('Signed'), findsWidgets);
  });

  testWidgets('office-processing task keeps remote signature disabled',
      (tester) async {
    final repository = _FakeRenewalSignatureTasksRepository(
      officeProcessingRequired: true,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: RenewalSignatureTasksPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Office'), findsOneWidget);
    expect(
      find.textContaining('Office Processing Required'),
      findsOneWidget,
    );
    final button = tester.widget<FilledButton>(
      find.byKey(const Key('sign-renewal-signer-1')),
    );
    expect(button.onPressed, isNull);
  });
}

const UserSession _session = UserSession(
  userId: 'guarantor-user-1',
  username: 'guarantor1',
  displayName: 'TEST GUARANTOR',
  role: AppRole.client,
  rawRole: 'Client',
  accessToken: 'signature-token',
  permissions: <String>['loan.self.view'],
);

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'signature-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

class _FakeRenewalSignatureTasksRepository
    implements RenewalSignatureTasksRepository {
  _FakeRenewalSignatureTasksRepository({this.officeProcessingRequired = false});

  final bool officeProcessingRequired;
  bool signed = false;
  String? signedRequestId;
  String? signedSignerId;
  String? deviceId;

  RenewalSignatureTask get task => RenewalSignatureTask(
        signerId: 'signer-1',
        requestId: 'request-1',
        partyRole: 'guarantor',
        fullName: 'TEST GUARANTOR',
        governmentIdVerified: true,
        selfieVerified: true,
        signed: signed,
        clientDecision: 'accepted',
        status: 'approved',
        borrowerName: 'TEST BORROWER',
        loanNumber: 'TEST-LOAN-001',
        officeProcessingRequired: officeProcessingRequired,
      );

  @override
  Future<List<RenewalSignatureTask>> list(
    UserSession session, {
    required String deviceId,
  }) async {
    this.deviceId = deviceId;
    return <RenewalSignatureTask>[task];
  }

  @override
  Future<void> sign(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required String signerId,
  }) async {
    this.deviceId = deviceId;
    signedRequestId = requestId;
    signedSignerId = signerId;
    signed = true;
  }
}
