import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/support/support_repository.dart';
import 'package:gilbic_mobile/src/core/support/support_request.dart';
import 'package:gilbic_mobile/src/features/management/management_support_requests_page.dart';

void main() {
  testWidgets('Management can answer an open support request', (tester) async {
    final repository = _FakeManagementSupportRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementSupportRequestsPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Client Support'), findsOneWidget);
    expect(find.text('TEST CLIENT REGULAR'), findsOneWidget);
    expect(find.text('Question about payment'), findsOneWidget);

    await _submitResponse(
      tester,
      buttonKey: const Key('answer-support-support-1'),
      response: 'Your payment is recorded correctly.',
    );

    expect(
      find.byKey(const Key('management-review-client-support')),
      findsOneWidget,
    );
    expect(
      find.text(
        'The response will be saved to the client communication history. '
        'Official financial records will not be edited.',
      ),
      findsOneWidget,
    );
    expect(repository.reviewedAction, isNull);

    await tester.tap(find.byKey(const Key('cancel-client-support')));
    await tester.pumpAndSettle();
    expect(repository.reviewedAction, isNull);

    await _submitResponse(
      tester,
      buttonKey: const Key('answer-support-support-1'),
      response: 'Your payment is recorded correctly.',
    );
    await tester.tap(find.byKey(const Key('confirm-client-support')));
    await tester.pumpAndSettle();

    expect(repository.reviewedAction, 'answered');
    expect(repository.reviewedResponse, 'Your payment is recorded correctly.');
    expect(repository.deviceId, 'management-device');
  });

  testWidgets('Management reviews a resolution before closing support', (
    tester,
  ) async {
    final repository = _FakeManagementSupportRepository();
    await _pumpPage(tester, repository);

    await _submitResponse(
      tester,
      buttonKey: const Key('resolve-support-support-1'),
      response: 'Receipt verified and concern resolved.',
    );

    expect(
      find.text(
        'The request will be closed as resolved with this response in '
        'communication history. Official financial records will not be edited.',
      ),
      findsOneWidget,
    );
    expect(repository.reviewedAction, isNull);
    await tester.tap(find.byKey(const Key('confirm-client-support')));
    await tester.pumpAndSettle();

    expect(repository.reviewedAction, 'resolved');
    expect(
      repository.reviewedResponse,
      'Receipt verified and concern resolved.',
    );
  });

  testWidgets('Management reviews a cancellation before closing support', (
    tester,
  ) async {
    final repository = _FakeManagementSupportRepository();
    await _pumpPage(tester, repository);

    await _submitResponse(
      tester,
      buttonKey: const Key('cancel-support-support-1'),
      response: 'Duplicate support request confirmed.',
    );

    expect(
      find.text(
        'The request will be closed as cancelled. Official financial records '
        'will not be edited.',
      ),
      findsOneWidget,
    );
    expect(repository.reviewedAction, isNull);
    await tester.tap(find.byKey(const Key('confirm-client-support')));
    await tester.pumpAndSettle();

    expect(repository.reviewedAction, 'cancelled');
    expect(repository.reviewedResponse, 'Duplicate support request confirmed.');
  });
}

Future<void> _pumpPage(
  WidgetTester tester,
  _FakeManagementSupportRepository repository,
) async {
  await tester.pumpWidget(
    MaterialApp(
      home: ManagementSupportRequestsPage(
        session: _session,
        deviceIdentityProvider: _deviceIdentityProvider(),
        repository: repository,
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> _submitResponse(
  WidgetTester tester, {
  required Key buttonKey,
  required String response,
}) async {
  await tester.tap(find.byKey(buttonKey));
  await tester.pumpAndSettle();
  await tester.enterText(
    find.byKey(const Key('management-support-response')),
    response,
  );
  await tester.tap(find.byKey(const Key('submit-management-support-response')));
  await tester.pumpAndSettle();
}

const UserSession _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>['support.manage'],
);

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'management-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

class _FakeManagementSupportRepository implements ManagementSupportRepository {
  String? deviceId;
  String? reviewedAction;
  String? reviewedResponse;
  bool answered = false;

  @override
  Future<List<SupportRequestItem>> loadRequests(
    UserSession session, {
    required String deviceId,
    required String status,
  }) async {
    this.deviceId = deviceId;
    if (status == 'open' && !answered) {
      return <SupportRequestItem>[_request(status: 'open')];
    }
    return const <SupportRequestItem>[];
  }

  @override
  Future<SupportRequestItem> review(
    UserSession session, {
    required String deviceId,
    required String requestId,
    required String action,
    required String response,
  }) async {
    this.deviceId = deviceId;
    reviewedAction = action;
    reviewedResponse = response;
    answered = true;
    return _request(status: action);
  }
}

SupportRequestItem _request({required String status}) {
  return SupportRequestItem(
    requestId: 'support-1',
    clientId: 'client-record-1',
    clientCode: 'TEST-REG-001',
    clientName: 'TEST CLIENT REGULAR',
    category: 'payment',
    subject: 'Question about payment',
    message: 'Please check my latest receipt.',
    referenceText: 'GBC-20260806-00000010',
    status: status,
    createdAt: DateTime.utc(2026, 8, 7, 2, 30),
    managedByName: status == 'open' ? null : 'Management',
    managementResponse: status == 'open'
        ? ''
        : 'Your payment is recorded correctly.',
    respondedAt: status == 'open' ? null : DateTime.utc(2026, 8, 7, 2, 40),
  );
}
