import 'dart:async';
import 'dart:collection';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan_repository.dart';
import 'package:gilbic_mobile/src/core/loans/client_schedule.dart';
import 'package:gilbic_mobile/src/core/loans/client_schedule_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/client_payment.dart';
import 'package:gilbic_mobile/src/core/payments/client_payment_repository.dart';
import 'package:gilbic_mobile/src/core/statements/client_statement.dart';
import 'package:gilbic_mobile/src/core/statements/client_statement_repository.dart';
import 'package:gilbic_mobile/src/features/client/client_loans_page.dart';
import 'package:gilbic_mobile/src/features/client/client_payments_page.dart';
import 'package:gilbic_mobile/src/features/client/client_schedule_page.dart';
import 'package:gilbic_mobile/src/features/client/client_statement_page.dart';

void main() {
  for (final page in _Page.values) {
    for (final status in [401, 403, 426]) {
      testWidgets('${page.name}: denied refresh $status clears private data', (
        tester,
      ) async {
        final harness = await _show(tester, page);
        harness.repository.next.add(() async {
          throw SpinaApiException('Access revoked', statusCode: status);
        });
        await _refresh(tester);
        await tester.pumpAndSettle();

        expect(_alice, findsNothing);
        expect(find.byType(RefreshIndicator), findsNothing);
        expect(find.text('Access revoked'), findsOneWidget);
        expect(find.text('Try again'), findsOneWidget);
        // Only a fresh successful read can restore the private controls.
        await tester.tap(find.text('Try again'));
        await tester.pumpAndSettle();
        expect(_alice, findsWidgets);
      });
    }

    for (final failure in <Object>[
      const SpinaApiException('Offline', code: 'network_unavailable'),
      const SpinaApiException('Server unavailable', statusCode: 503),
      TimeoutException('Connection timeout'),
    ]) {
      testWidgets('${page.name}: $failure retains previously allowed data', (
        tester,
      ) async {
        final harness = await _show(tester, page);
        harness.repository.next.add(() async => throw failure);
        await _refresh(tester);
        await tester.pumpAndSettle();
        expect(_alice, findsWidgets);
        expect(find.byType(RefreshIndicator), findsOneWidget);
      });
    }

    for (final denialFirst in [false, true]) {
      testWidgets(
        '${page.name}: denial invalidates overlapping reads (denial first: $denialFirst)',
        (tester) async {
          final harness = await _show(tester, page);
          final success = Completer<void>();
          final denied = Completer<void>();
          harness.repository.next.addAll([
            () => denialFirst ? denied.future : success.future,
            () => denialFirst ? success.future : denied.future,
          ]);
          final first = _refresh(tester);
          await tester.pump();
          final second = _refresh(tester);
          await tester.pump();
          denied.completeError(
            const SpinaApiException('Access revoked', statusCode: 403),
          );
          await (denialFirst ? first : second);
          await tester.pump();
          expect(_alice, findsNothing);
          success.complete();
          await Future.wait([first, second]);
          await tester.pumpAndSettle();
          expect(_alice, findsNothing);
          expect(find.text('Access revoked'), findsOneWidget);
        },
      );
    }

    for (final sameUser in [false, true]) {
      testWidgets(
        '${page.name}: session change clears data and ignores the old response (same user: $sameUser)',
        (tester) async {
          final harness = await _show(tester, page);
          final oldRead = Completer<void>();
          final newRead = Completer<void>();
          harness.repository.next.addAll([
            () => oldRead.future,
            () => newRead.future,
          ]);
          final refreshing = _refresh(tester);
          await tester.pump();
          harness.session.value = _session(
            sameUser ? 'alice' : 'bob',
            token: 'new-token',
          );
          await tester.pump();
          expect(_alice, findsNothing);
          oldRead.complete();
          await refreshing;
          await tester.pump();
          expect(_alice, findsNothing);
          newRead.complete();
          await tester.pumpAndSettle();
          expect(
            find.textContaining(sameUser ? 'private-alice' : 'private-bob'),
            findsWidgets,
          );
          if (!sameUser) expect(_alice, findsNothing);
        },
      );
    }

    for (final sessionChange in [false, true]) {
      testWidgets(
        '${page.name}: ${sessionChange ? 'session change' : 'denial'} removes nested private routes only',
        (tester) async {
          final harness = _Harness(page);
          final navigator = GlobalKey<NavigatorState>();
          await tester.pumpWidget(
            MaterialApp(
              navigatorKey: navigator,
              home: const Scaffold(body: Text('Public root')),
            ),
          );
          unawaited(
            navigator.currentState!.push(
              MaterialPageRoute<void>(builder: (_) => harness.widget),
            ),
          );
          await tester.pumpAndSettle();
          final pending = Completer<void>();
          harness.repository.next.add(() => pending.future);
          final refreshing = _refresh(tester);
          await tester.pump();
          unawaited(
            navigator.currentState!.push(
              MaterialPageRoute<void>(
                builder: (_) => const Scaffold(body: Text('Private child')),
              ),
            ),
          );
          await tester.pumpAndSettle();
          expect(find.text('Private child'), findsOneWidget);
          if (sessionChange) {
            harness.session.value = _session('bob');
            await tester.pump();
            pending.complete();
          } else {
            pending.completeError(
              const SpinaApiException('Access revoked', statusCode: 403),
            );
          }
          await refreshing;
          await tester.pumpAndSettle();
          expect(find.text('Private child', skipOffstage: false), findsNothing);
          expect(_alice, findsNothing);
          expect(navigator.currentState!.canPop(), isTrue);
          navigator.currentState!.pop();
          await tester.pumpAndSettle();
          expect(find.text('Public root'), findsOneWidget);
        },
      );
    }
  }
}

