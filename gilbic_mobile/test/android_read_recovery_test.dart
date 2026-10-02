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

class ControlledSchedules implements ClientScheduleRepository {
  final calls = <String>[];
  final pending = Completer<ClientLoanSchedule>();
  bool fail = true;
  bool defer = false;
  @override
  Future<ClientLoanSchedule> loadSchedule(UserSession session, {required String deviceId, required String loanId}) {
    calls.add(loanId);
    if (defer) return pending.future;
    if (fail) return Future.error(const SpinaApiException('secret', statusCode: 500));
    return FakeClientScheduleRepository().loadSchedule(session, deviceId: deviceId, loanId: loanId);
  }
}
class ControlledPortfolio implements ClientLoanRepository {
  final pending = Completer<ClientLoanPortfolio>();
  @override
  Future<ClientLoanPortfolio> loadPortfolio(UserSession session, {required String deviceId}) => pending.future;
}
Future<void> open(WidgetTester tester, {ClientLoanRepository? loans, ClientScheduleRepository? schedules, Future<void> Function()? signOut}) => pumpAndroidRoleFixture(tester,
  size: const Size(412, 915), textScaler: TextScaler.linear(1), home: ClientDashboard(
    session: clientSession(), deviceIdentityProvider: clientIdentity(), onSignOut: signOut ?? () async {},
    loanRepository: loans ?? FakeClientLoanRepository(clientPortfolio()), scheduleRepository: schedules ?? FakeClientScheduleRepository(),
  ));
void main() {
  testWidgets('client_401_action_enters_session_recovery', (tester) async {
    var signedOut = 0;
    await open(tester, loans: FakeClientLoanRepository.failure(const SpinaApiException('expired', statusCode: 401)), signOut: () async { signedOut++; });
    await tester.pumpAndSettle();
    expect(find.text('Sign in again'), findsOneWidget);
    await tester.tap(find.text('Sign in again'));
    expect(signedOut, 1);
  });
  testWidgets('client_403_clears_affected_data', (tester) async {
    await open(tester, loans: FakeClientLoanRepository.failure(const SpinaApiException('denied', statusCode: 403)));
    await tester.pumpAndSettle();
    expect(find.text('Access unavailable'), findsOneWidget);
    expect(find.text('Retry'), findsNothing);
    expect(find.text('Official remaining balance'), findsNothing);
  });
  testWidgets('schedule_failure_keeps_other_loans_and_shows_retry', (tester) async {
    final schedules = ControlledSchedules();
    await open(tester, schedules: schedules);
    await tester.pumpAndSettle();
    expect(find.text('Official remaining balance'), findsNWidgets(2));
    expect(find.text('Schedule/payoff information unavailable'), findsOneWidget);
    expect(find.text('Exact payoff'), findsNothing);
    schedules.fail = false;
    await tester.tap(find.text('Retry schedule'));
    await tester.pumpAndSettle();
    expect(schedules.calls, ['seven-by-seven-loan', 'seven-by-seven-loan']);
    expect(find.text('Schedule/payoff information unavailable'), findsNothing);
  });
  testWidgets('verified portfolio renders before a deferred schedule', (tester) async {
    final schedules = ControlledSchedules()..defer = true;
    await open(tester, schedules: schedules);
    await tester.pump(); await tester.pump();
    expect(find.text('Official remaining balance'), findsNWidgets(2));
    expect(find.text('Loading schedule/payoff information'), findsOneWidget);
    schedules.pending.complete(await FakeClientScheduleRepository().loadSchedule(clientSession(), deviceId: 'device', loanId: 'seven-by-seven-loan'));
    await tester.pumpAndSettle();
  });
  testWidgets('old_read_cannot_overwrite_new_session', (tester) async {
    final old = ControlledPortfolio();
    await open(tester, loans: old); await tester.pump();
    await open(tester, loans: FakeClientLoanRepository.failure(const SpinaApiException('denied', statusCode: 403)));
    await tester.pumpAndSettle();
    old.pending.complete(clientPortfolio());
    await tester.pumpAndSettle();
    expect(find.text('Official remaining balance'), findsNothing);
    expect(find.text('Access unavailable'), findsOneWidget);
  });
}
