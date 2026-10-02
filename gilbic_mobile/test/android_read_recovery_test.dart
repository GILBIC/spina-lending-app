import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan_repository.dart';
import 'package:gilbic_mobile/src/core/loans/client_schedule.dart';
import 'package:gilbic_mobile/src/core/loans/client_schedule_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/client/client_dashboard.dart';
import 'support/android_role_fixture.dart';
import 'support/client_fixture.dart';
import 'support/role_homes.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/management/management_dashboard_overview.dart';
import 'package:gilbic_mobile/src/core/management/management_dashboard_overview_repository.dart';

class DeferredOverview implements ManagementDashboardOverviewRepository {
  final pending = Completer<ManagementDashboardOverview>();
  @override
  Future<ManagementDashboardOverview> loadOverview(
    UserSession session, {
    required String deviceId,
  }) => pending.future;
}

class RevocableOverview extends SyntheticOverview {
  bool denied = false;
  @override
  Future<ManagementDashboardOverview> loadOverview(
    UserSession session, {
    required String deviceId,
  }) => denied
      ? Future.error(
          const SpinaApiException('column private_secret', statusCode: 403),
        )
      : super.loadOverview(session, deviceId: deviceId);
}

class ControlledSchedules implements ClientScheduleRepository {
  final calls = <String>[];
  final pending = Completer<ClientLoanSchedule>();
  bool fail = true;
  bool defer = false;
  int failureStatus = 500;
  @override
  Future<ClientLoanSchedule> loadSchedule(
    UserSession session, {
    required String deviceId,
    required String loanId,
  }) {
    calls.add(loanId);
    if (defer) return pending.future;
    if (fail) {
      return Future.error(
        SpinaApiException('secret', statusCode: failureStatus),
      );
    }
    return FakeClientScheduleRepository().loadSchedule(
      session,
      deviceId: deviceId,
      loanId: loanId,
    );
  }
}

class ControlledPortfolio implements ClientLoanRepository {
  final pending = Completer<ClientLoanPortfolio>();
  @override
  Future<ClientLoanPortfolio> loadPortfolio(
    UserSession session, {
    required String deviceId,
  }) => pending.future;
}

