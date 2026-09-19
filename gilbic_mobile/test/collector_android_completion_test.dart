import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_grouping.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_repository.dart';
import 'package:gilbic_mobile/src/core/collector/collector_schedule.dart';
import 'package:gilbic_mobile/src/core/collector/collector_schedule_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/collector/collector_client_schedule_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_page.dart';

void main() {
  for (final status in <int>[401, 403, 426]) {
    test(
      'route rejection $status clears the offline copy and stays blocked',
      () async {
        final cache = MemoryCollectorRouteCache();
        await cache.writeForUser(
          _session.userId,
          _route,
          DateTime.utc(2026, 9, 19),
        );
        final repository = _RouteRepository()..failureStatus = status;
        final loader = CachedCollectorRouteLoader(
          remote: repository,
          cache: cache,
        );

        await expectLater(
          loader.loadToday(_session),
          throwsA(
            isA<SpinaApiException>().having(
              (error) => error.statusCode,
              'status',
              status,
            ),
          ),
        );
        expect(await cache.readForUser(_session.userId), isNull);
      },
    );

    testWidgets(
      'route refresh rejection $status removes live clients and payment actions',
      (tester) async {
        await tester.binding.setSurfaceSize(const Size(430, 1000));
        addTearDown(() => tester.binding.setSurfaceSize(null));
        final repository = _RouteRepository();
        final loader = CachedCollectorRouteLoader(
          remote: repository,
          cache: MemoryCollectorRouteCache(),
        );
        await tester.pumpWidget(
          MaterialApp(
            home: CollectorRoutePage(session: _session, loader: loader),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.text('Protected Client'), findsOneWidget);
        expect(
          find.byKey(const Key('record-collection-entry-1')),
          findsOneWidget,
        );

        repository.failureStatus = status;
        await tester.tap(find.byTooltip('Refresh route'));
        await tester.pumpAndSettle();

        expect(find.text('Protected Client'), findsNothing);
        expect(
          find.byKey(const Key('record-collection-entry-1')),
          findsNothing,
        );
        expect(
          find.byKey(const Key('collector-offline-read-only')),
          findsNothing,
        );
        expect(find.text('Try again'), findsOneWidget);
      },
    );
  }

  testWidgets(
    '7x7 schedule displays exact current payoff and distinct penalty facts',
    (tester) async {
      await _showSchedule(tester, _schedulePayload());
      expect(find.text('As of 2026-09-19'), findsOneWidget);
      expect(
        find.text('Current payoff: ₱90,071,992,547,409.93'),
        findsOneWidget,
      );
      expect(find.text('Projected penalty: ₱1.01'), findsOneWidget);
      expect(find.text('Assessed penalty balance: ₱2.02'), findsOneWidget);
      expect(find.text('Penalty base: ₱89.00'), findsOneWidget);
      expect(find.text('Remaining cost headroom: ₱100.00'), findsOneWidget);
      expect(find.text('₱90,071,992,547,409.93'), findsOneWidget);
      await tester.tap(find.byKey(const Key('schedule-row-loan-1-0')));
      await tester.pumpAndSettle();
      expect(
        find.text('Remaining amount: ₱90,071,992,547,409.93'),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    '7x7 review-required schedule does not present zero as a payoff',
    (tester) async {
      await _showSchedule(
        tester,
        _schedulePayload()
          ..['penalty_status'] = 'management_review_required'
          ..['exact_payoff_total'] = '0.00'
          ..['management_review_required_reason'] =
              'Signed penalty authority needs Management review.',
      );
      expect(find.text('Management review required'), findsOneWidget);
      expect(
        find.text('Signed penalty authority needs Management review.'),
        findsOneWidget,
      );
      expect(find.textContaining('Current payoff:'), findsNothing);
    },
  );

  testWidgets('missing 7x7 payoff stays unavailable instead of becoming zero', (
    tester,
  ) async {
    await _showSchedule(
      tester,
      _schedulePayload()..remove('exact_payoff_total'),
    );
    expect(
      find.text(
        'Current payoff unavailable. Refresh the schedule or contact Management.',
      ),
      findsOneWidget,
    );
    expect(find.textContaining('Current payoff:'), findsNothing);
  });

  test(
    'schedule refuses malformed authoritative money instead of replacing it with zero',
    () {
      expect(
        () => CollectorSchedule.fromPayload(
          _schedulePayload()..['past_due_amount'] = 'not-money',
        ),
        throwsA(isA<SpinaApiException>()),
      );
    },
  );
}

Future<void> _showSchedule(
  WidgetTester tester,
  Map<String, Object?> payload,
) async {
  await tester.binding.setSurfaceSize(const Size(600, 1400));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(
    MaterialApp(
      home: CollectorClientSchedulePage(
        session: _session,
        client: const CollectorRouteClientGroup(
          clientId: 'client-1',
          clientName: 'Protected Client',
          area: 'Cardona',
          loans: <CollectorRouteEntry>[_entry],
        ),
        repository: _ScheduleRepository(payload),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

const _session = UserSession(
  userId: 'collector-1',
  username: 'collector.one',
  displayName: 'Collector One',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'token',
  permissions: <String>['route.view', 'collection.create'],
);
const _entry = CollectorRouteEntry(
  id: 'entry-1',
  clientId: 'client-1',
  loanId: 'loan-1',
  clientName: 'Protected Client',
  area: 'Cardona',
  loanType: '7x7',
  dailyAmount: 100,
  balance: 900,
  status: 'Pending',
  passCount: 0,
  routeRevision: 'revision-1',
  sevenBySevenMobileEnabled: true,
);
final _route = CollectorRoute(
  routeDate: DateTime(2026, 9, 19),
  collectorName: 'Collector One',
  areas: const <String>['Cardona'],
  entries: const <CollectorRouteEntry>[_entry],
  expectedTotal: 100,
);

class _RouteRepository implements CollectorRouteRepository {
  int? failureStatus;
  @override
  Future<CollectorRoute> fetchToday(UserSession session) async {
    if (failureStatus != null) {
      throw SpinaApiException('Access rejected.', statusCode: failureStatus);
    }
    return _route;
  }
}

class _ScheduleRepository implements CollectorScheduleRepository {
  _ScheduleRepository(this.payload);
  final Map<String, Object?> payload;
  @override
  Future<CollectorSchedule> fetchSchedule(
    UserSession session, {
    required String loanId,
  }) async => CollectorSchedule.fromPayload(payload);
}

Map<String, Object?> _schedulePayload() => <String, Object?>{
  'loan_id': 'loan-1',
  'loan_number': '7X7-1',
  'client_id': 'client-1',
  'client_name': 'Protected Client',
  'loan_type': '7x7',
  'calculation_mode': 'seven_by_seven',
  'is_7x7': true,
  'schedule_id': 'schedule-1',
  'schedule_version': 1,
  'payment_frequency': 'daily',
  'contract_reference': 'contract-1',
  'as_of_date': '2026-09-19',
  'read_only': true,
  'past_due_amount': '89.00',
  'past_due_count': 1,
  'schedule_extension_slots': 0,
  'maturity_extended': false,
  'base_maturity': '2026-09-18',
  'updated_maturity': '2026-09-18',
  'maturity_projection_status': 'on_schedule',
  'penalty_status': 'projected',
  'projected_penalty': '1.01',
  'assessed_penalty_balance': '2.02',
  'penalty_base': '89.00',
  'remaining_cost_headroom': '100.00',
  'exact_payoff_total': '90071992547409.93',
  'management_review_required_reason': '',
  'rows': <Object?>[
    <String, Object?>{
      'kind': 'installment',
      'date': '2026-09-18',
      'status': 'Past Due',
      'amount': '90071992547409.93',
      'contractual_amount': '90071992547409.93',
      'paid_amount': '0.00',
      'prepaid_amount': '0.00',
      'remaining_amount': '90071992547409.93',
      'installment_id': 1,
      'installment_number': 1,
      'contractual_due_date': '2026-09-18',
      'principal_component': '80.00',
      'interest_component': '9.00',
      'principal_reduction_amount': '0.00',
      'past_due_reason_code': null,
      'past_due_reason_note': null,
      'promised_for_date': null,
      'promise_remaining_amount': '0.00',
      'promise_status': null,
      'no_collection_reason': null,
    },
  ],
};