final _alice = find.textContaining('private-alice', skipOffstage: false);

Future<void> _refresh(WidgetTester tester) =>
    tester.widget<RefreshIndicator>(find.byType(RefreshIndicator)).onRefresh();

Future<_Harness> _show(WidgetTester tester, _Page page) async {
  await tester.binding.setSurfaceSize(const Size(1100, 2400));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  final harness = _Harness(page);
  await tester.pumpWidget(MaterialApp(home: harness.widget));
  await tester.pumpAndSettle();
  expect(_alice, findsWidgets);
  return harness;
}

UserSession _session(String user, {String? token}) => UserSession(
  userId: user,
  username: user,
  displayName: user,
  role: AppRole.client,
  rawRole: 'Client',
  accessToken: token ?? '$user-token',
);

enum _Page { payments, loans, statement, schedule }

class _Harness {
  _Harness(this.page);
  final _Page page;
  final repository = _Repository();
  final session = ValueNotifier(_session('alice'));
  final identity = DeviceIdentityProvider(
    store: MemoryDeviceIdentityStore()..value = 'client-device',
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );

  Widget get widget => ValueListenableBuilder<UserSession>(
    valueListenable: session,
    builder: (_, current, _) => switch (page) {
      _Page.payments => ClientPaymentsPage(
        session: current,
        deviceIdentityProvider: identity,
        repository: repository,
      ),
      _Page.loans => ClientLoansPage(
        session: current,
        deviceIdentityProvider: identity,
        repository: repository,
        scheduleRepository: repository,
      ),
      _Page.statement => ClientStatementPage(
        session: current,
        deviceIdentityProvider: identity,
        repository: repository,
      ),
      _Page.schedule => ClientSchedulePage(
        session: current,
        deviceIdentityProvider: identity,
        repository: repository,
        loanId: 'loan-1',
        loanNumber: 'loan-1',
      ),
    },
  );
}

// Replace only the external read. Widgets, refresh callbacks and Navigator are real.
class _Repository
    implements
        ClientPaymentRepository,
        ClientLoanRepository,
        ClientStatementRepository,
        ClientScheduleRepository {
  final next = Queue<Future<void> Function()>();

  Future<void> _read() async {
    if (next.isNotEmpty) await next.removeFirst()();
  }

  @override
  Future<ClientPaymentTimeline> loadTimeline(
    UserSession session, {
    required String deviceId,
  }) async {
    await _read();
    return ClientPaymentTimeline(
      clientId: session.userId,
      clientCode: 'private-${session.userId}-code',
      clientName: 'private-${session.userId}',
      proofUploadAvailable: false,
      proofMessage: 'Official receipts only',
      payments: [
        ClientPayment(
          transactionId: 'payment-1',
          receiptNumber: 'private-${session.userId}-receipt',
          loanId: 'loan-1',
          loanNumber: 'private-${session.userId}-loan',
          loanTypeName: 'Regular',
          collectorName: 'Collector',
          collectionDate: DateTime(2026, 8, 6),
          recordedAt: DateTime.utc(2026, 8, 6),
          entryType: 'payment',
          amount: '50.00',
          coveredDates: const [],
          officialBalance: '4950.00',
          status: 'posted',
          isVoided: false,
          editVersion: 0,
        ),
      ],
    );
  }

  @override
  Future<ClientLoanPortfolio> loadPortfolio(
    UserSession session, {
    required String deviceId,
  }) async {
    await _read();
    return ClientLoanPortfolio(
      clientId: session.userId,
      clientCode: 'private-${session.userId}-code',
      clientName: 'private-${session.userId}',
      clientStatus: 'active',
      loans: [
        ClientLoan(
          loanId: 'loan-1',
          loanNumber: 'private-${session.userId}-loan',
          loanTypeName: 'Regular',
          principal: '5000.00',
          dailyAmount: '50.00',
          status: 'active',
          remainingBalance: '4950.00',
          paidAmount: '50.00',
          passCount: 0,
          stateVersion: 1,
          paymentCount: 1,
        ),
      ],
    );
  }

  @override
  Future<ClientStatement> loadStatement(
    UserSession session, {
    required String deviceId,
  }) async {
    await _read();
    return ClientStatement(
      clientCode: 'private-${session.userId}-code',
      clientName: 'private-${session.userId}',
      loans: const [],
      payments: [
        ClientStatementPayment(
          receiptNumber: 'private-${session.userId}-receipt',
          loanNumber: 'private-${session.userId}-loan',
          collectionDate: DateTime(2026, 8, 6),
          amount: '50.00',
          status: 'posted',
          isVoided: false,
        ),
      ],
    );
  }

  @override
  Future<ClientLoanSchedule> loadSchedule(
    UserSession session, {
    required String deviceId,
    required String loanId,
  }) async {
    await _read();
    return ClientLoanSchedule(
      loanId: loanId,
      loanNumber: 'private-${session.userId}-loan',
      loanType: 'Regular',
      calculationMode: 'fixed_total',
      isSevenBySeven: false,
      paymentFrequency: 'daily',
      readOnly: true,
      pastDueAmount: '0.00',
      pastDueCount: 0,
      scheduleExtensionSlots: 0,
      maturityStatus: 'current',
      penaltyStatus: 'not_applicable',
      projectedPenalty: '0.00',
      assessedPenaltyBalance: '0.00',
      penaltyBase: '0.00',
      remainingCostHeadroom: '0.00',
      exactPayoffTotal: '4950.00',
      managementReviewRequiredReason: '',
      rows: const [],
    );
  }
}
