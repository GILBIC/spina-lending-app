import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/employee_operations/attendance_outbox.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_operations_repository.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_operations_service.dart';
import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart';
import 'package:gilbic_mobile/src/features/employee/employee_dashboard.dart';
import 'package:gilbic_mobile/src/features/employee/employee_operations_page.dart';
import 'package:gilbic_mobile/src/features/employee/employee_command_form.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const user = '00000000-0000-4000-8000-000000000001';
const device = '00000000-0000-4000-8000-000000000002';
const recordId = '00000000-0000-4000-8000-000000000003';
const employeeSession = UserSession(
  userId: user,
  username: 'worker',
  displayName: 'Worker One',
  role: AppRole.employee,
  rawRole: 'Employee',
  accessToken: 'test-token',
  permissions: ['employee.portal.view'],
);
DeviceIdentityProvider identity() => DeviceIdentityProvider(
  store: MemoryDeviceIdentityStore()..value = 'installation',
  platformResolver: () => 'android',
  appVersionResolver: () async => 'test',
);
Map<String, dynamic> workspace({bool owner = false}) => {
  'contract_version': 1,
  'actor': {
    'user_id': user,
    'employee_id': user,
    'device_id': device,
    'is_owner': owner,
  },
  'capabilities': {
    'can_self_service': true,
    'can_configure': owner,
    'can_prepare_payroll': owner,
  },
  'setup_missing': [],
  'account_candidates': owner
      ? [
          {
            'user_id': user,
            'full_name': 'Worker One',
            'username': 'worker',
            'roles': ['Collector'],
          },
        ]
      : [],
  for (final key in employeeCollections) key: <dynamic>[],
};

