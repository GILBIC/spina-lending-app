import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
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
  // These regressions catch dropping current producer fields from summaries.
  for (final fixture in [
    (
      'requests',
      {'request_kind': 'leave', 'work_date': '2026-10-02'},
      'request_kind',
      'leave',
    ),
    (
      'tasks',
      {'description': 'Visit the assigned client', 'due_date': '2026-10-04'},
      'due_date',
      '2026-10-04',
    ),
    (
      'shortages',
      {
        'expected_cash': '100.10',
        'accounted_cash': '90.00',
        'shortage_amount': '10.10',
      },
      'shortage_amount',
      '₱10.10',
    ),
  ]) {
    test('${fixture.$1} summary includes the authoritative producer field', () {
      final record = <String, dynamic>{
        'status': 'pending',
        'payload': fixture.$2,
      };
      final original = jsonEncode(record);
      final view = presentEmployeeRecord(fixture.$1, record, 'Worker');
      expect(view.summaryFields[fixture.$3], fixture.$4);
      expect(view.detailKeys, contains(fixture.$3));
      expect(jsonEncode(record), original);
    });
  }
  test('summary_uses_supplied_values_only across the seven record domains', () {
    for (final fixture in [
      (
        'attendance',
        {'event_type': 'clock_in', 'captured_at': '2026-10-02T00:15:00Z'},
        'captured_at',
        '2026-10-02 08:15',
      ),
      (
        'requests',
        {'request_type': 'historical leave', 'work_date': '2026-10-02'},
        'request_type',
        'historical leave',
      ),
      (
        'tasks',
        {'description': 'Long task ' * 30, 'due_date': '2026-10-04'},
        'due_date',
        '2026-10-04',
      ),
      (
        'advances',
        {'amount': '0.00', 'outstanding_amount': '1.2345'},
        'outstanding_amount',
        '₱1.2345',
      ),
      (
        'payroll',
        {
          'gross_pay': '12345.60',
          'deductions': '45.60',
          'period_end': '2026-10-03',
        },
        'gross_pay',
        '₱12,345.60',
      ),
      (
        'shortages',
        {'expected_cash': '100.10', 'accounted_cash': '90.00'},
        'shortage_amount',
        null,
      ),
      (
        'accounting_preparations',
        {
          'period_start': '2026-10-01',
          'period_end': '2026-10-03',
          'lines': [
            {'debit': '100.10', 'credit': '0.00'},
          ],
        },
        'period_start',
        '2026-10-01',
      ),
    ]) {
      final record = <String, dynamic>{
        'status': 'draft',
        'payload': fixture.$2,
      };
      final original = jsonEncode(record);
      final view = presentEmployeeRecord(fixture.$1, record, 'Worker');
      expect(view.summaryFields[fixture.$3], fixture.$4, reason: fixture.$1);
      expect(view.summaryFields.keys, isNot(contains('net_pay')));
      expect(view.summaryFields.keys, isNot(contains('paid_amount')));
      expect(jsonEncode(record), original);
    }
  });
  test(
    'unknown_record_retains_safe_details and excluded_metadata_stays_hidden',
    () {
      final record = <String, dynamic>{
        'status': 'future_state',
        'payload': {
          'new_fact': {'device_id': 'nested secret', 'safe': 'retained'},
          'amount': '0.00',
          'source_reference': 'source',
          'device_id': 'secret',
          'request_id': 'request',
        },
      };
      final original = jsonEncode(record);
      final view = presentEmployeeRecord('future_collection', record, 'Worker');
      expect(view.summaryFields, isEmpty);
      expect(view.detailKeys, ['new_fact', 'amount', 'source_reference']);
      expect(jsonEncode(record), original);
      expect(
        presentEmployeeRecord('payroll', {
          'payload': {},
        }, 'Worker').summaryFields,
        isEmpty,
      );
    },
  );
  for (final role in [
    AppRole.employee,
    AppRole.collector,
    AppRole.management,
  ]) {
    testWidgets(
      '${role.label} shared_roles_keep_distinct_authority and command_receives_original_id_and_version',
      (tester) async {
        final owner = role == AppRole.management;
        final action = owner ? 'shortage_decide' : 'shortage_respond';
        final subject = owner ? deviceSubject : user;
        final session = UserSession(
          userId: user,
          username: 'worker',
          displayName: 'Synthetic worker',
          role: role,
          rawRole: role.label,
          accessToken: 'test-token',
          permissions: ['employee.portal.view'],
        );
        final provider = identity();
        final data = workspace(owner: owner);
        data['setup_missing'] = ['Effective schedule needed'];
        data['shortages'] = [
          {
            'id': recordId,
            'employee_id': subject,
            'version': 7,
            'status': 'reported',
            'allowed_actions': [action],
            'payload': {
              'work_date': '2026-10-02',
              'shortage_amount': '10.10',
              'source_reference': 'synthetic source',
              'unknown_fact': {
                'safe': 'Authorized nested fact ' * 20,
                'device_id': 'private-nested-device',
              },
              'device_id': 'private-device',
            },
          },
        ];
        data['history'] = [
          for (final version in [2, 1])
            {
              'domain': 'shortages',
              'record_id': recordId,
              'version': version,
              'action': 'shortage_report',
              'created_at': '2026-10-02T00:00:00Z',
              'status': 'reported',
              'payload': {
                'note': 'Synthetic history $version',
                'request_id': 'private-history-request',
              },
            },
          {
            'domain': 'tasks',
            'record_id': recordId,
            'version': 99,
            'payload': {'note': 'Unrelated history'},
          },
        ];
        final original = jsonEncode(data);
        final commands = <Map<String, dynamic>>[];
        final repository = EmployeeOperationsRepository(
          StaffOperationsClient(
            deviceIdentityProvider: provider,
            client: MockClient((request) async {
              if (request.method == 'GET') {
                return http.Response(jsonEncode(data), 200);
              }
              final command = jsonDecode(request.body) as Map<String, dynamic>;
              commands.add(command);
              return http.Response(
                jsonEncode({
                  'id': command['id'],
                  'request_id': command['request_id'],
                  'version': 8,
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
        await pumpAndroidRoleFixture(
          tester,
          size: const Size(320, 640),
          textScaler: TextScaler.linear(2),
          home: EmployeeOperationsPage(
            session: session,
            deviceIdentityProvider: provider,
            service: service,
            initialSection: EmployeeSection.shortages,
          ),
        );
        await tester.pumpAndSettle();
        expect(find.text('Setup needed'), findsOneWidget);
        expect(find.textContaining('₱10.10'), findsOneWidget);
        expect(find.textContaining('₱0'), findsNothing);
        final card = find.byKey(const ValueKey('shortages-$recordId'));
        await tester.scrollUntilVisible(
          card,
          250,
          scrollable: find.byType(Scrollable).last,
        );
        await tester.tap(card);
        await tester.pumpAndSettle();
        final permitted = find.byKey(Key('employee-action-$action-$recordId'));
        expect(permitted, findsOneWidget);
        expect(
          find.byKey(
            Key(
              'employee-action-${owner ? 'shortage_respond' : 'shortage_decide'}-$recordId',
            ),
          ),
          findsNothing,
        );
        // A permitted next action must precede optional details in the hierarchy.
        expect(
          tester.getTopLeft(permitted).dy,
          lessThan(tester.getTopLeft(find.text('Details')).dy),
        );
        await tester.ensureVisible(find.text('Details'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Details'));
        await tester.pumpAndSettle();
        expect(find.textContaining('Authorized nested fact'), findsOneWidget);
        expect(find.textContaining('private-device'), findsNothing);
        expect(find.textContaining('private-nested-device'), findsNothing);
        expect(find.textContaining('Version: 7'), findsOneWidget);
        expect(find.textContaining('Record id: $recordId'), findsOneWidget);
        await tester.ensureVisible(find.text('Details'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Details'));
        await tester.pumpAndSettle();
        await tester.ensureVisible(find.text('Record history'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Record history'));
        await tester.pumpAndSettle();
        expect(
          tester.getTopLeft(find.textContaining('Synthetic history 2')).dy,
          lessThan(
            tester.getTopLeft(find.textContaining('Synthetic history 1')).dy,
          ),
        );
        expect(find.textContaining('Unrelated history'), findsNothing);
        expect(find.textContaining('private-history-request'), findsNothing);
        await tester.ensureVisible(permitted);
        await tester.pumpAndSettle();
        await tester.tap(permitted);
        await tester.pumpAndSettle();
        if (owner) {
          final decision = find.byKey(const Key('employee-field-decision'));
          await tester.ensureVisible(decision);
          await tester.pumpAndSettle();
          await tester.tap(decision);
          await tester.pumpAndSettle();
          await tester.tap(find.text('Confirmed').last);
          await tester.pumpAndSettle();
          for (final field in ['reason', 'response_opportunity']) {
            final input = find.byKey(Key('employee-field-$field'));
            await tester.ensureVisible(input);
            await tester.pumpAndSettle();
            await tester.enterText(input, 'Synthetic reviewed evidence');
          }
        } else {
          final input = find.byKey(const Key('employee-field-explanation'));
          await tester.ensureVisible(input);
          await tester.pumpAndSettle();
          await tester.enterText(input, 'Synthetic employee explanation');
        }
        await tester.ensureVisible(find.byKey(const Key('employee-submit')));
        await tester.pumpAndSettle();
        await tester.tap(find.byKey(const Key('employee-submit')));
        await tester.pumpAndSettle();
        expect(commands, hasLength(1));
        expect(commands.single['id'], recordId);
        expect(commands.single['expected_version'], 7);
        expect(commands.single['employee_id'], subject);
        expect(commands.single['action'], action);
        expect(jsonEncode(data), original);
        expect(tester.takeException(), isNull);
        service.attach(null);
        await tester.pumpWidget(const SizedBox());
        await tester.pump();
      },
    );
  }
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

const deviceSubject = '00000000-0000-4000-8000-000000000005';
