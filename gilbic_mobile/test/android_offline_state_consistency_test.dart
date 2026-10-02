import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/employee_operations/attendance_outbox.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_operations_repository.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_operations_service.dart';
import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart';
import 'package:gilbic_mobile/src/features/employee/employee_operations_page.dart';
import 'package:http/testing.dart';
import 'employee_operations_widget_test.dart' show identity, workspace, employeeSession;
import 'support/android_role_fixture.dart';

void main() {
  testWidgets('device_saved_attendance_is_not_server_accepted', (tester) async {
    final provider = identity();
    final service = EmployeeOperationsService(deviceIdentityProvider: provider,
      repository: EmployeeOperationsRepository(StaffOperationsClient(deviceIdentityProvider: provider, client: MockClient((_) async => throw Exception('offline')))),
      outbox: AttendanceOutbox(MemoryAttendanceVault()));
    service.foreground(false);
    service.attach(employeeSession);
    await service.acceptWorkspace(employeeSession, EmployeeWorkspace.parse(workspace(), employeeSession));
    final original = await service.outbox.capture(service.binding!, 'clock_in', offline: true);
    await pumpAndroidRoleFixture(tester, size: const Size(360, 640), textScaler: TextScaler.linear(1.3),
      home: EmployeeOperationsPage(session: employeeSession, deviceIdentityProvider: provider, service: service));
    await tester.pumpAndSettle();
    expect(find.textContaining('Saved on this device — awaiting server sync'), findsOneWidget);
    expect(find.textContaining('Received by server'), findsNothing);
    expect((await service.outbox.entries(service.binding!)).single.command, original.command);
    service.attach(null);
    await tester.pumpWidget(const SizedBox());
    service.dispose();
  });
}
