import 'dart:async';
import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/employee_operations/attendance_outbox.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_operations_repository.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_operations_service.dart';
import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const session = UserSession(
  userId: 'worker-a',
  username: 'a',
  displayName: 'A',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'worker-a-token',
);
void main() {
  test(
    'fresh sign-in revalidates HR authority and automatically resumes a previously revoked pending capture',
    () async {
      final vault = MemoryAttendanceVault();
      final outbox = AttendanceOutbox(vault);
      const binding = AttendanceBinding(
        userId: 'worker-a',
        installationId: 'installation',
        deviceId: 'device-a',
      );
      await outbox.authorize(binding);
      await vault.update(
        'actor|worker-a|installation',
        (_) => {'device_id': 'device-a'},
      );
      final original = await outbox.capture(binding, 'clock_in', offline: true);
      await outbox.sync(
        binding,
        (_) async => throw const SpinaApiException('expired', statusCode: 401),
      );
      final confirmed = Completer<Map<String, dynamic>>();
      var revalidated = false;
      final provider = DeviceIdentityProvider(
        store: MemoryDeviceIdentityStore()..value = 'installation',
        platformResolver: () => 'android',
        appVersionResolver: () async => 'test',
      );
      final repo = EmployeeOperationsRepository(
        StaffOperationsClient(
          deviceIdentityProvider: provider,
          client: MockClient((request) async {
            if (request.method == 'GET') {
              revalidated = true;
              return http.Response(
                jsonEncode({
                  'contract_version': 1,
                  'actor': {'user_id': 'worker-a', 'device_id': 'device-a'},
                  'capabilities': {'can_self_service': true},
                  'setup_missing': [],
                  for (final key in employeeCollections) key: [],
                }),
                200,
              );
            }
            expect(revalidated, isTrue);
            final body = jsonDecode(request.body) as Map<String, dynamic>;
            confirmed.complete(body);
            return http.Response(
              jsonEncode({
                'id': body['id'],
                'request_id': body['request_id'],
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
        repository: repo,
        outbox: AttendanceOutbox(vault),
      );
      addTearDown(service.dispose);
      service.attach(session);
      expect(
        await confirmed.future.timeout(const Duration(seconds: 1)),
        original.command,
      );
    },
  );
  test(
    'restart attaches same account and resumes automatic attendance upload; another account never sends it',
    () async {
      final vault = MemoryAttendanceVault();
      final provider = DeviceIdentityProvider(
        store: MemoryDeviceIdentityStore()..value = 'installation',
        platformResolver: () => 'android',
        appVersionResolver: () async => 'test',
      );
      final sent = Completer<Map<String, dynamic>>();
      final repo = EmployeeOperationsRepository(
        StaffOperationsClient(
          deviceIdentityProvider: provider,
          client: MockClient((request) async {
            expect(request.headers['authorization'], 'Bearer worker-a-token');
            final command = jsonDecode(request.body) as Map<String, dynamic>;
            sent.complete(command);
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
      final initial = EmployeeOperationsService(
        deviceIdentityProvider: provider,
        repository: repo,
        outbox: AttendanceOutbox(vault),
      );
      initial.foreground(false);
      initial.attach(session);
      final workspace = EmployeeWorkspace.parse({
        'contract_version': 1,
        'actor': {'user_id': 'worker-a', 'device_id': 'device-a'},
        'capabilities': {'can_self_service': true},
        'setup_missing': [],
        for (final key in employeeCollections) key: [],
      }, session);
      await initial.acceptWorkspace(session, workspace);
      final capture = await initial.outbox.capture(
        initial.binding!,
        'clock_in',
        offline: true,
      );
      initial.dispose();
      final resumed = EmployeeOperationsService(
        deviceIdentityProvider: provider,
        repository: repo,
        outbox: AttendanceOutbox(vault),
      );
      addTearDown(resumed.dispose);
      const other = UserSession(
        userId: 'worker-b',
        username: 'b',
        displayName: 'B',
        role: AppRole.collector,
        rawRole: 'Collector',
        accessToken: 'worker-b-token',
      );
      resumed.attach(other);
      await Future<void>.delayed(Duration.zero);
      expect(sent.isCompleted, isFalse);
      resumed.attach(session);
      final command = await sent.future.timeout(const Duration(seconds: 2));
      expect(command, capture.command);
      resumed.foreground(false);
      await resumed.sync();
      expect(sent.isCompleted, isTrue);
    },
  );
}
