import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_grouping.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/collector/collector_schedule.dart';
import 'package:gilbic_mobile/src/core/collector/collector_schedule_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collector_client_schedule_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_page.dart';

void main() {
  testWidgets(
    'Schedule opens a dedicated read-only Client Schedule surface',
    (tester) async {
      await _usePhoneSurface(tester);

      await tester.pumpWidget(
        MaterialApp(
          home: CollectorRoutePage(
            session: _session,
            loader: _ScheduleRouteLoader(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('route-client-client-schedule')));
      await tester.pumpAndSettle();
      expect(find.text('Client Tools'), findsOneWidget);

      await tester.tap(find.text('Schedule').first);
      await _pumpUntilFound(tester, find.text('Client Schedule'));

      expect(find.text('Client Schedule'), findsOneWidget);
      expect(
        find.textContaining(
          'connected in the next Area Management step',
        ),
        findsNothing,
      );
      expect(find.text('Edit'), findsNothing);
      expect(find.text('Save'), findsNothing);
      expect(find.text('Change Maturity'), findsNothing);
    },
  );

  testWidgets(
    'Client Schedule loads Regular and 7x7 separately in server row order',
    (tester) async {
      await _usePhoneSurface(tester);
      final repository = _FakeScheduleRepository();

      await tester.pumpWidget(
        MaterialApp(
          home: CollectorClientSchedulePage(
            session: _session,
            client: _clientGroup,
            repository: repository,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(
        repository.requestedLoanIds,
        <String>['loan-schedule-regular', 'loan-schedule-7x7'],
      );
      expect(
        find.byKey(const Key('schedule-section-loan-schedule-regular')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('schedule-section-loan-schedule-7x7')),
        findsOneWidget,
      );

      final regularPaid = find.byKey(
        const Key('schedule-row-loan-schedule-regular-0'),
      );
      final regularPastDue = find.byKey(
        const Key('schedule-row-loan-schedule-regular-1'),
      );
      expect(regularPaid, findsOneWidget);
      expect(regularPastDue, findsOneWidget);
      expect(
        tester.getTopLeft(regularPaid).dy,
        lessThan(tester.getTopLeft(regularPastDue).dy),
      );

      expect(find.text('2026-09-08'), findsOneWidget);
      expect(find.text('Paid'), findsOneWidget);
      expect(find.text('Past Due'), findsOneWidget);
      expect(find.text('Due Today'), findsOneWidget);
      expect(find.text('₱100.00'), findsWidgets);
      expect(find.text('₱35.00'), findsOneWidget);

      expect(find.text('Edit'), findsNothing);
      expect(find.text('Save'), findsNothing);
      expect(find.text('Change Maturity'), findsNothing);

      await tester.tap(regularPastDue);
      await tester.pumpAndSettle();

      expect(find.text('Schedule row details'), findsOneWidget);
      expect(find.textContaining('Paid amount'), findsOneWidget);
      expect(find.textContaining('Prepaid amount'), findsOneWidget);
      expect(find.textContaining('Remaining amount'), findsOneWidget);
      expect(find.textContaining('Client requested extension'), findsOneWidget);
      expect(find.textContaining('2026-09-10'), findsOneWidget);
      expect(find.textContaining('Principal component'), findsOneWidget);
      expect(find.textContaining('Interest component'), findsOneWidget);
      expect(find.text('Edit'), findsNothing);
      expect(find.text('Save'), findsNothing);
      expect(find.text('Change Maturity'), findsNothing);
    },
  );
}

Future<void> _usePhoneSurface(WidgetTester tester) async {
  await tester.binding.setSurfaceSize(const Size(430, 900));
  addTearDown(() async {
    await tester.binding.setSurfaceSize(null);
  });
}

Future<void> _pumpUntilFound(WidgetTester tester, Finder finder) async {
  for (var attempt = 0; attempt < 20 && finder.evaluate().isEmpty; attempt++) {
    await tester.pump(const Duration(milliseconds: 100));
  }
}

const UserSession _session = UserSession(
  userId: 'collector-schedule',
  username: 'collector.schedule',
  displayName: 'Collector Schedule',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'collector-schedule-token',
  permissions: <String>[
    'route.view',
    'collection.create',
  ],
);

const CollectorRouteEntry _regularEntry = CollectorRouteEntry(
  id: 'schedule-regular',
  clientId: 'client-schedule',
  loanId: 'loan-schedule-regular',
  clientName: 'Schedule Client',
  area: 'Cardona › Calahan',
  loanType: 'Regular',
  dailyAmount: 100,
  balance: 4200,
  status: 'Pending',
  passCount: 0,
  routeRevision: 'loan:schedule-regular:v1',
);

const CollectorRouteEntry _sevenBySevenEntry = CollectorRouteEntry(
  id: 'schedule-7x7',
  clientId: 'client-schedule',
  loanId: 'loan-schedule-7x7',
  clientName: 'Schedule Client',
  area: 'Cardona › Calahan',
  loanType: '7x7',
  dailyAmount: 35,
  balance: 2500,
  status: 'Pending',
  passCount: 0,
  routeRevision: 'loan:schedule-7x7:v1',
);

const CollectorRouteClientGroup _clientGroup = CollectorRouteClientGroup(
  clientId: 'client-schedule',
  clientName: 'Schedule Client',
  area: 'Cardona › Calahan',
  loans: <CollectorRouteEntry>[_regularEntry, _sevenBySevenEntry],
);

class _ScheduleRouteLoader implements CollectorRouteLoader {
  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async {
    return CollectorRouteLoadResult(
      route: CollectorRoute(
        routeDate: DateTime(2026, 9, 9),
        collectorName: 'Collector Schedule',
        areas: const <String>['Cardona › Calahan'],
        entries: const <CollectorRouteEntry>[
          _regularEntry,
          _sevenBySevenEntry,
        ],
        expectedTotal: 135,
      ),
      syncedAt: DateTime.utc(2026, 9, 9, 2),
      isFromCache: false,
    );
  }
}

class _FakeScheduleRepository implements CollectorScheduleRepository {
  final List<String> requestedLoanIds = <String>[];

  @override
  Future<CollectorSchedule> fetchSchedule(
    UserSession session, {
    required String loanId,
  }) async {
    requestedLoanIds.add(loanId);
    return switch (loanId) {
      'loan-schedule-regular' => CollectorSchedule.fromPayload(
          <String, Object?>{
            'loan_id': 'loan-schedule-regular',
            'loan_number': 'REG-1001',
            'client_id': 'client-schedule',
            'client_name': 'Schedule Client',
            'loan_type': 'Regular',
            'calculation_mode': 'regular_contract',
            'is_7x7': false,
            'schedule_id': 'schedule-regular-v1',
            'schedule_version': 1,
            'payment_frequency': 'daily',
            'contract_reference': 'REG-CONTRACT-1001',
            'as_of_date': '2026-09-09',
            'read_only': true,
            'past_due_amount': 50,
            'past_due_count': 1,
            'schedule_extension_slots': 1,
            'maturity_extended': true,
            'base_maturity': '2026-12-01',
            'updated_maturity': '2026-12-02',
            'maturity_projection_status': 'extended',
            'rows': <Object?>[
              <String, Object?>{
                'kind': 'installment',
                'date': '2026-09-08',
                'status': 'Paid',
                'amount': 100,
                'contractual_amount': 100,
                'paid_amount': 100,
                'prepaid_amount': 0,
                'remaining_amount': 0,
                'installment_id': 1,
                'installment_number': 1,
                'contractual_due_date': '2026-09-08',
                'principal_component': 80,
                'interest_component': 20,
                'principal_reduction_amount': 0,
                'promise_remaining_amount': 0,
              },
              <String, Object?>{
                'kind': 'installment',
                'date': '2026-09-09',
                'status': 'Past Due',
                'amount': 100,
                'contractual_amount': 100,
                'paid_amount': 50,
                'prepaid_amount': 0,
                'remaining_amount': 50,
                'installment_id': 2,
                'installment_number': 2,
                'contractual_due_date': '2026-09-09',
                'principal_component': 80,
                'interest_component': 20,
                'principal_reduction_amount': 0,
                'past_due_reason_code': 'promise_to_pay',
                'past_due_reason_note': 'Client requested extension',
                'promised_for_date': '2026-09-10',
                'promise_remaining_amount': 50,
                'promise_status': 'pending',
              },
            ],
          },
        ),
      'loan-schedule-7x7' => CollectorSchedule.fromPayload(
          <String, Object?>{
            'loan_id': 'loan-schedule-7x7',
            'loan_number': '7X7-2001',
            'client_id': 'client-schedule',
            'client_name': 'Schedule Client',
            'loan_type': '7x7',
            'calculation_mode': '7x7_interest',
            'is_7x7': true,
            'schedule_id': 'schedule-7x7-v1',
            'schedule_version': 1,
            'payment_frequency': 'daily',
            'contract_reference': '7X7-CONTRACT-2001',
            'as_of_date': '2026-09-09',
            'read_only': true,
            'past_due_amount': 0,
            'past_due_count': 0,
            'schedule_extension_slots': 0,
            'maturity_extended': false,
            'base_maturity': '2026-10-01',
            'updated_maturity': '2026-10-01',
            'maturity_projection_status': 'on_schedule',
            'rows': <Object?>[
              <String, Object?>{
                'kind': 'interest',
                'date': '2026-09-09',
                'status': 'Due Today',
                'amount': 35,
                'contractual_amount': 35,
                'paid_amount': 0,
                'prepaid_amount': 0,
                'remaining_amount': 35,
                'installment_id': 10,
                'installment_number': 1,
                'contractual_due_date': '2026-09-09',
                'principal_component': 0,
                'interest_component': 35,
                'principal_reduction_amount': 0,
                'promise_remaining_amount': 0,
              },
            ],
          },
        ),
      _ => throw StateError('Unexpected loan id $loanId'),
    };
  }
}
