import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/employee_operations/attendance_outbox.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_operations_repository.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_operations_service.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart';
import 'package:gilbic_mobile/src/features/employee/employee_operations_page.dart';
import 'package:http/testing.dart';
import 'employee_operations_widget_test.dart' as fixture;
import 'support/android_role_fixture.dart';

class _EmployeeRepository extends EmployeeOperationsRepository {
  _EmployeeRepository()
    : super(
        StaffOperationsClient(
          deviceIdentityProvider: fixture.identity(),
          client: MockClient((request) async {
            throw StateError('No read-recovery test may issue a mutation');
          }),
        ),
      );

  int calls = 0;
  int? failure;
  Completer<EmployeeWorkspace>? pending;

  EmployeeWorkspace snapshot() {
    final data = fixture.workspace(owner: true);
    data['payroll'] = [
      {
        'id': fixture.recordId,
        'employee_id': fixture.user,
        'version': 1,
        'status': 'approved',
        'allowed_actions': [],
        'payload': {
          'week_start': '2026-09-13',
          'net_pay': '987.65',
          'components': [],
        },
      },
    ];
    return EmployeeWorkspace.parse(data, fixture.employeeSession);
  }

  @override
  Future<EmployeeWorkspace> workspace(
    UserSession session, {
    String? requestId,
  }) async {
    calls++;
    if (pending != null) return pending!.future;
    if (failure != null) {
      throw SpinaApiException(
        'private_employee_backend_detail',
        statusCode: failure,
      );
    }
    return snapshot();
  }
}

Future<EmployeeOperationsService> _open(
  WidgetTester tester,
  _EmployeeRepository repository, {
  Future<void> Function()? onSignOut,
}) async {
  final provider = fixture.identity();
  final service = EmployeeOperationsService(
    deviceIdentityProvider: provider,
    repository: repository,
    outbox: AttendanceOutbox(MemoryAttendanceVault()),
  );
  addTearDown(service.dispose);
  // Stop the independent background timer; the page still owns this read.
  service.foreground(false);
  await pumpAndroidRoleFixture(
    tester,
    size: const Size(412, 915),
    textScaler: TextScaler.linear(1),
    home: EmployeeOperationsPage(
      session: fixture.employeeSession,
      deviceIdentityProvider: provider,
      service: service,
      onSignOut: onSignOut,
      initialSection: EmployeeSection.payroll,
    ),
  );
  await tester.pumpAndSettle();
  return service;
}

VoidCallback _refresh(WidgetTester tester) => tester
    .widget<IconButton>(find.byKey(const Key('employee-refresh')))
    .onPressed!;