void main() {
  testWidgets(
    'owner without an employee identity can select actual staff during private setup',
    (tester) async {
      final provider = identity();
      final data = workspace(owner: true);
      (data['capabilities'] as Map)['can_self_service'] = false;
      final repository = EmployeeOperationsRepository(
        StaffOperationsClient(
          deviceIdentityProvider: provider,
          client: MockClient((_) async => http.Response(jsonEncode(data), 200)),
        ),
      );
      final service = EmployeeOperationsService(
        deviceIdentityProvider: provider,
        repository: repository,
        outbox: AttendanceOutbox(MemoryAttendanceVault()),
      );
      addTearDown(service.dispose);
      await tester.pumpWidget(
        MaterialApp(
          home: EmployeeOperationsPage(
            session: employeeSession,
            deviceIdentityProvider: provider,
            service: service,
            initialSection: EmployeeSection.setup,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('employee-create-profile_save')),
        findsOneWidget,
      );
      expect(service.accessDenied, isFalse);
      await tester.tap(find.byKey(const Key('employee-create-profile_save')));
      await tester.pumpAndSettle();
      final selector = find.byKey(const Key('employee-field-employee_id'));
      await tester.scrollUntilVisible(
        selector,
        250,
        scrollable: find.byType(Scrollable).last,
      );
      await tester.tap(selector);
      await tester.pumpAndSettle();
      expect(find.text('Worker One'), findsOneWidget);
      await tester.tap(find.text('Worker One'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      service.attach(null);
      await tester.pumpWidget(const SizedBox());
    },
  );
  testWidgets(
    'Employee dashboard opens attendance and captures a protected server-confirmed clock event',
    (tester) async {
      final commands = <Map<String, dynamic>>[];
      final provider = identity();
      final repository = EmployeeOperationsRepository(
        StaffOperationsClient(
          deviceIdentityProvider: provider,
          client: MockClient((request) async {
            expect(request.headers['x-device-id'], 'installation');
            if (request.method == 'GET') {
              return http.Response(jsonEncode(workspace()), 200);
            }
            final command = jsonDecode(request.body) as Map<String, dynamic>;
            commands.add(command);
            return http.Response(
              jsonEncode({
                'id': command['id'],
                'request_id': command['request_id'],
                'version': 1,
                'status': 'accepted',
              }),
              200,
            );
          }),
        ),
      );
      final service = EmployeeOperationsService(
        deviceIdentityProvider: provider,
        repository: repository,
        outbox: AttendanceOutbox(MemoryAttendanceVault()),
      );
      addTearDown(service.dispose);
      await tester.pumpWidget(
        MaterialApp(
          builder: (context, child) =>
              EmployeeOperationsScope(service: service, child: child!),
          home: EmployeeDashboard(
            session: employeeSession,
            onSignOut: () async {},
            deviceIdentityProvider: provider,
          ),
        ),
      );
      await tester.tap(find.byKey(const Key('employee-attendance')));
      await tester.pumpAndSettle();
      expect(find.text('Employee operations'), findsOneWidget);
      await tester.tap(find.byKey(const Key('employee-clock_in')));
      await tester.pumpAndSettle();
      expect(commands.single['employee_id'], user);
      expect(commands.single['device_id'], device);
      expect(commands.single['event_type'], 'clock_in');
      expect(commands.single['previous_event_id'], isNull);
      expect(commands.single['sequence'], 1);
      expect(
        (await service.outbox.entries(service.binding!)).single.state,
        'accepted',
      );
      expect(tester.takeException(), isNull);
      service.attach(null);
      await tester.pumpWidget(const SizedBox());
    },
  );
  testWidgets(
    'uncertain mutation freezes form and retries the identical request before returning',
    (tester) async {
      final commands = <String>[];
      final provider = identity();
      final repository = EmployeeOperationsRepository(
        StaffOperationsClient(
          deviceIdentityProvider: provider,
          client: MockClient((request) async {
            commands.add(request.body);
            final command = jsonDecode(request.body) as Map;
            return http.Response(
              commands.length == 1
                  ? '{}'
                  : jsonEncode({
                      'id': command['id'],
                      'request_id': command['request_id'],
                      'version': 2,
                      'status': 'accepted',
                    }),
              200,
            );
          }),
        ),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => Scaffold(
              body: TextButton(
                onPressed: () => Navigator.push<void>(
                  context,
                  MaterialPageRoute(
                    builder: (_) => EmployeeCommandForm(
                      session: employeeSession,
                      workspace: EmployeeWorkspace.parse(
                        workspace(),
                        employeeSession,
                      ),
                      repository: repository,
                      action: 'shortage_respond',
                      record: {
                        'id': recordId,
                        'employee_id': user,
                        'version': 1,
                        'payload': {},
                      },
                    ),
                  ),
                ),
                child: const Text('Open response'),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Open response'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('employee-field-explanation')),
        'My counted cash and witness record.',
      );
      await tester.tap(find.byKey(const Key('employee-submit')));
      await tester.pumpAndSettle();
      expect(find.text('Check server confirmation'), findsOneWidget);
      expect(
        tester
            .widget<TextFormField>(
              find.byKey(const Key('employee-field-explanation')),
            )
            .enabled,
        isFalse,
      );
      await tester.tap(find.text('Retry unchanged request'));
      await tester.pumpAndSettle();
      expect(commands.length, 2);
      expect(commands.first, commands.last);
      expect(find.text('Open response'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets('refresh denial clears private payroll at mobile width', (
    tester,
  ) async {
    var denied = false;
    final provider = identity();
    final data = workspace(owner: true);
    data['payroll'] = [
      {
        'id': recordId,
        'employee_id': user,
        'version': 1,
        'status': 'paid',
        'allowed_actions': [],
        'payload': {
          'week_start': '2026-09-13',
          'net_pay': '987.65',
          'components': [],
        },
      },
    ];
    final repository = EmployeeOperationsRepository(
      StaffOperationsClient(
        deviceIdentityProvider: provider,
        client: MockClient(
          (request) async => http.Response(
            denied ? '{}' : jsonEncode(data),
            denied ? 403 : 200,
          ),
        ),
      ),
    );
    final service = EmployeeOperationsService(
      deviceIdentityProvider: provider,
      repository: repository,
      outbox: AttendanceOutbox(MemoryAttendanceVault()),
    );
    addTearDown(service.dispose);
    await tester.binding.setSurfaceSize(const Size(360, 640));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        home: MediaQuery(
          data: const MediaQueryData(textScaler: TextScaler.linear(1.3)),
          child: EmployeeOperationsPage(
            session: employeeSession,
            deviceIdentityProvider: provider,
            service: service,
            initialSection: EmployeeSection.payroll,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('987.65'), findsWidgets);
    denied = true;
    await tester.tap(find.byKey(const Key('employee-refresh')));
    await tester.pumpAndSettle();
    expect(find.textContaining('987.65'), findsNothing);
    expect(service.binding, isNull);
    expect(tester.takeException(), isNull);
    service.attach(null);
    await tester.pumpWidget(const SizedBox());
  });
}