Future<void> open(
  WidgetTester tester, {
  ClientLoanRepository? loans,
  ClientScheduleRepository? schedules,
  Future<void> Function()? signOut,
}) => pumpAndroidRoleFixture(
  tester,
  size: const Size(412, 915),
  textScaler: TextScaler.linear(1),
  home: ClientDashboard(
    session: clientSession(),
    deviceIdentityProvider: clientIdentity(),
    onSignOut: signOut ?? () async {},
    loanRepository: loans ?? FakeClientLoanRepository(clientPortfolio()),
    scheduleRepository: schedules ?? FakeClientScheduleRepository(),
  ),
);
void main() {
  testWidgets('Management changed session discards late private overview', (
    tester,
  ) async {
    final old = DeferredOverview();
    await pumpAndroidRoleFixture(
      tester,
      size: const Size(412, 915),
      textScaler: TextScaler.linear(1),
      home: roleHome(AppRole.management, overview: old),
    );
    await tester.pump();
    await pumpAndroidRoleFixture(
      tester,
      size: const Size(412, 915),
      textScaler: TextScaler.linear(1),
      home: roleHome(AppRole.management),
    );
    await tester.pump(const Duration(milliseconds: 50));
    expect(find.byKey(const Key('management-overview-facts')), findsOneWidget);
    old.pending.complete(
      ManagementDashboardOverview(
        generatedAt: DateTime.utc(2026, 10, 2),
        currency: 'PHP',
        ignoredMetricKeys: const [],
        metrics: [
          ManagementDashboardMetric(
            key: ManagementDashboardMetricKey.values.first,
            count: 66,
            amount: '666.66',
            asOfDate: DateTime(2026, 10, 2),
          ),
        ],
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('₱666.66'), findsNothing);
  });
  testWidgets(
    'Management denied refresh clears facts and has no permission retry',
    (tester) async {
      final repository = RevocableOverview();
      await pumpAndroidRoleFixture(
        tester,
        size: const Size(412, 915),
        textScaler: TextScaler.linear(1),
        home: roleHome(AppRole.management, overview: repository),
      );
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('management-overview-facts')),
        findsOneWidget,
      );
      repository.denied = true;
      await tester.tap(find.byKey(const Key('management-overview-refresh')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('management-overview-facts')), findsNothing);
      expect(find.byKey(const Key('management-overview-retry')), findsNothing);
      expect(find.textContaining('private_secret'), findsNothing);
    },
  );
  for (final status in [401, 403]) {
    testWidgets(
      'nested schedule $status is visible and clears denied private snapshot',
      (tester) async {
        await open(
          tester,
          schedules: ControlledSchedules()..failureStatus = status,
        );
        await tester.pumpAndSettle();
        expect(
          find.text(status == 401 ? 'Sign in again' : 'Access unavailable'),
          findsOneWidget,
        );
        expect(find.text('Official remaining balance'), findsNothing);
        expect(find.text('Retry schedule'), findsNothing);
      },
    );
  }
  testWidgets('schedule Retry deduplicates a pending same-loan read', (
    tester,
  ) async {
    final schedules = ControlledSchedules();
    await open(tester, schedules: schedules);
    await tester.pumpAndSettle();
    final retry = tester
        .widget<OutlinedButton>(
          find.widgetWithText(OutlinedButton, 'Retry schedule'),
        )
        .onPressed!;
    schedules.defer = true;
    retry();
    retry();
    await tester.pump();
    expect(schedules.calls.length, 2);
    schedules.pending.complete(
      await FakeClientScheduleRepository().loadSchedule(
        clientSession(),
        deviceId: 'device',
        loanId: 'seven-by-seven-loan',
      ),
    );
    await tester.pumpAndSettle();
  });
  testWidgets('Management review required never presents a zero payoff', (
    tester,
  ) async {
    await open(
      tester,
      schedules: FakeClientScheduleRepository(
        penaltyStatus: 'management_review_required',
        reviewReason: 'Server review required',
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Management review required'), findsOneWidget);
    expect(find.text('Exact payoff'), findsNothing);
    expect(find.text('₱0.00'), findsNothing);
  });
  testWidgets('client_401_action_enters_session_recovery', (tester) async {
    var signedOut = 0;
    await open(
      tester,
      loans: FakeClientLoanRepository.failure(
        const SpinaApiException('expired', statusCode: 401),
      ),
      signOut: () async {
        signedOut++;
      },
    );
    await tester.pumpAndSettle();
    expect(find.text('Sign in again'), findsOneWidget);
    await tester.tap(find.text('Sign in again'));
    expect(signedOut, 1);
  });
  testWidgets('client_403_clears_affected_data', (tester) async {
    await open(
      tester,
      loans: FakeClientLoanRepository.failure(
        const SpinaApiException('denied', statusCode: 403),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Access unavailable'), findsOneWidget);
    expect(find.text('Retry'), findsNothing);
    expect(find.text('Official remaining balance'), findsNothing);
  });
  testWidgets('schedule_failure_keeps_other_loans_and_shows_retry', (
    tester,
  ) async {
    final schedules = ControlledSchedules();
    await open(tester, schedules: schedules);
    await tester.pumpAndSettle();
    expect(find.text('Official remaining balance'), findsNWidgets(2));
    expect(
      find.text('Schedule/payoff information unavailable'),
      findsOneWidget,
    );
    expect(find.text('Exact payoff'), findsNothing);
    schedules.fail = false;
    await tester.tap(find.text('Retry schedule'));
    await tester.pumpAndSettle();
    expect(schedules.calls, ['seven-by-seven-loan', 'seven-by-seven-loan']);
    expect(find.text('Schedule/payoff information unavailable'), findsNothing);
  });
  testWidgets('verified portfolio renders before a deferred schedule', (
    tester,
  ) async {
    final schedules = ControlledSchedules()..defer = true;
    await open(tester, schedules: schedules);
    await tester.pump();
    await tester.pump();
    expect(find.text('Official remaining balance'), findsNWidgets(2));
    expect(find.text('Loading schedule/payoff information'), findsOneWidget);
    schedules.pending.complete(
      await FakeClientScheduleRepository().loadSchedule(
        clientSession(),
        deviceId: 'device',
        loanId: 'seven-by-seven-loan',
      ),
    );
    await tester.pumpAndSettle();
  });
  testWidgets('old_read_cannot_overwrite_new_session', (tester) async {
    final old = ControlledPortfolio();
    await open(tester, loans: old);
    await tester.pump();
    await open(
      tester,
      loans: FakeClientLoanRepository.failure(
        const SpinaApiException('denied', statusCode: 403),
      ),
    );
    await tester.pumpAndSettle();
    old.pending.complete(clientPortfolio());
    await tester.pumpAndSettle();
    expect(find.text('Official remaining balance'), findsNothing);
    expect(find.text('Access unavailable'), findsOneWidget);
  });
}
