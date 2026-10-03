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

class _Portfolio implements ClientLoanRepository {
  int calls = 0;
  int? failure;
  Completer<ClientLoanPortfolio>? pending;

  @override
  Future<ClientLoanPortfolio> loadPortfolio(
    UserSession session, {
    required String deviceId,
  }) async {
    calls++;
    if (failure != null) {
      throw SpinaApiException('private_failure_detail', statusCode: failure);
    }
    return pending == null ? clientPortfolio() : pending!.future;
  }
}

class _DeniedSchedule implements ClientScheduleRepository {
  _DeniedSchedule(this.status);
  final int status;

  @override
  Future<ClientLoanSchedule> loadSchedule(
    UserSession session, {
    required String deviceId,
    required String loanId,
  }) => Future.error(
    SpinaApiException('private_schedule_detail', statusCode: status),
  );
}

Future<void> _open(
  WidgetTester tester,
  _Portfolio repository, {
  ClientScheduleRepository? schedules,
  Future<void> Function()? signOut,
}) => pumpAndroidRoleFixture(
  tester,
  size: const Size(412, 915),
  textScaler: TextScaler.linear(1),
  home: ClientDashboard(
    session: clientSession(),
    onSignOut: signOut ?? () async {},
    deviceIdentityProvider: clientIdentity(),
    loanRepository: repository,
    scheduleRepository: schedules ?? FakeClientScheduleRepository(),
  ),
);

void main() {
  testWidgets('Client new authorized binding can recover after denied read', (
    tester,
  ) async {
    await _open(tester, _Portfolio()..failure = 403);
    await tester.pumpAndSettle();
    expect(find.text('Access unavailable'), findsOneWidget);
    final replacement = _Portfolio();
    await _open(tester, replacement);
    await tester.pumpAndSettle();
    expect(replacement.calls, 1);
    expect(find.text('Access unavailable'), findsNothing);
    expect(find.text('Official remaining balance'), findsNWidgets(2));
  });

  testWidgets('Client retained refresh callback is inert after disposal', (
    tester,
  ) async {
    final repository = _Portfolio();
    await _open(tester, repository);
    await tester.pumpAndSettle();
    final refresh = tester
        .widget<RefreshIndicator>(find.byType(RefreshIndicator))
        .onRefresh;
    await tester.pumpWidget(const SizedBox());
    await refresh();
    await tester.pump();
    expect(repository.calls, 1);
    expect(tester.takeException(), isNull);
  });

  for (final status in [401, 403, 426]) {
    for (final nested in [false, true]) {
      testWidgets(
        'Client $status ${nested ? 'schedule' : 'portfolio'} denial blocks refresh gestures and retained callbacks',
        (tester) async {
          final repository = _Portfolio();
          var signOuts = 0;
          await _open(
            tester,
            repository,
            schedules: nested ? _DeniedSchedule(status) : null,
            signOut: () async => signOuts++,
          );
          await tester.pumpAndSettle();
          final refresh = tester
              .widget<RefreshIndicator>(find.byType(RefreshIndicator))
              .onRefresh;
          if (!nested) {
            expect(find.text('Official remaining balance'), findsNWidgets(2));
            repository.failure = status;
            await refresh();
            await tester.pumpAndSettle();
          }
          final callsBefore = repository.calls;
          expect(find.text('Official remaining balance'), findsNothing);
          expect(find.textContaining('private_'), findsNothing);
          expect(signOuts, 0);
          await tester.drag(
            find.byKey(const Key('client-dashboard-list')),
            const Offset(0, 400),
          );
          await tester.pumpAndSettle();
          await refresh();
          await refresh();
          await tester.pumpAndSettle();
          expect(repository.calls, callsBefore);
          expect(signOuts, 0);
          if (status != 403) {
            await tester.tap(
              find.text(status == 401 ? 'Sign in again' : 'Return to sign-in'),
            );
            expect(signOuts, 1);
          } else {
            expect(find.text('Access unavailable'), findsOneWidget);
            expect(find.text('Retry'), findsNothing);
          }
        },
      );
    }
  }

  testWidgets('Client refresh deduplicates an already pending portfolio read', (
    tester,
  ) async {
    final pending = Completer<ClientLoanPortfolio>();
    final repository = _Portfolio()..pending = pending;
    await _open(tester, repository);
    await tester.pump();
    final refresh = tester
        .widget<RefreshIndicator>(find.byType(RefreshIndicator))
        .onRefresh;
    unawaited(refresh());
    unawaited(refresh());
    await tester.pump();
    expect(repository.calls, 1);
    pending.complete(clientPortfolio());
    await tester.pumpAndSettle();
    expect(find.text('Official remaining balance'), findsNWidgets(2));
    expect(tester.takeException(), isNull);
  });

  testWidgets('Client transient refresh retains stale facts and can recover', (
    tester,
  ) async {
    final repository = _Portfolio();
    await _open(tester, repository);
    await tester.pumpAndSettle();
    repository.failure = 503;
    await tester
        .widget<RefreshIndicator>(find.byType(RefreshIndicator))
        .onRefresh();
    await tester.pumpAndSettle();
    expect(find.text('Official remaining balance'), findsNWidgets(2));
    expect(find.textContaining('last successful information'), findsOneWidget);
    expect(find.textContaining('private_'), findsNothing);
    repository.failure = null;
    await tester.ensureVisible(find.text('Retry'));
    await tester.tap(find.text('Retry'));
    await tester.pumpAndSettle();
    expect(repository.calls, 3);
    expect(find.textContaining('last successful information'), findsNothing);
    expect(find.text('Official remaining balance'), findsNWidgets(2));
  });
}
