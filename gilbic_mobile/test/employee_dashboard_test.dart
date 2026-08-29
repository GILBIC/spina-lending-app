import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification_repository.dart';
import 'package:gilbic_mobile/src/features/employee/employee_dashboard.dart';

void main() {
  testWidgets('Employee dashboard separates personal and office work', (
    tester,
  ) async {
    await _pumpDashboard(tester, _session());

    expect(find.text('Employee Dashboard'), findsOneWidget);
    expect(find.byKey(const Key('employee-section-workday')), findsOneWidget);
    expect(
      find.byKey(const Key('employee-section-pay-requests')),
      findsOneWidget,
    );
    expect(find.text('Attendance'), findsOneWidget);
    expect(find.text('Tasks & work items'), findsOneWidget);
    expect(find.text('Payroll & payslips'), findsOneWidget);
    expect(find.text('Leave & requests'), findsOneWidget);
    expect(find.text('Not available yet'), findsNWidgets(4));

    await _scrollTo(tester, find.byKey(const Key('employee-section-office')));
    expect(find.byKey(const Key('employee-section-office')), findsOneWidget);
    expect(
      find.text(
        'No office functions are assigned by your current server permissions.',
      ),
      findsOneWidget,
    );

    await _scrollTo(tester, find.byKey(const Key('employee-section-updates')));
    expect(find.byKey(const Key('employee-section-updates')), findsOneWidget);
    expect(find.text('Notifications'), findsOneWidget);
    expect(find.text('My account & devices'), findsOneWidget);
    expect(find.text('Connectivity & offline policy'), findsOneWidget);

    expect(find.text('Daily Route'), findsNothing);
    expect(find.text('Record Payment'), findsNothing);
    expect(find.text('Staff & devices'), findsNothing);
    expect(find.text('Management Employee Activity'), findsNothing);
  });

  testWidgets('Office functions use exact independent permissions', (
    tester,
  ) async {
    await _pumpDashboard(
      tester,
      _session(
        permissions: const <String>[
          'employee.portal.view',
          'remittance.view',
          'support.manage',
          'accounting.view',
        ],
      ),
    );

    await _scrollTo(tester, find.byKey(const Key('employee-remittance')));
    expect(find.byKey(const Key('employee-remittance')), findsOneWidget);
    expect(find.byKey(const Key('employee-client-support')), findsOneWidget);
    expect(find.byKey(const Key('employee-accounting')), findsOneWidget);
    expect(find.text('Remittance requests'), findsOneWidget);
    expect(find.text('Client support'), findsOneWidget);
    expect(find.text('Accounting & bookkeeping'), findsOneWidget);
    expect(
      find.descendant(
        of: find.byKey(const Key('employee-remittance')),
        matching: find.text('Available now'),
      ),
      findsOneWidget,
    );
    expect(find.text('Employee workflow not connected yet'), findsNWidgets(2));

    await _pumpDashboard(
      tester,
      _session(permissions: const <String>['employee.portal.view']),
    );
    await _scrollTo(tester, find.byKey(const Key('employee-section-office')));
    expect(find.byKey(const Key('employee-remittance')), findsNothing);
    expect(find.byKey(const Key('employee-client-support')), findsNothing);
    expect(find.byKey(const Key('employee-accounting')), findsNothing);
  });

  testWidgets('Employee opens the existing remittance review flow', (
    tester,
  ) async {
    await _pumpDashboard(
      tester,
      _session(
        permissions: const <String>['employee.portal.view', 'remittance.view'],
      ),
      notificationRepository: _EmptyNotificationRepository(),
    );

    await _scrollTo(tester, find.byKey(const Key('employee-remittance')));
    await tester.tap(find.byKey(const Key('employee-remittance')));
    await tester.pumpAndSettle();

    expect(find.text('Remittance requests'), findsOneWidget);
    expect(find.text('No remittance notifications yet.'), findsOneWidget);
  });

  testWidgets('Employee office tools repeat permission checks at tap time', (
    tester,
  ) async {
    final permissions = <String>['employee.portal.view', 'remittance.view'];
    await _pumpDashboard(
      tester,
      _session(permissions: permissions),
      notificationRepository: _EmptyNotificationRepository(),
    );

    final launcher = find.byKey(const Key('employee-remittance'));
    await _scrollTo(tester, launcher);
    expect(launcher, findsOneWidget);

    permissions.remove('remittance.view');
    await tester.tap(launcher);
    await tester.pumpAndSettle();

    expect(
      find.text(
        'Your current server permissions do not allow Remittance requests.',
      ),
      findsOneWidget,
    );
    expect(find.text('No remittance notifications yet.'), findsNothing);
  });

  testWidgets('Employee dashboard scrolls at 360x640 with 1.3 text scale', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(360, 640));
    addTearDown(() async => tester.binding.setSurfaceSize(null));

    await _pumpDashboard(
      tester,
      _session(
        permissions: const <String>[
          'employee.portal.view',
          'remittance.view',
          'support.manage',
          'accounting.view',
        ],
      ),
      textScaler: const TextScaler.linear(1.3),
    );

    expect(tester.takeException(), isNull);
    await _scrollTo(tester, find.text('Connectivity & offline policy'));
    expect(find.text('Connectivity & offline policy'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}

Future<void> _scrollTo(WidgetTester tester, Finder finder) async {
  await tester.scrollUntilVisible(
    finder,
    260,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pumpAndSettle();
}

Future<void> _pumpDashboard(
  WidgetTester tester,
  UserSession session, {
  RemittanceNotificationRepository? notificationRepository,
  TextScaler textScaler = TextScaler.noScaling,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: MediaQuery(
        data: MediaQueryData(textScaler: textScaler),
        child: EmployeeDashboard(
          session: session,
          onSignOut: () async {},
          deviceIdentityProvider: _deviceIdentityProvider(),
          remittanceNotificationRepository: notificationRepository,
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

UserSession _session({List<String>? permissions}) => UserSession(
  userId: 'employee-one',
  username: 'employee.one',
  displayName: 'Employee One',
  role: AppRole.employee,
  rawRole: 'Employee',
  accessToken: 'employee-token',
  permissions: permissions ?? const <String>['employee.portal.view'],
);

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'employee-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

class _EmptyNotificationRepository implements RemittanceNotificationRepository {
  @override
  Future<List<RemittanceNotification>> loadNotifications(
    UserSession session, {
    required String deviceId,
  }) async => const <RemittanceNotification>[];

  @override
  Future<RemittanceNotification> markRead(
    UserSession session, {
    required String deviceId,
    required String notificationId,
  }) {
    throw StateError('No notification should be marked read.');
  }

  @override
  Future<RemittanceAcceptanceResult> acceptRemittance(
    UserSession session, {
    required String deviceId,
    required String notificationId,
  }) {
    throw StateError(
      'Employee dashboard does not accept remittances directly.',
    );
  }
}
