import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collector_failure_guidance.dart';
import 'package:gilbic_mobile/src/features/collector/collector_master_review_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_page.dart';
import 'package:gilbic_mobile/src/features/shared/daily_workspace_widgets.dart';
import 'support/android_role_fixture.dart';

void main() {
  for (final master in [false, true]) {
    final surface = master ? 'Master Review' : 'Daily Route';
    for (final status in [401, 403, 426]) {
      testWidgets(
        '$surface $status clears private facts and blocks retained read callbacks',
        (tester) async {
          final loader = _ControlledRoute();
          await _open(tester, master: master, loader: loader);
          await tester.pumpAndSettle();
          expect(
            find.textContaining('Private Synthetic Borrower'),
            findsWidgets,
          );
          final refresh = tester
              .widget<IconButton>(_refreshButton(master))
              .onPressed!;
          final pull = tester
              .widget<RefreshIndicator>(find.byType(RefreshIndicator))
              .onRefresh;
          loader.error = SpinaApiException(
            'column private_secret',
            statusCode: status,
          );
          refresh();
          await tester.pumpAndSettle();
          expect(
            find.textContaining('Private Synthetic Borrower'),
            findsNothing,
          );
          expect(find.textContaining('private_secret'), findsNothing);
          expect(find.text('Try again'), findsNothing);
          expect(find.text('Retry'), findsNothing);
          expect(
            find.widgetWithText(OutlinedButton, 'Sign in again'),
            findsNothing,
          );
          final notice = tester.widget<WorkspaceReadNotice>(
            find.byType(WorkspaceReadNotice),
          );
          expect(notice.onAction, isNull);
          expect(find.widgetWithText(OutlinedButton, 'Back'), findsNothing);
          refresh();
          await pull();
          await tester.pumpAndSettle();
          expect(
            loader.calls,
            2,
            reason:
                'Denial cannot be retried through retained same-session callbacks.',
          );
          expect(
            tester.widget<IconButton>(_refreshButton(master)).onPressed,
            isNull,
          );
        },
      );
    }

    testWidgets(
      '$surface transient refresh is safe stale information and deduplicates reads',
      (tester) async {
        final loader = _ControlledRoute();
        await _open(tester, master: master, loader: loader);
        await tester.pumpAndSettle();
        final refresh = tester
            .widget<IconButton>(_refreshButton(master))
            .onPressed!;
        final pull = tester
            .widget<RefreshIndicator>(find.byType(RefreshIndicator))
            .onRefresh;
        loader.pending = Completer<CollectorRouteLoadResult>();
        refresh();
        refresh();
        unawaited(pull());
        await tester.pump();
        expect(loader.calls, 2);
        loader.pending!.completeError(
          const SpinaApiException('column private_secret', statusCode: 503),
        );
        await tester.pumpAndSettle();
        expect(find.textContaining('Private Synthetic Borrower'), findsWidgets);
        expect(find.textContaining('private_secret'), findsNothing);
        expect(find.textContaining('has not been refreshed'), findsOneWidget);
      },
    );

    testWidgets('$surface disposed read cannot restore private facts', (
      tester,
    ) async {
      final loader = _ControlledRoute()
        ..pending = Completer<CollectorRouteLoadResult>();
      await _open(tester, master: master, loader: loader);
      await tester.pump();
      await tester.pumpWidget(const MaterialApp(home: Text('Different scope')));
      loader.pending!.complete(_route());
      await tester.pumpAndSettle();
      expect(find.text('Different scope'), findsOneWidget);
      expect(find.textContaining('Private Synthetic Borrower'), findsNothing);
      expect(tester.takeException(), isNull);
    });

    for (final status in [401, 403, 426]) {
      testWidgets(
        '$surface root $status invokes supplied session recovery only on explicit action',
        (tester) async {
          var signOuts = 0;
          final loader = _ControlledRoute()
            ..error = SpinaApiException('private_secret', statusCode: status);
          await _open(
            tester,
            master: master,
            loader: loader,
            onSignOut: () async {
              signOuts++;
            },
          );
          await tester.pumpAndSettle();
          expect(signOuts, 0);
          expect(loader.calls, 1);
          await tester.tap(
            find.widgetWithText(
              OutlinedButton,
              status == 401 ? 'Sign in again' : 'Return to sign-in',
            ),
          );
          await tester.pump();
          expect(signOuts, 1);
          expect(loader.calls, 1);
        },
      );
    }

    for (final status in [403, 426]) {
      testWidgets(
        '$surface pushed $status can return Back without a supplied callback',
        (tester) async {
          final loader = _ControlledRoute()
            ..error = SpinaApiException('private_secret', statusCode: status);
          await _open(tester, master: master, loader: loader, pushed: true);
          await tester.pumpAndSettle();
          final notice = tester.widget<WorkspaceReadNotice>(
            find.byType(WorkspaceReadNotice),
          );
          expect(notice.actionLabel, 'Back');
          expect(notice.onAction, isNotNull);
          await tester.tap(find.widgetWithText(OutlinedButton, 'Back'));
          await tester.pumpAndSettle();
          expect(find.text('Safe prior context'), findsOneWidget);
          expect(loader.calls, 1);
        },
      );
    }
  }

  for (final status in [400, 404, 422, 426, 500]) {
    test('Collector read $status suppresses unclassified backend text', () {
      final error = SpinaApiException(
        'column private_secret',
        statusCode: status,
      );
      expect(
        collectorReadFailureMessage(error),
        isNot(contains('private_secret')),
      );
      if (status == 426) {
        expect(collectorReadFailureMessage(error), contains('update'));
      }
    });
  }
  test('Collector known stale-route guidance is retained', () {
    const error = SpinaApiException(
      'Internal route revision conflict.',
      statusCode: 409,
      code: 'route_revision_changed',
    );
    expect(
      collectorReadFailureMessage(error),
      collectorFailureMessage(error, task: CollectorFailureTask.loadRoute),
    );
  });

  testWidgets(
    'route read refresh preserves exact uncertain payment and denial cannot resubmit it',
    (tester) async {
      final loader = _ControlledRoute();
      final payments = _UncertainPayment();
      await _open(tester, master: false, loader: loader, payments: payments);
      await tester.pumpAndSettle();
      final payFinder = find.byKey(const Key('record-collection-entry-a'));
      await tester.tap(payFinder);
      await tester.pumpAndSettle();
      expect(payments.drafts, hasLength(1));
      final original = payments.drafts.single.toJson();
      loader.error = const SpinaApiException(
        'network unavailable',
        statusCode: 503,
      );
      tester.widget<IconButton>(_refreshButton(false)).onPressed!();
      await tester.pumpAndSettle();
      expect(
        payments.drafts,
        hasLength(1),
        reason: 'Read retry never retries a financial command.',
      );
      final exactRetry = tester.widget<FilledButton>(payFinder).onPressed!;
      await tester.ensureVisible(payFinder);
      await tester.tap(payFinder);
      await tester.pumpAndSettle();
      expect(payments.drafts, hasLength(2));
      expect(identical(payments.drafts[0], payments.drafts[1]), isTrue);
      expect(payments.drafts[1].toJson(), original);
      loader.error = const SpinaApiException('device revoked', statusCode: 403);
      tester.widget<IconButton>(_refreshButton(false)).onPressed!();
      await tester.pumpAndSettle();
      expect(find.textContaining('Private Synthetic Borrower'), findsNothing);
      exactRetry();
      await tester.pumpAndSettle();
      expect(payments.drafts, hasLength(2));
      expect(payments.drafts[0].toJson(), original);
    },
  );

  testWidgets(
    'late confirmed payment after read denial cannot reveal private receipt or reload',
    (tester) async {
      final loader = _ControlledRoute();
      final payments = _DeferredPayment();
      await _open(tester, master: false, loader: loader, payments: payments);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('record-collection-entry-a')));
      await tester.pump();
      await tester.pump();
      loader.error = const SpinaApiException('device revoked', statusCode: 403);
      tester.widget<IconButton>(_refreshButton(false)).onPressed!();
      await tester.pump();
      payments.pending.complete(payments.accepted());
      await tester.pumpAndSettle();
      expect(find.textContaining('PRIVATE-RECEIPT'), findsNothing);
      expect(find.textContaining('Private Synthetic Borrower'), findsNothing);
      expect(loader.calls, 2);
      expect(payments.drafts, hasLength(1));
    },
  );

  testWidgets('confirmed payment readback supersedes a pre-payment read', (
    tester,
  ) async {
    final loader = _ControlledRoute();
    final payments = _DeferredPayment();
    await _open(tester, master: false, loader: loader, payments: payments);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('record-collection-entry-a')));
    await tester.pump();
    await tester.pump();
    final oldRead = Completer<CollectorRouteLoadResult>();
    loader.pending = oldRead;
    tester.widget<IconButton>(_refreshButton(false)).onPressed!();
    await tester.pump();
    loader.pending = null;
    loader.result = _route(borrower: 'Verified after payment');
    payments.pending.complete(payments.accepted());
    await tester.pump();
    await tester.pump();
    expect(loader.calls, 3);
    expect(find.textContaining('Verified after payment'), findsOneWidget);
    oldRead.complete(_route());
    await tester.pumpAndSettle();
    expect(find.textContaining('Verified after payment'), findsOneWidget);
    expect(find.textContaining('Private Synthetic Borrower'), findsNothing);
    expect(payments.drafts, hasLength(1));
  });

  testWidgets(
    'read denial clears the already-open private Client Tools sheet',
    (tester) async {
      final loader = _ControlledRoute();
      await _open(tester, master: false, loader: loader);
      await tester.pumpAndSettle();
      loader.pending = Completer<CollectorRouteLoadResult>();
      tester.widget<IconButton>(_refreshButton(false)).onPressed!();
      await tester.pump();
      await tester.tap(find.byKey(const Key('route-client-client-a')));
      await tester.pumpAndSettle();
      expect(find.text('Client Tools'), findsOneWidget);
      loader.pending!.completeError(
        const SpinaApiException('device revoked', statusCode: 403),
      );
      await tester.pumpAndSettle();
      expect(find.text('Client Tools'), findsNothing);
      expect(find.textContaining('Private Synthetic Borrower'), findsNothing);
      expect(find.text('Access unavailable'), findsOneWidget);
      expect(
        tester
            .widget<WorkspaceReadNotice>(find.byType(WorkspaceReadNotice))
            .onAction,
        isNull,
      );
      expect(loader.calls, 2);
    },
  );
}

