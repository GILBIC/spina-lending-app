import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_operations_repository.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const session = UserSession(
  userId: 'user-a',
  username: 'a',
  displayName: 'A',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'secret',
);
void main() {
  test('history matches domain as well as UUID', () {
    final data = {
      'contract_version': 1,
      'actor': {'user_id': session.userId},
      'capabilities': {},
      'setup_missing': [],
      for (final collection in employeeCollections) collection: <dynamic>[],
    };
    data['history'] = [
      {'domain': 'profiles', 'record_id': 'same-id', 'version': 1},
      {'domain': 'payroll', 'record_id': 'same-id', 'version': 2},
    ];
    final workspace = EmployeeWorkspace.parse(data, session);
    expect(workspace.historyFor('payroll', 'same-id').single['version'], 2);
  });
  test(
    'mutation keeps exact money and identity; malformed success remains uncertain',
    () async {
      final bodies = <String>[];
      var malformed = true;
      final provider = DeviceIdentityProvider(
        store: MemoryDeviceIdentityStore()..value = 'installation',
        platformResolver: () => 'android',
        appVersionResolver: () async => 'test',
      );
      final repo = EmployeeOperationsRepository(
        StaffOperationsClient(
          deviceIdentityProvider: provider,
          client: MockClient((request) async {
            expect(request.headers['authorization'], 'Bearer secret');
            expect(request.headers['x-device-id'], 'installation');
            bodies.add(request.body);
            final body = jsonDecode(request.body) as Map;
            return http.Response(
              malformed
                  ? '{}'
                  : jsonEncode({
                      'request_id': body['request_id'],
                      'id': body['id'],
                      'version': 1,
                      'status': 'accepted',
                    }),
              200,
            );
          }),
        ),
      );
      final attempt = EmployeeAttempt({
        'action': 'advance_repay',
        'id': 'record',
        'request_id': 'request',
        'employee_id': 'user-a',
        'expected_version': 1,
        'amount': '100.10',
      });
      await expectLater(
        repo.submit(session, attempt),
        throwsA(isA<EmployeeUncertain>()),
      );
      malformed = false;
      await repo.submit(session, attempt);
      expect(bodies[0], bodies[1]);
      expect((jsonDecode(bodies[0]) as Map)['amount'], '100.10');
    },
  );
  test('workspace refuses another actor and unknown contract version', () {
    expect(
      () => EmployeeWorkspace.parse({
        'contract_version': 1,
        'actor': {'user_id': 'other'},
      }, session),
      throwsFormatException,
    );
    expect(
      () => EmployeeWorkspace.parse({
        'contract_version': 2,
        'actor': {'user_id': 'user-a'},
      }, session),
      throwsFormatException,
    );
  });
}
