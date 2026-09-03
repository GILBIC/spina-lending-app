import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_employee_activity.dart';
import 'package:gilbic_mobile/src/core/management/management_employee_activity_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_employee_activity_detail_page.dart';
import 'package:gilbic_mobile/src/features/management/management_employee_activity_page.dart'
    as feature;
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

void main() {
  testWidgets('compact employee rows remain readable on a small phone', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(360, 640));
    addTearDown(() async => tester.binding.setSurfaceSize(null));
    final repository = _FakeRepository(page: _page(), timeline: _timeline());

    await tester.pumpWidget(
      _app(
        MediaQuery(
          data: const MediaQueryData(
            size: Size(360, 640),
            textScaler: TextScaler.linear(1.3),
          ),
          child: _activityPage(repository),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Employee Name · Accounting'), findsOneWidget);
    expect(find.textContaining('6 completed'), findsOneWidget);
    expect(find.textContaining('1 awaiting Management'), findsOneWidget);
    expect(find.textContaining('1 needs attention'), findsOneWidget);
    expect(tester.takeException(), isNull);

    final row = find.byKey(const Key('employee-activity-row-$_employeeId'));
    await tester.drag(find.byType(ListView), const Offset(0, -500));
    await tester.pumpAndSettle();
    await tester.tap(row);
    await tester.pumpAndSettle();

    expect(find.byType(ManagementEmployeeActivityDetailPage), findsOneWidget);
    expect(find.text('Prepared journal entry'), findsOneWidget);
    expect(find.text('Maker: Employee Name'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('zero visible domains never implies the Employee did no work', (
    tester,
  ) async {
    final repository = _FakeRepository(
      page: _page(
        availableDomains: const <ManagementEmployeeActivityDomain>[],
        rows: <ManagementEmployeeActivityRow>[_noVisibleActivityRow],
      ),
      timeline: _timeline(),
    );

    await tester.pumpWidget(_app(_activityPage(repository)));
    await tester.pumpAndSettle();

    expect(
      find.text(
        'No Employee Activity domains are available under your current permissions.',
      ),
      findsOneWidget,
    );
    expect(find.text('No permitted activity in this range'), findsOneWidget);
    expect(find.textContaining('did no work'), findsNothing);
  });

  testWidgets('permission errors are safe and refreshable', (tester) async {
    final repository = _FakeRepository(
      error: const SpinaApiException(
        'Employee Activity review permission is required.',
        statusCode: 403,
        code: 'employee_activity_permission_required',
      ),
    );

    await tester.pumpWidget(_app(_activityPage(repository)));
    await tester.pumpAndSettle();

    expect(find.text('Employee Activity access unavailable'), findsOneWidget);
    expect(
      find.text('Employee Activity review permission is required.'),
      findsOneWidget,
    );
    expect(find.byKey(const Key('employee-activity-retry')), findsOneWidget);
  });

  testWidgets('loading and empty authorized results remain explicit', (
    tester,
  ) async {
    final repository = _DeferredRepository();
    await tester.pumpWidget(_app(_activityPage(repository)));
    await tester.pump();

    expect(find.byKey(const Key('employee-activity-loading')), findsOneWidget);

    repository.requests.single.complete(
      _page(rows: const <ManagementEmployeeActivityRow>[]),
    );
    await tester.pumpAndSettle();

    expect(
      find.text('No Employees matched the current authorized filters.'),
      findsOneWidget,
    );
  });

  testWidgets('refresh issues another read without adding write actions', (
    tester,
  ) async {
    final repository = _FakeRepository(page: _page(), timeline: _timeline());
    await tester.pumpWidget(_app(_activityPage(repository)));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('employee-activity-refresh')));
    await tester.pumpAndSettle();

    expect(repository.listCalls, 2);
    expect(find.text('Approve'), findsNothing);
    expect(find.text('Reject'), findsNothing);
    expect(find.text('Edit'), findsNothing);
  });

  testWidgets('new filters suppress an older in-flight response', (
    tester,
  ) async {
    final repository = _DeferredRepository();
    await tester.pumpWidget(_app(_activityPage(repository)));
    await tester.pump();
    expect(repository.requests, hasLength(1));

    await tester.enterText(
      find.byKey(const Key('employee-activity-search')),
      'Newer Employee',
    );
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pump();
    expect(repository.requests, hasLength(2));

    repository.requests[1].complete(_page(employeeName: 'Newer Employee'));
    await tester.pumpAndSettle();
    expect(find.text('Newer Employee · Accounting'), findsOneWidget);

    repository.requests[0].complete(_page(employeeName: 'Older Employee'));
    await tester.pumpAndSettle();
    expect(find.text('Newer Employee · Accounting'), findsOneWidget);
    expect(find.text('Older Employee · Accounting'), findsNothing);
  });

  testWidgets('domain and status filters issue read-only list requests', (
    tester,
  ) async {
    final repository = _FakeRepository(page: _page(), timeline: _timeline());
    await tester.pumpWidget(_app(_activityPage(repository)));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('employee-activity-domain-filter')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Accounting').last);
    await tester.pumpAndSettle();
    expect(repository.lastDomain, ManagementEmployeeActivityDomain.accounting);

    await tester.tap(find.byKey(const Key('employee-activity-status-filter')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Needs attention').last);
    await tester.pumpAndSettle();
    expect(
      repository.lastStatus,
      ManagementEmployeeActivityStatus.needsAttention,
    );
    expect(repository.listCalls, 3);
  });

  testWidgets('timeline opens only an authorized registered destination', (
    tester,
  ) async {
    final repository = _FakeRepository(page: _page(), timeline: _timeline());
    String? openedRecordId;
    await tester.pumpWidget(
      _app(
        ManagementEmployeeActivityDetailPage(
          session: _session,
          deviceId: 'management-phone',
          repository: repository,
          employeeUserId: _employeeId,
          employeeName: 'Employee Name',
          dateFrom: _businessDate,
          dateTo: _businessDate,
          onOpenGeneralJournal: (recordId) => openedRecordId = recordId,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(
      find.byKey(const Key('employee-activity-item-$_recordId')),
    );
    await tester.pump();

    expect(openedRecordId, _recordId);
    expect(repository.timelineCalls, 1);
  });

  testWidgets('timeline safely explains an item without a destination', (
    tester,
  ) async {
    final repository = _FakeRepository(
      page: _page(),
      timeline: _timeline(navigationCode: null),
    );
    await tester.pumpWidget(
      _app(
        ManagementEmployeeActivityDetailPage(
          session: _session,
          deviceId: 'management-phone',
          repository: repository,
          employeeUserId: _employeeId,
          employeeName: 'Employee Name',
          dateFrom: _businessDate,
          dateTo: _businessDate,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(
      find.byKey(const Key('employee-activity-item-$_recordId')),
    );
    await tester.pump();

    expect(
      find.text('Detailed review is unavailable for this item.'),
      findsOneWidget,
    );
  });
}

MaterialApp _app(Widget home) =>
    MaterialApp(theme: SpinaTheme.light, home: home);

feature.ManagementEmployeeActivityPage _activityPage(
  ManagementEmployeeActivityRepository repository,
) => feature.ManagementEmployeeActivityPage(
  session: _session,
  deviceIdentityProvider: _deviceProvider,
  repository: repository,
  initialDateFrom: _businessDate,
  initialDateTo: _businessDate,
);

final _deviceProvider = DeviceIdentityProvider(
  store: MemoryDeviceIdentityStore(),
  platformResolver: () => 'android',
  appVersionResolver: () async => '1.0.0+1',
);

const _employeeId = '33333333-3333-4333-8333-333333333333';
const _recordId = '44444444-4444-4444-8444-444444444444';
final _businessDate = DateTime.utc(2026, 8, 29);
final _generatedAt = DateTime.utc(2026, 8, 29, 4, 15, 30);

const _session = UserSession(
  userId: '22222222-2222-4222-8222-222222222222',
  username: 'manager',
  displayName: 'Management User',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'access-token',
  permissions: <String>[
    'employee.activity.review',
    'accounting.view',
    'support.manage',
    'remittance.view',
  ],
);

const _noVisibleActivityRow = ManagementEmployeeActivityRow(
  employeeUserId: _employeeId,
  employeeName: 'Employee Name',
  functionLabels: <String>[],
  completedCount: 0,
  inProgressCount: 0,
  awaitingReviewCount: 0,
  needsAttentionCount: 0,
  totalVisibleCount: 0,
  lastActivityAt: null,
  lastActivityDomain: null,
  status: ManagementEmployeeActivityStatus.noActivity,
  statusMessage: 'No permitted activity in this range.',
);

ManagementEmployeeActivityPage _page({
  String employeeName = 'Employee Name',
  List<ManagementEmployeeActivityDomain> availableDomains =
      const <ManagementEmployeeActivityDomain>[
        ManagementEmployeeActivityDomain.accounting,
      ],
  List<ManagementEmployeeActivityRow>? rows,
}) {
  final resultRows =
      rows ??
      <ManagementEmployeeActivityRow>[
        ManagementEmployeeActivityRow(
          employeeUserId: _employeeId,
          employeeName: employeeName,
          functionLabels: const <String>['Accounting'],
          completedCount: 6,
          inProgressCount: 0,
          awaitingReviewCount: 1,
          needsAttentionCount: 1,
          totalVisibleCount: 8,
          lastActivityAt: _generatedAt,
          lastActivityDomain: ManagementEmployeeActivityDomain.accounting,
          status: ManagementEmployeeActivityStatus.needsAttention,
          statusMessage: '1 item needs attention.',
        ),
      ];
  return ManagementEmployeeActivityPage(
    dateFrom: _businessDate,
    dateTo: _businessDate,
    generatedAt: _generatedAt,
    availableDomains: availableDomains,
    totalCount: resultRows.length,
    rows: resultRows,
  );
}

ManagementEmployeeActivityTimeline _timeline({
  ManagementEmployeeActivityNavigationCode? navigationCode =
      ManagementEmployeeActivityNavigationCode.generalJournals,
}) => ManagementEmployeeActivityTimeline(
  employeeUserId: _employeeId,
  employeeName: 'Employee Name',
  functionLabels: const <String>['Accounting'],
  dateFrom: _businessDate,
  dateTo: _businessDate,
  generatedAt: _generatedAt,
  availableDomains: const <ManagementEmployeeActivityDomain>[
    ManagementEmployeeActivityDomain.accounting,
  ],
  totalCount: 1,
  items: <ManagementEmployeeActivityItem>[
    ManagementEmployeeActivityItem(
      activityCode: ManagementEmployeeActivityCode.accountingJournalPrepared,
      domain: ManagementEmployeeActivityDomain.accounting,
      occurredAt: _generatedAt,
      businessDate: _businessDate,
      recordType: 'journal_entry',
      recordId: _recordId,
      displayReference: 'Draft journal',
      summary: 'Prepared journal entry',
      workflowState: 'draft',
      status: ManagementEmployeeActivityStatus.inProgress,
      makerName: 'Employee Name',
      checkerName: null,
      navigationCode: navigationCode,
    ),
  ],
);

class _FakeRepository implements ManagementEmployeeActivityRepository {
  _FakeRepository({this.page, this.timeline, this.error});

  final ManagementEmployeeActivityPage? page;
  final ManagementEmployeeActivityTimeline? timeline;
  final Object? error;
  int listCalls = 0;
  int timelineCalls = 0;
  ManagementEmployeeActivityDomain? lastDomain;
  ManagementEmployeeActivityStatus? lastStatus;

  @override
  Future<ManagementEmployeeActivityPage> listEmployees(
    UserSession session, {
    required String deviceId,
    required DateTime dateFrom,
    required DateTime dateTo,
    String? query,
    ManagementEmployeeActivityDomain? domain,
    ManagementEmployeeActivityStatus? status,
    int limit = 50,
    int offset = 0,
  }) async {
    listCalls += 1;
    lastDomain = domain;
    lastStatus = status;
    if (error != null) throw error!;
    return page!;
  }

  @override
  Future<ManagementEmployeeActivityTimeline> loadTimeline(
    UserSession session, {
    required String deviceId,
    required String employeeUserId,
    required DateTime dateFrom,
    required DateTime dateTo,
    ManagementEmployeeActivityDomain? domain,
    int limit = 100,
    int offset = 0,
  }) async {
    timelineCalls += 1;
    if (error != null) throw error!;
    return timeline!;
  }
}

class _DeferredRepository implements ManagementEmployeeActivityRepository {
  final requests = <Completer<ManagementEmployeeActivityPage>>[];

  @override
  Future<ManagementEmployeeActivityPage> listEmployees(
    UserSession session, {
    required String deviceId,
    required DateTime dateFrom,
    required DateTime dateTo,
    String? query,
    ManagementEmployeeActivityDomain? domain,
    ManagementEmployeeActivityStatus? status,
    int limit = 50,
    int offset = 0,
  }) {
    final request = Completer<ManagementEmployeeActivityPage>();
    requests.add(request);
    return request.future;
  }

  @override
  Future<ManagementEmployeeActivityTimeline> loadTimeline(
    UserSession session, {
    required String deviceId,
    required String employeeUserId,
    required DateTime dateFrom,
    required DateTime dateTo,
    ManagementEmployeeActivityDomain? domain,
    int limit = 100,
    int offset = 0,
  }) => throw StateError('Timeline is not expected.');
}
