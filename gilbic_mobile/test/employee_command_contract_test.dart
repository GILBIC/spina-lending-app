import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/employee_operations/attendance_outbox.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_action_schema.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_form_values.dart';

const employee = '00000000-0000-4000-8000-000000000001';
const device = '00000000-0000-4000-8000-000000000002';
void main() {
  test(
    'every typed form builds a strict command with exact money for backend cross-validation',
    () async {
      final commands = <Map<String, dynamic>>[];
      for (final action in employeeActionFields.keys.where(
        (key) => key != 'attendance_record',
      )) {
        final values = <String, dynamic>{};
        for (final field in employeeActionFields[action]!) {
          final name = field['name'] as String;
          values[name] = switch (field['kind']) {
            'employee' => employee,
            'record' => device,
            'money' => '100.10',
            'integer' =>
              name == 'year'
                  ? '2026'
                  : name == 'ordinary_leave_days_per_year'
                  ? '5'
                  : '240',
            'date' => name == 'month' ? '2026-09-01' : '2026-09-20',
            'timestamp' => '2026-09-20T06:00:00+08:00',
            'time' => name == 'start_time' ? '06:00' : '15:00',
            'bool' => false,
            'choice' => (field['options'] as List).first,
            'days' => [1, 2, 3, 4, 5, 6],
            'duties' => ['review_requests'],
            'installments' => [
              {'due_date': '2026-09-26', 'amount': '100.10'},
            ],
            'lines' => [
              {
                'account_code': 'TEST-CASH',
                'debit': '100.10',
                'credit': '0.00',
              },
              {
                'account_code': 'TEST-WAGES',
                'debit': '0.00',
                'credit': '100.10',
              },
            ],
            'dates' => ['2026-09-20'],
            _ => 'Synthetic reviewed evidence only',
          };
        }
        if (action == 'leave_conversion_request') values['minutes'] = '2400';
        final command = buildEmployeeCommand(
          action: action,
          values: values,
          requestId: employeeRequestId(),
          newRecordId: employeeRequestId(),
        );
        expect(command['action'], action);
        for (final field in employeeActionFields[action]!.where(
          (field) => field['kind'] == 'money',
        )) {
          expect(
            command[field['name']],
            isA<String>(),
            reason: '$action.${field['name']}',
          );
        }
        commands.add(command);
      }
      final outbox = AttendanceOutbox(MemoryAttendanceVault());
      const binding = AttendanceBinding(
        userId: employee,
        installationId: 'synthetic-installation',
        deviceId: device,
      );
      await outbox.authorize(binding);
      commands.add(
        (await outbox.capture(
          binding,
          'clock_in',
          capturedAt: DateTime.utc(2026, 9, 20, 0),
          offline: true,
        )).command,
      );
      expect(commands.length, 30);
      final artifact = Platform.environment['EMPLOYEE_CONTRACT_ARTIFACT'];
      if (artifact != null) {
        File(artifact).writeAsStringSync(
          const JsonEncoder.withIndent('  ').convert(commands),
        );
      }
    },
  );
  test(
    'typed form rejects floating point money, invalid dates and unknown commands',
    () {
      expect(
        employeeFieldError({'kind': 'money', 'required': true}, 100.10),
        isNotNull,
      );
      expect(
        employeeFieldError({'kind': 'money', 'required': true}, '0.001'),
        isNotNull,
      );
      expect(
        employeeFieldError({'kind': 'date', 'required': true}, '2026-02-31'),
        isNotNull,
      );
      expect(
        () => buildEmployeeCommand(
          action: 'post_journal',
          values: {},
          requestId: employee,
          newRecordId: device,
        ),
        throwsArgumentError,
      );
    },
  );
}
