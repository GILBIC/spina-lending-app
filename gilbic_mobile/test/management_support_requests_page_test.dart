import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
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

  testWidgets('Management exposes only supported support decisions', (
    tester,
  ) async {
    final repository = _FakeManagementSupportRepository();
    await _pumpPage(tester, repository);

    expect(find.byKey(const Key('cancel-support-support-1')), findsNothing);
    expect(find.byKey(const Key('answer-support-support-1')), findsOneWidget);
    expect(find.byKey(const Key('resolve-support-support-1')), findsOneWidget);
    expect(repository.reviewedAction, isNull);
  });

  testWidgets('failed refresh disables stale support decisions until reload', (
    tester,
  ) async {
    final repository = _FakeManagementSupportRepository();
    await _pumpPage(tester, repository);
    repository.loadError = const SpinaApiException(
      'Support unavailable',
      statusCode: 500,
    );
    await tester.tap(find.byTooltip('Refresh'));
    await tester.pumpAndSettle();
    expect(find.text('Support unavailable'), findsOneWidget);
    expect(
      tester
          .widget<OutlinedButton>(
            find.byKey(const Key('answer-support-support-1')),
          )
          .onPressed,
      isNull,
    );
    repository.loadError = null;
    await tester.tap(find.byTooltip('Refresh'));
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<OutlinedButton>(
            find.byKey(const Key('answer-support-support-1')),
          )
          .onPressed,
      isNotNull,
    );
  });

  for (final status in [401, 403, 426]) {
    testWidgets('terminal support denial $status clears private requests', (
      tester,
    ) async {
      final repository = _FakeManagementSupportRepository();
      await _pumpPage(tester, repository);
      repository.loadError = SpinaApiException(
        'Access unavailable',
        statusCode: status,
      );
      await tester.tap(find.byTooltip('Refresh'));
      await tester.pumpAndSettle();
      expect(find.text('TEST CLIENT REGULAR'), findsNothing);
      expect(find.text('Please check my latest receipt.'), findsNothing);
      expect(
        tester
            .widget<IconButton>(find.widgetWithIcon(IconButton, Icons.refresh))
            .onPressed,
        isNull,
      );
      expect(find.text('Try again'), findsNothing);
    });
  }

  testWidgets(
    'support refreshes are serialized and stale controls stay disabled',
    (tester) async {
      final repository = _FakeManagementSupportRepository();
      await _pumpPage(tester, repository);
      final pending = Completer<List<SupportRequestItem>>();
      repository.nextLoad = pending.future;
      final refresh = tester
          .widget<RefreshIndicator>(find.byType(RefreshIndicator))
          .onRefresh;
      final first = refresh();
      await tester.pump();
      final second = refresh();
      await tester.pump();
      expect(repository.loads, 2);
      expect(
        tester
            .widget<OutlinedButton>(
              find.byKey(const Key('answer-support-support-1')),
            )
            .onPressed,
        isNull,
      );
      pending.complete([_request(status: 'open')]);
      await first;
      await second;
      await tester.pumpAndSettle();
    },
  );

  testWidgets('uncertain support write requires refresh before fresh intent', (
    tester,
  ) async {
    final repository = _FakeManagementSupportRepository();
    await _pumpPage(tester, repository);
    repository.reviewError = StateError('lost response');
    await _submitResponse(
      tester,
      buttonKey: const Key('answer-support-support-1'),
      response: 'Response for the client.',
    );
    await tester.tap(find.byKey(const Key('confirm-client-support')));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(repository.reviews, 1);
    expect(
      tester
          .widget<OutlinedButton>(
            find.byKey(const Key('answer-support-support-1')),
          )
          .onPressed,
      isNull,
    );
    repository.reviewError = null;
    await tester.tap(find.byTooltip('Refresh'));
    await tester.pumpAndSettle();
    expect(repository.reviews, 1);
    expect(
      tester
          .widget<OutlinedButton>(
            find.byKey(const Key('answer-support-support-1')),
          )
          .onPressed,
      isNotNull,
    );
    await _submitResponse(
      tester,
      buttonKey: const Key('answer-support-support-1'),
      response: 'Response for the client.',
    );
    expect(repository.reviews, 1);
    await tester.tap(find.byKey(const Key('confirm-client-support')));
    await tester.pumpAndSettle();
    expect(repository.reviews, 2);
  });

  testWidgets('denied support write clears the selected private request', (
    tester,
  ) async {
    final repository = _FakeManagementSupportRepository();
    await _pumpPage(tester, repository);
    repository.reviewError = const SpinaApiException(
      'Device revoked',
      statusCode: 403,
    );
    await _submitResponse(
      tester,
      buttonKey: const Key('answer-support-support-1'),
      response: 'Response for the client.',
    );
    await tester.tap(find.byKey(const Key('confirm-client-support')));
    await tester.pumpAndSettle();
    expect(find.text('TEST CLIENT REGULAR'), findsNothing);
    expect(find.text('Device revoked'), findsOneWidget);
    expect(
      tester
          .widget<IconButton>(find.widgetWithIcon(IconButton, Icons.refresh))
          .onPressed,
      isNull,
    );
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
  Object? loadError;
  Object? reviewError;
  Future<List<SupportRequestItem>>? nextLoad;
  int loads = 0;
  int reviews = 0;
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
    loads++;
    if (loadError != null) throw loadError!;
    if (nextLoad != null) return nextLoad!;
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
    reviews++;
    if (reviewError != null) throw reviewError!;
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