Finder _refreshButton(bool master) => find.byWidgetPredicate(
  (widget) =>
      widget is IconButton &&
      widget.tooltip == (master ? 'Refresh review' : 'Refresh route'),
);

const _session = UserSession(
  userId: 'collector-a',
  username: 'synthetic',
  displayName: 'Synthetic Collector',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'synthetic-token',
  permissions: ['collection.create'],
);

Future<void> _open(
  WidgetTester tester, {
  required bool master,
  required CollectorRouteLoader loader,
  Future<void> Function()? onSignOut,
  PaymentSubmissionRepository? payments,
  bool pushed = false,
}) async {
  final page = master
      ? CollectorMasterReviewPage(
          session: _session,
          loader: loader,
          onSignOut: onSignOut,
        )
      : CollectorRoutePage(
          session: _session,
          loader: loader,
          onSignOut: onSignOut,
          paymentRepository: payments,
          deviceIdentityProvider: DeviceIdentityProvider(
            store: MemoryDeviceIdentityStore()..value = 'synthetic-device',
            platformResolver: () => 'android',
            appVersionResolver: () async => 'test',
          ),
          deviceSequence: MemoryCollectionDeviceSequence(),
        );
  await pumpAndroidRoleFixture(
    tester,
    size: const Size(412, 915),
    textScaler: TextScaler.linear(1),
    home: pushed
        ? Scaffold(
            body: Builder(
              builder: (context) => TextButton(
                onPressed: () => Navigator.of(
                  context,
                ).push(MaterialPageRoute<void>(builder: (_) => page)),
                child: const Text('Safe prior context'),
              ),
            ),
          )
        : page,
  );
  if (pushed) {
    await tester.tap(find.text('Safe prior context'));
    await tester.pump();
  }
}

