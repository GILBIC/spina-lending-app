import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/renewals/renewal_repository.dart';
import 'package:gilbic_mobile/src/core/renewals/renewal_request.dart';
import 'package:gilbic_mobile/src/features/management/management_renewal_requests_page.dart';

void main() {
  testWidgets('Management can approve a pending renewal request',
      (tester) async {
    final repository = _FakeManagementRenewalRepository();

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
    expect(find.text('₱6,000.00'), findsWidgets);
    expect(find.text('Pending review'), findsOneWidget);

    await tester.tap(find.byKey(const Key('approve-renewal-request-1')));
    await tester.pumpAndSettle();
    expect(find.text('Approve renewal request?'), findsOneWidget);

    await tester.enterText(
      find.byKey(const Key('renewal-review-note')),
      'Approved for office processing',
    );
    await tester.tap(find.byKey(const Key('confirm-renewal-review')));
    await tester.pumpAndSettle();

    expect(repository.reviewedRequestId, 'request-1');
    expect(repository.decision, 'approved');
    expect(repository.reviewNote, 'Approved for office processing');
    expect(repository.deviceId, 'management-device');
  });
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

class _FakeManagementRenewalRepository
    implements ManagementRenewalRepository {
  String? deviceId;
  String? reviewedRequestId;
  String? decision;
  String? reviewNote;

  @override
  Future<List<RenewalRequestItem>> loadRequests(
    UserSession session, {
    required String deviceId,
    required String status,
  }) async {
    this.deviceId = deviceId;
    return <RenewalRequestItem>[_request(status: status)];
  }

  @override
  Future<RenewalRequestItem> review(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required String decision,
    required String reviewNote,
  }) async {
    this.deviceId = deviceId;
    reviewedRequestId = requestId;
    this.decision = decision;
    this.reviewNote = reviewNote;
    return _request(status: decision);
  }
}

RenewalRequestItem _request({required String status}) {
  return RenewalRequestItem(
    requestId: 'request-1',
    clientId: 'client-record-1',
    clientCode: 'TEST-REG-001',
    clientName: 'TEST CLIENT REGULAR',
    loanId: 'regular-loan',
    loanNumber: 'TEST-REG-20260802',
    loanTypeName: 'Regular',
    currentPrincipal: 5000,
    remainingBalance: 4900,
    requestedAmount: 6000,
    clientMessage: 'Requesting a higher renewal amount',
    status: status,
    submittedAt: DateTime.utc(2026, 8, 6, 12, 45),
    reviewNote: status == 'approved' ? 'Approved for office processing' : '',
    reviewedAt: status == 'approved'
        ? DateTime.utc(2026, 8, 6, 13)
        : null,
    reviewedByName: status == 'approved' ? 'Management' : null,
  );
}
