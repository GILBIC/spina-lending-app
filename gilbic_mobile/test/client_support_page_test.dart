import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/support/support_repository.dart';
import 'package:gilbic_mobile/src/core/support/support_request.dart';
import 'package:gilbic_mobile/src/features/client/client_support_page.dart';

void main() {
  testWidgets('client can submit and monitor a support request', (tester) async {
    final repository = _FakeClientSupportRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ClientSupportPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Support'), findsOneWidget);
    expect(find.text('TEST CLIENT REGULAR'), findsOneWidget);
    expect(find.text('No support request has been submitted yet.'), findsOneWidget);

    await tester.tap(find.byKey(const Key('create-support-request')));
    await tester.pumpAndSettle();
    expect(find.text('Ask for assistance'), findsWidgets);

    await tester.enterText(
      find.byKey(const Key('support-subject')),
      'Question about payment',
    );
    await tester.enterText(
      find.byKey(const Key('support-message')),
      'Please check my latest receipt.',
    );
    await tester.enterText(
      find.byKey(const Key('support-reference')),
      'GBC-20260806-00000010',
    );
    await tester.tap(find.byKey(const Key('submit-support-request')));
    await tester.pumpAndSettle();

    expect(repository.submittedCategory, 'payment');
    expect(repository.submittedSubject, 'Question about payment');
    expect(repository.submittedMessage, 'Please check my latest receipt.');
    expect(repository.submittedReference, 'GBC-20260806-00000010');
    expect(repository.deviceId, 'client-device');

    expect(find.text('Question about payment'), findsOneWidget);
    expect(find.text('Open'), findsOneWidget);
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

class _FakeClientSupportRepository implements ClientSupportRepository {
  String? deviceId;
  String? submittedCategory;
  String? submittedSubject;
  String? submittedMessage;
  String? submittedReference;
  final List<SupportRequestItem> requests = <SupportRequestItem>[];

  @override
  Future<ClientSupportPortal> loadPortal(
    UserSession session, {
    required String deviceId,
  }) async {
    this.deviceId = deviceId;
    return ClientSupportPortal(
      clientId: 'client-record-1',
      clientCode: 'TEST-REG-001',
      clientName: 'TEST CLIENT REGULAR',
      requests: List<SupportRequestItem>.unmodifiable(requests),
      notice: 'SPINA staff will review the concern and reply here.',
    );
  }

  @override
  Future<SupportRequestItem> submit(
    UserSession session, {
    required String deviceId,
    required String category,
    required String subject,
    required String message,
    required String referenceText,
  }) async {
    this.deviceId = deviceId;
    submittedCategory = category;
    submittedSubject = subject;
    submittedMessage = message;
    submittedReference = referenceText;
    final request = _request(status: 'open');
    requests.insert(0, request);
    return request;
  }

  @override
  Future<SupportRequestItem> cancel(
    UserSession session, {
    required String deviceId,
    required String requestId,
  }) async {
    return _request(status: 'cancelled');
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
    managementResponse: '',
  );
}
