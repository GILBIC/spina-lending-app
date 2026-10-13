import 'dart:async';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/support/support_repository.dart';
import 'package:gilbic_mobile/src/core/support/support_request.dart';
import 'package:gilbic_mobile/src/features/client/client_support_page.dart';

void main() {
  testWidgets('support denial invalidates newer reads already in flight', (
    tester,
  ) async {
    final repository = _ControlledSupportRepository();
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
    final old = Completer<ClientSupportPortal>(),
        newer = Completer<ClientSupportPortal>();
    repository.pending = old;
    final first = tester
        .widget<RefreshIndicator>(find.byType(RefreshIndicator))
        .onRefresh();
    await tester.pump();
    repository.pending = newer;
    final second = tester
        .widget<RefreshIndicator>(find.byType(RefreshIndicator))
        .onRefresh();
    await tester.pump();
    old.completeError(const SpinaApiException('Denied', statusCode: 403));
    await first;
    await tester.pump();
    expect(find.text('TEST CLIENT REGULAR'), findsNothing);
    newer.complete(
      await _FakeClientSupportRepository().loadPortal(
        _session,
        deviceId: 'client-device',
      ),
    );
    await second;
    await tester.pumpAndSettle();
    expect(find.text('TEST CLIENT REGULAR'), findsNothing);
  });

  for (final status in [401, 403, 426, 503]) {
    testWidgets('support refresh $status handles retained private model', (
      tester,
    ) async {
      final repository = _ControlledSupportRepository();
      final provider = _deviceIdentityProvider();
      await tester.pumpWidget(
        MaterialApp(
          home: ClientSupportPage(
            session: _session,
            deviceIdentityProvider: provider,
            repository: repository,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('TEST CLIENT REGULAR'), findsOneWidget);
      repository.failure = SpinaApiException(
        'Synthetic failure',
        statusCode: status,
      );
      await tester.tap(find.byTooltip('Refresh'));
      await tester.pumpAndSettle();
      expect(
        find.text('TEST CLIENT REGULAR'),
        status == 503 ? findsOneWidget : findsNothing,
      );
    });
  }
  testWidgets('support context switch drops private data and fences old read', (
    tester,
  ) async {
    final repository = _ControlledSupportRepository();
    final provider = _deviceIdentityProvider();
    Widget page(UserSession session) => MaterialApp(
      home: ClientSupportPage(
        session: session,
        deviceIdentityProvider: provider,
        repository: repository,
      ),
    );
    await tester.pumpWidget(page(_session));
    await tester.pumpAndSettle();
    repository.pending = Completer<ClientSupportPortal>();
    await tester.tap(find.byTooltip('Refresh'));
    await tester.pump();
    final old = repository.pending!;
    repository.pending = Completer<ClientSupportPortal>();
    await tester.pumpWidget(
      page(
        const UserSession(
          userId: 'other-client',
          username: 'other',
          displayName: 'Other',
          role: AppRole.client,
          rawRole: 'client',
          accessToken: 'other-token',
        ),
      ),
    );
    await tester.pump();
    expect(find.text('TEST CLIENT REGULAR'), findsNothing);
    old.complete(
      await _FakeClientSupportRepository().loadPortal(
        _session,
        deviceId: 'client-device',
      ),
    );
    await tester.pump();
    expect(find.text('TEST CLIENT REGULAR'), findsNothing);
    repository.pending!.completeError(
      const SpinaApiException('Denied', statusCode: 403),
    );
    await tester.pumpAndSettle();
  });

  testWidgets('client can submit and monitor a support request', (
    tester,
  ) async {
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
    expect(
      find.text('No support request has been submitted yet.'),
      findsOneWidget,
    );

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

class _ControlledSupportRepository extends _FakeClientSupportRepository {
  SpinaApiException? failure;
  Completer<ClientSupportPortal>? pending;
  @override
  Future<ClientSupportPortal> loadPortal(
    UserSession session, {
    required String deviceId,
  }) {
    if (failure != null) return Future.error(failure!);
    return pending?.future ?? super.loadPortal(session, deviceId: deviceId);
  }
}
