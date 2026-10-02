import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/employee_operations/attendance_outbox.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_operations_repository.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_operations_service.dart';
import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart';
import 'package:gilbic_mobile/src/features/employee/employee_operations_page.dart';
import 'package:gilbic_mobile/src/features/employee/employee_record_presentation.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'employee_operations_widget_test.dart'
    show identity, workspace, employeeSession, recordId, user;
import 'support/android_role_fixture.dart';

void main() {
  for (final collection in [
    'attendance',
    'requests',
    'tasks',
    'advances',
    'payroll',
    'shortages',
    'accounting_preparations',
    'unknown',
  ]) {
    test(
      '$collection summaries use supplied values only and preserve authorized details',
      () {
        final record = <String, dynamic>{
          'id': 'original',
          'version': 9,
          'status': 'future_state',
          'payload': {
            'work_date': '2026-10-02',
            'amount': '1.2345',
            'unknown_fact': 'retained',
            'device_id': 'hidden',
          },
        };
        final view = presentEmployeeRecord(collection, record, 'Employee');
        expect(view.title, 'Employee');
        expect(view.status, isNot(contains('paid')));
        expect(view.detailKeys, contains('unknown_fact'));
        expect(view.detailKeys, isNot(contains('device_id')));
        expect(view.summaryFields.keys, isNot(contains('net_pay')));
        if (collection != 'unknown') {
          expect(view.summaryFields['amount'], '₱1.2345');
        }
        expect(record['id'], 'original');
        expect(record['version'], 9);
      },
    );
  }
  testWidgets(
    'payroll_approved_is_not_paid and safe details retain unknown facts',
    (tester) async {
      final provider = identity();
      final data = workspace();
      data['payroll'] = [
        {
          'id': recordId,
          'employee_id': user,
          'version': 7,
          'status': 'approved',
          'allowed_actions': [],
          'payload': {
            'payroll_kind': 'weekly',
            'week_start': '2026-10-02',
            'net_pay': '12345.60',
            'source_reference': 'safe-source',
            'new_fact': 'Unknown authorized fact',
            'device_id': 'private-device',
          },
        },
      ];
      final repository = EmployeeOperationsRepository(
        StaffOperationsClient(
          deviceIdentityProvider: provider,
          client: MockClient((request) async {
            expect(request.method, 'GET');
            return http.Response(jsonEncode(data), 200);
          }),
        ),
      );
      final service = EmployeeOperationsService(
        deviceIdentityProvider: provider,
        repository: repository,
        outbox: AttendanceOutbox(MemoryAttendanceVault()),
      );
      addTearDown(service.dispose);
      await pumpAndroidRoleFixture(
        tester,
        size: const Size(360, 640),
        textScaler: TextScaler.linear(1.3),
        home: EmployeeOperationsPage(
          session: employeeSession,
          deviceIdentityProvider: provider,
          service: service,
          initialSection: EmployeeSection.payroll,
        ),
      );
      await tester.pumpAndSettle();
      expect(
        find.textContaining('Payroll approved · payment not confirmed'),
        findsOneWidget,
      );
      expect(find.textContaining('₱12,345.60'), findsOneWidget);
      final card = find.byKey(const ValueKey('payroll-$recordId'));
      await tester.scrollUntilVisible(
        card,
        250,
        scrollable: find.byType(Scrollable).last,
      );
      await tester.tap(card);
      await tester.pumpAndSettle();
      expect(find.text('Details'), findsOneWidget);
      await tester.tap(find.text('Details'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Unknown authorized fact'), findsOneWidget);
      expect(find.textContaining('private-device'), findsNothing);
      expect(find.textContaining('Version: 7'), findsOneWidget);
      expect(tester.takeException(), isNull);
      service.attach(null);
      await tester.pumpWidget(const SizedBox());
      await tester.pump();
    },
  );
}