void main() {
  for (final status in [401, 426]) {
    testWidgets('Employee $status recovery calls explicit supplied sign-out', (
      tester,
    ) async {
      var signOuts = 0;
      final repository = _EmployeeRepository()..failure = status;
      await _open(
        tester,
        repository,
        onSignOut: () async {
          signOuts++;
        },
      );
      expect(signOuts, 0);
      expect(repository.calls, 1);
      await tester.tap(
        find.widgetWithText(
          OutlinedButton,
          status == 401 ? 'Sign in again' : 'Return to sign-in',
        ),
      );
      await tester.pumpAndSettle();
      expect(signOuts, 1);
      expect(repository.calls, 1);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('Employee service denial invalidates a pending workspace read', (
    tester,
  ) async {
    final repository = _EmployeeRepository();
    final service = await _open(tester, repository);
    final binding = service.binding!;
    final capture = await service.outbox.capture(
      binding,
      'clock_in',
      offline: true,
    );
    final refresh = _refresh(tester);
    final pending = Completer<EmployeeWorkspace>();
    repository.pending = pending;
    refresh();
    await tester.pump();
    await service.denyAttendance();
    service.notifyListeners();
    await tester.pump();
    expect(find.textContaining('987.65'), findsNothing);
    pending.complete(repository.snapshot());
    repository.pending = null;
    await tester.pumpAndSettle();
    expect(find.textContaining('987.65'), findsNothing);
    expect(service.binding, isNull);
    expect(service.accessDenied, isTrue);
    final retained = await service.outbox.entries(binding);
    expect(retained.single.command, capture.command);
    expect(retained.single.state, 'pending');
    expect(await service.outbox.isAuthorized(binding), isFalse);
    refresh();
    await tester.pump();
    expect(repository.calls, 2);
    expect(tester.takeException(), isNull);
  });

  for (final status in [401, 403, 426]) {
    testWidgets(
      'Employee $status blocks retained and visible refresh after clearing private records',
      (tester) async {
        final repository = _EmployeeRepository();
        final service = await _open(tester, repository);
        expect(find.textContaining('987.65'), findsWidgets);
        final refresh = _refresh(tester);
        repository.failure = status;
        refresh();
        await tester.pumpAndSettle();
        expect(find.textContaining('987.65'), findsNothing);
        expect(service.binding, isNull);
        final deniedCount = repository.calls;
        refresh();
        await tester.pumpAndSettle();
        expect(repository.calls, deniedCount);
        expect(
          tester
              .widget<IconButton>(find.byKey(const Key('employee-refresh')))
              .onPressed,
          isNull,
        );
        expect(
          find.textContaining('private_employee_backend_detail'),
          findsNothing,
        );
        expect(
          find.text(
            status == 401
                ? 'Sign in again'
                : status == 426
                ? 'Return to sign-in'
                : 'Access unavailable',
          ),
          findsOneWidget,
        );
        expect(tester.takeException(), isNull);
      },
    );
  }

  testWidgets(
    'Employee transient refresh keeps stale verified records read-only and protected attendance available',
    (tester) async {
      final repository = _EmployeeRepository();
      final service = await _open(tester, repository);
      final refresh = _refresh(tester);
      repository.failure = 503;
      refresh();
      await tester.pumpAndSettle();
      expect(find.textContaining('987.65'), findsWidgets);
      expect(
        find.textContaining(
          RegExp(
            'last successful|not refreshed|previously loaded',
            caseSensitive: false,
          ),
        ),
        findsWidgets,
      );
      expect(
        find.textContaining('private_employee_backend_detail'),
        findsNothing,
      );
      final create = find.byKey(const Key('employee-create-payroll_prepare'));
      expect(create, findsOneWidget);
      expect(tester.widget<OutlinedButton>(create).onPressed, isNull);
      tester
          .widget<DropdownButtonFormField<EmployeeSection>>(
            find.byType(DropdownButtonFormField<EmployeeSection>),
          )
          .onChanged!(EmployeeSection.attendance);
      await tester.pumpAndSettle();
      expect(service.binding, isNotNull);
      expect(
        tester
            .widget<FilledButton>(find.byKey(const Key('employee-clock_in')))
            .onPressed,
        isNotNull,
      );
      repository.failure = null;
      _refresh(tester)();
      await tester.pumpAndSettle();
      expect(repository.calls, 3);
      expect(
        find.textContaining(
          RegExp(
            'last successful|not refreshed|previously loaded',
            caseSensitive: false,
          ),
        ),
        findsNothing,
      );
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'Employee unknown initial read failure is safe unavailable state, not empty success',
    (tester) async {
      final repository = _EmployeeRepository()..failure = 500;
      await _open(tester, repository);
      expect(
        find.textContaining('private_employee_backend_detail'),
        findsNothing,
      );
      expect(find.text('No records available for your access.'), findsNothing);
      expect(
        find.textContaining(
          RegExp('unavailable|could not', caseSensitive: false),
        ),
        findsWidgets,
      );
      repository.failure = null;
      _refresh(tester)();
      await tester.pumpAndSettle();
      expect(find.textContaining('987.65'), findsWidgets);
      expect(repository.calls, 2);
    },
  );

  testWidgets(
    'Employee retained refresh deduplicates a pending workspace read',
    (tester) async {
      final repository = _EmployeeRepository();
      await _open(tester, repository);
      final refresh = _refresh(tester);
      final pending = Completer<EmployeeWorkspace>();
      repository.pending = pending;
      refresh();
      refresh();
      await tester.pump();
      final callsWhilePending = repository.calls;
      pending.complete(repository.snapshot());
      repository.pending = null;
      await tester.pumpAndSettle();
      expect(callsWhilePending, 2);
      expect(find.textContaining('987.65'), findsWidgets);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('Employee retained refresh is inert after disposal', (
    tester,
  ) async {
    final repository = _EmployeeRepository();
    await _open(tester, repository);
    final refresh = _refresh(tester);
    await tester.pumpWidget(const SizedBox());
    refresh();
    await tester.pump();
    expect(repository.calls, 1);
    expect(tester.takeException(), isNull);
  });
}
