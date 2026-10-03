import 'support/android_workflow_capture.dart';
import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/employee_operations/attendance_outbox.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_operations_repository.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_operations_service.dart';
import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/employee/employee_operations_page.dart';
import 'package:gilbic_mobile/src/features/offline/mobile_offline_policy_page.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'employee_operations_widget_test.dart'
    show identity, workspace, employeeSession, user, device;
import 'support/android_role_fixture.dart';

void main() {
  for (final state in ['accepted', 'pending_review', 'needs_attention']) {
    testWidgets(
      'attendance $state reflects receipt or review without payroll payment',
      (tester) async {
        final provider = identity();
        final service = EmployeeOperationsService(
          deviceIdentityProvider: provider,
          repository: EmployeeOperationsRepository(
            StaffOperationsClient(
              deviceIdentityProvider: provider,
              client: MockClient((request) async {
                expect(request.method, 'GET');
                throw Exception('offline');
              }),
            ),
          ),
          outbox: AttendanceOutbox(MemoryAttendanceVault()),
        );
        addTearDown(service.dispose);
        service.foreground(false);
        service.attach(employeeSession);
        await service.acceptWorkspace(
          employeeSession,
          EmployeeWorkspace.parse(workspace(), employeeSession),
        );
        final bound = service.binding!;
        final original = await service.outbox.capture(
          bound,
          'clock_in',
          offline: true,
        );
        await service.outbox.sync(bound, (command) async {
          expect(command, original.command);
          if (state == 'needs_attention') {
            throw const SpinaApiException(
              'Review the attendance sequence.',
              statusCode: 409,
            );
          }
          return {
            'id': command['id'],
            'request_id': command['request_id'],
            'version': 1,
            'status': state,
          };
        });
        await pumpAndroidRoleFixture(
          tester,
          size: const Size(320, 640),
          textScaler: TextScaler.linear(2),
          home: EmployeeOperationsPage(
            session: employeeSession,
            deviceIdentityProvider: provider,
            service: service,
          ),
        );
        await tester.pumpAndSettle();
        expect(
          find.textContaining(
            state == 'accepted'
                ? 'Clock in · Received by server'
                : 'Clock in · Needs review',
          ),
          findsOneWidget,
        );
        expect(
          find.textContaining('Saved on this device — awaiting server sync'),
          findsNothing,
        );
        expect(find.text('Paid'), findsNothing);
        final retained = (await service.outbox.entries(bound)).single;
        expect(retained.state, state);
        expect(retained.command, original.command);
        await captureAndroidWorkflowScroll(tester, 'E1-attendance-$state');
        service.attach(null);
        await tester.pumpWidget(const SizedBox());
      },
    );
  }

  test(
    'expired session leaves pending attendance untouched without sending',
    () async {
      final provider = identity();
      var sends = 0;
      final service = EmployeeOperationsService(
        deviceIdentityProvider: provider,
        repository: EmployeeOperationsRepository(
          StaffOperationsClient(
            deviceIdentityProvider: provider,
            client: MockClient((_) async {
              sends++;
              throw StateError('Expired credentials must not be sent.');
            }),
          ),
        ),
        outbox: AttendanceOutbox(MemoryAttendanceVault()),
      );
      addTearDown(service.dispose);
      service.foreground(false);
      service.attach(employeeSession);
      await service.acceptWorkspace(
        employeeSession,
        EmployeeWorkspace.parse(workspace(), employeeSession),
      );
      final bound = service.binding!;
      final original = await service.outbox.capture(
        bound,
        'clock_in',
        offline: true,
      );
      final expired = UserSession(
        userId: user,
        username: 'worker',
        displayName: 'Worker One',
        role: AppRole.employee,
        rawRole: 'Employee',
        accessToken: 'expired-token',
        expiresAt: DateTime.utc(2000),
      );
      service.attach(expired);
      service.foreground(true);
      await service.sync();
      await Future<void>.delayed(Duration.zero);
      expect(sends, 0);
      expect(
        (await service.outbox.entries(bound)).single.command,
        original.command,
      );
      expect((await service.outbox.entries(bound)).single.state, 'pending');
      service.foreground(false);
    },
  );

  testWidgets('configured Management attendance agrees with offline policy', (
    tester,
  ) async {
    const session = UserSession(
      userId: user,
      username: 'configured.manager',
      displayName: 'Configured Manager',
      role: AppRole.management,
      rawRole: 'Management',
      accessToken: 'synthetic-management-token',
      permissions: ['employee.portal.view'],
    );
    final provider = identity();
    var offline = false;
    var writes = 0;
    final service = EmployeeOperationsService(
      deviceIdentityProvider: provider,
      repository: EmployeeOperationsRepository(
        StaffOperationsClient(
          deviceIdentityProvider: provider,
          client: MockClient((request) async {
            expect(
              request.headers['authorization'],
              'Bearer synthetic-management-token',
            );
            if (request.method != 'GET') {
              writes++;
              throw StateError('No server write is permitted in this fixture.');
            }
            if (offline) throw Exception('offline');
            return http.Response(jsonEncode(workspace()), 200);
          }),
        ),
      ),
      outbox: AttendanceOutbox(MemoryAttendanceVault()),
    );
    addTearDown(service.dispose);
    service.foreground(false);
    await pumpAndroidRoleFixture(
      tester,
      size: const Size(412, 915),
      textScaler: TextScaler.linear(1),
      home: EmployeeOperationsPage(
        session: session,
        deviceIdentityProvider: provider,
        service: service,
      ),
    );
    await tester.pumpAndSettle();
    offline = true;
    await tester.tap(find.byKey(const Key('employee-refresh')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('employee-clock_in')));
    await tester.pumpAndSettle();
    final capture = (await service.outbox.entries(service.binding!)).single;
    expect(capture.state, 'pending');
    expect(capture.command['employee_id'], user);
    expect(capture.command['device_id'], device);
    expect(capture.command['offline'], isTrue);
    expect(writes, 0);
    expect(
      find.textContaining('Saved on this device — awaiting server sync'),
      findsOneWidget,
    );
    await pumpAndroidRoleFixture(
      tester,
      size: const Size(412, 915),
      textScaler: TextScaler.linear(1),
      home: const MobileOfflinePolicyPage(session: session),
    );
    await tester.pumpAndSettle();
    expect(
      find.textContaining(
        'When your own active staff profile and protected device setup are configured',
      ),
      findsWidgets,
    );
    await tester.scrollUntilVisible(
      find.byKey(const Key('offline-write-safety')),
      400,
    );
    expect(
      find.text('Encrypted own attendance outbox, when configured'),
      findsOneWidget,
    );
    expect(find.text('None'), findsNothing);
    expect(
      (await service.outbox.entries(service.binding!)).single.command,
      capture.command,
    );
    service.attach(null);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('offline queue prohibition explicitly applies to finance', (
    tester,
  ) async {
    await pumpAndroidRoleFixture(
      tester,
      size: const Size(412, 915),
      textScaler: TextScaler.linear(1),
      home: const MobileOfflinePolicyPage(session: employeeSession),
    );
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.byKey(const Key('offline-write-safety')),
      400,
    );
    expect(find.text('Silent offline financial write queue'), findsOneWidget);
    expect(find.text('Silent offline write queue'), findsNothing);
    expect(find.text('Financial writes while offline'), findsOneWidget);
    expect(find.text('Blocked'), findsOneWidget);
    expect(find.text('Encrypted attendance outbox'), findsOneWidget);
  });

  test(
    'token rotation retries attendance with current credentials and original command',
    () async {
      final provider = identity();
      final failed = Completer<void>();
      final received = Completer<void>();
      final commands = <Map<String, dynamic>>[];
      final tokens = <String?>[];
      final service = EmployeeOperationsService(
        deviceIdentityProvider: provider,
        repository: EmployeeOperationsRepository(
          StaffOperationsClient(
            deviceIdentityProvider: provider,
            client: MockClient((request) async {
              expect(request.method, 'POST');
              final command = jsonDecode(request.body) as Map<String, dynamic>;
              commands.add(command);
              tokens.add(request.headers['authorization']);
              if (commands.length == 1) {
                failed.complete();
                throw Exception('connection lost during submit');
              }
              received.complete();
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
        ),
        outbox: AttendanceOutbox(MemoryAttendanceVault()),
      );
      addTearDown(service.dispose);
      addTearDown(employeeSession.clearRefreshOverride);
      service.foreground(false);
      service.attach(employeeSession);
      await service.acceptWorkspace(
        employeeSession,
        EmployeeWorkspace.parse(workspace(), employeeSession),
      );
      final bound = service.binding!;
      final original = await service.outbox.capture(
        bound,
        'clock_in',
        offline: false,
      );
      service.foreground(true);
      await failed.future.timeout(const Duration(seconds: 2));
      await Future<void>.delayed(Duration.zero);
      expect((await service.outbox.entries(bound)).single.state, 'pending');
      service.foreground(false);
      const rotated = UserSession(
        userId: user,
        username: 'worker',
        displayName: 'Worker One',
        role: AppRole.employee,
        rawRole: 'Employee',
        accessToken: 'current-rotated-token',
        permissions: ['employee.portal.view'],
      );
      employeeSession.applyRefresh(rotated);
      service.attach(rotated);
      service.foreground(true);
      await received.future.timeout(const Duration(seconds: 2));
      await Future<void>.delayed(Duration.zero);
      expect(tokens, ['Bearer test-token', 'Bearer current-rotated-token']);
      expect(commands, [original.command, original.command]);
      expect((await service.outbox.entries(bound)).single.state, 'accepted');
      service.foreground(false);
    },
  );

  test(
    'changed registered device and self-service grant retain old pending capture privately',
    () async {
      final provider = identity();
      final service = EmployeeOperationsService(
        deviceIdentityProvider: provider,
        repository: EmployeeOperationsRepository(
          StaffOperationsClient(
            deviceIdentityProvider: provider,
            client: MockClient(
              (_) async => throw StateError('No network expected.'),
            ),
          ),
        ),
        outbox: AttendanceOutbox(MemoryAttendanceVault()),
      );
      addTearDown(service.dispose);
      service.foreground(false);
      service.attach(employeeSession);
      await service.acceptWorkspace(
        employeeSession,
        EmployeeWorkspace.parse(workspace(), employeeSession),
      );
      final old = service.binding!;
      final original = await service.outbox.capture(
        old,
        'clock_in',
        offline: true,
      );
      final changed = workspace();
      (changed['actor'] as Map)['device_id'] = 'registered-device-b';
      await service.acceptWorkspace(
        employeeSession,
        EmployeeWorkspace.parse(changed, employeeSession),
      );
      final current = service.binding!;
      expect(current.deviceId, 'registered-device-b');
      expect(await service.outbox.entries(current), isEmpty);
      expect(
        (await service.outbox.entries(old)).single.command,
        original.command,
      );
      (changed['capabilities'] as Map)['can_self_service'] = false;
      await service.acceptWorkspace(
        employeeSession,
        EmployeeWorkspace.parse(changed, employeeSession),
      );
      expect(service.binding, isNull);
      expect(await service.outbox.isAuthorized(current), isFalse);
      expect(
        (await service.outbox.entries(old)).single.command,
        original.command,
      );
      expect((await service.outbox.entries(old)).single.state, 'pending');
    },
  );

  testWidgets('device_saved_attendance_is_not_server_accepted', (tester) async {
    final provider = identity();
    final service = EmployeeOperationsService(
      deviceIdentityProvider: provider,
      repository: EmployeeOperationsRepository(
        StaffOperationsClient(
          deviceIdentityProvider: provider,
          client: MockClient((_) async => throw Exception('offline')),
        ),
      ),
      outbox: AttendanceOutbox(MemoryAttendanceVault()),
    );
    service.foreground(false);
    service.attach(employeeSession);
    await service.acceptWorkspace(
      employeeSession,
      EmployeeWorkspace.parse(workspace(), employeeSession),
    );
    final original = await service.outbox.capture(
      service.binding!,
      'clock_in',
      offline: true,
    );
    await pumpAndroidRoleFixture(
      tester,
      size: const Size(320, 640),
      textScaler: TextScaler.linear(2),
      home: EmployeeOperationsPage(
        session: employeeSession,
        deviceIdentityProvider: provider,
        service: service,
      ),
    );
    await tester.pumpAndSettle();
    expect(
      find.textContaining('Saved on this device — awaiting server sync'),
      findsOneWidget,
    );
    expect(find.textContaining('Received by server'), findsNothing);
    expect(
      (await service.outbox.entries(service.binding!)).single.command,
      original.command,
    );
    await captureAndroidWorkflowScroll(tester, 'E1-device-queued');
    service.attach(null);
    await tester.pumpWidget(const SizedBox());
    service.dispose();
  });
}