CollectorRouteLoadResult _route({
  String borrower = 'Private Synthetic Borrower',
}) => CollectorRouteLoadResult(
  route: CollectorRoute(
    routeDate: DateTime(2026, 10, 3),
    collectorName: 'Synthetic Collector',
    areas: const ['Synthetic Area'],
    expectedTotal: 100,
    entries: [
      CollectorRouteEntry(
        id: 'entry-a',
        clientId: 'client-a',
        loanId: 'loan-a',
        clientName: borrower,
        area: 'Synthetic Area',
        loanType: 'Regular',
        dailyAmount: 100,
        balance: 1000,
        status: 'Pending',
        passCount: 0,
        routeRevision: 'exact-loan-v7',
      ),
    ],
  ),
  syncedAt: DateTime.utc(2026, 10, 3),
  isFromCache: false,
);

class _ControlledRoute implements CollectorRouteLoader {
  int calls = 0;
  Object? error;
  Completer<CollectorRouteLoadResult>? pending;
  CollectorRouteLoadResult? result;
  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async {
    calls++;
    if (pending != null) return pending!.future;
    if (error != null) throw error!;
    return result ?? _route();
  }
}

class _UncertainPayment implements PaymentSubmissionRepository {
  final drafts = <PaymentSubmissionDraft>[];
  @override
  Future<PaymentSubmissionResult> submit(
    UserSession session,
    PaymentSubmissionDraft draft,
  ) async {
    drafts.add(draft);
    throw const SpinaApiException('unknown payment result', statusCode: 503);
  }
}

class _DeferredPayment implements PaymentSubmissionRepository {
  final drafts = <PaymentSubmissionDraft>[];
  final pending = Completer<PaymentSubmissionResult>();
  @override
  Future<PaymentSubmissionResult> submit(
    UserSession session,
    PaymentSubmissionDraft draft,
  ) {
    drafts.add(draft);
    return pending.future;
  }

  PaymentSubmissionResult accepted() => PaymentSubmissionResult(
    disposition: PaymentSubmissionDisposition.accepted,
    idempotencyKey: drafts.single.idempotencyKey,
    message: 'Payment saved.',
    receiptNumber: 'PRIVATE-RECEIPT',
    officialBalance: 900,
  );
}
