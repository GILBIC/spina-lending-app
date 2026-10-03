import 'support/android_workflow_capture.dart';
import 'support/android_role_fixture.dart';
import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:gilbic_mobile/src/app.dart';
import 'package:gilbic_mobile/src/core/auth/auth_repository.dart';
import 'package:gilbic_mobile/src/core/auth/session_store.dart';
import 'package:gilbic_mobile/src/core/employee_operations/attendance_outbox.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_operations_service.dart';
import 'support/app_platform_dependencies.dart';
import 'package:gilbic_mobile/src/core/media/image_recovery_controller.dart';
import 'package:gilbic_mobile/src/core/mirror/mirror_controller.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow.dart';
import 'package:gilbic_mobile/src/features/collector/collector_cash_status_card.dart';
import 'package:gilbic_mobile/src/features/collector/collector_renewal_cash_release_page.dart';
import 'package:image_picker/image_picker.dart';
import 'mirror_controller_test.dart' show FakeMirrorRepository;
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/combined_payment_submission.dart';
import 'package:gilbic_mobile/src/core/payments/combined_payment_submission_repository.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_page.dart';
import 'package:gilbic_mobile/src/features/collector/collection_entry_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_field_home_page.dart';
import 'package:gilbic_mobile/src/features/dashboard/enhanced_role_dashboard.dart';

void main() {
  testWidgets(
    'A9 authorization cover blocks late route autofocus traversal and activation during classification',
    (tester) async {
      final identity = _A9Identity(MemoryDeviceIdentityStore());
      final images = testAppImageRecovery();
      final payments = _RetryRepository();
      await _pumpA9DirectApp(
        tester,
        _GrantRefreshAuth(),
        identity: identity,
        images: images,
        payments: payments,
      );
      final root = tester.state(find.byType(CollectorRoutePage));
      final navigator = tester.state<NavigatorState>(find.byType(Navigator));
      await tester.tap(find.byKey(const Key('record-collection-entry-1')));
      await tester.pumpAndSettle();
      final original = payments.drafts.single.toJson();
      final fieldFocus = FocusNode();
      final actionFocus = FocusNode();
      addTearDown(fieldFocus.dispose);
      addTearDown(actionFocus.dispose);
      var activations = 0;
      identity.delayed = Completer<DeviceIdentity>();
      final classification = identity.delayed!;
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      for (
        var frame = 0;
        frame < 12 && (!identity.held || images.ready);
        frame++
      ) {
        await tester.pump();
      }
      expect(identity.held, isTrue);
      expect(images.ready, isFalse);

      // A mounted-only async continuation can push above the guard before the
      // awaited installation lookup finishes. The app's cover must also block
      // this newly pushed route's keyboard access for the whole interval.
      unawaited(
        navigator.push<void>(
          MaterialPageRoute<void>(
            builder: (_) => Scaffold(
              body: Column(
                children: [
                  TextField(autofocus: true, focusNode: fieldFocus),
                  FilledButton(
                    focusNode: actionFocus,
                    onPressed: () => activations++,
                    child: const Text('Late private action'),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      final autofocusDuringCover = fieldFocus.hasFocus;
      final fieldEligibleDuringCover = fieldFocus.canRequestFocus;
      await tester.sendKeyEvent(LogicalKeyboardKey.tab);
      await tester.pump();
      final traversalDuringCover = actionFocus.hasFocus;
      await tester.sendKeyEvent(LogicalKeyboardKey.enter);
      await tester.pump();
      actionFocus.requestFocus();
      await tester.pump();
      final requestedFocusDuringCover = actionFocus.hasFocus;
      await tester.sendKeyEvent(LogicalKeyboardKey.enter);
      await tester.pump();
      final activationsDuringCover = activations;
      classification.complete(await identity.unheld());
      await tester.pumpAndSettle();

      expect(autofocusDuringCover, isFalse);
      expect(fieldEligibleDuringCover, isFalse);
      expect(traversalDuringCover, isFalse);
      expect(requestedFocusDuringCover, isFalse);
      expect(activationsDuringCover, 0);
      expect(find.text('Late private action'), findsNothing);
      expect(
        identical(root, tester.state(find.byType(CollectorRoutePage))),
        isTrue,
      );
      expect(find.text('Retry'), findsOneWidget);
      expect(payments.drafts, hasLength(1));
      expect(payments.drafts.single.toJson(), original);
      expect(images.ready, isTrue);
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets(
    'A9 blocked combined Retry amount uses readable disabled foreground',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(800, 1200));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final loader = _MutableAttemptRoute(combined: true);
      await tester.pumpWidget(
        MaterialApp(
          theme: SpinaTheme.light,
          home: CollectorRoutePage(
            session: _session,
            loader: loader,
            combinedPaymentRepository: _RetryCombinedRepository(),
            deviceIdentityProvider: _deviceIdentityProvider(),
            deviceSequence: MemoryCollectionDeviceSequence(),
          ),
        ),
      );
      await tester.pumpAndSettle();
      final action = find.byKey(const Key('record-client-client-combined'));
      await tester.tap(action);
      await tester.pumpAndSettle();
      loader.paid = true;
      loader.ready = false;
      await tester.tap(find.byTooltip('Refresh route'));
      await tester.pumpAndSettle();
      expect(tester.widget<FilledButton>(action).onPressed, isNull);
      final amount = find.descendant(of: action, matching: find.text('₱150'));
      expect(amount, findsOneWidget);
      expect(
        tester.widget<Text>(amount).style!.color,
        Theme.of(
          tester.element(action),
        ).colorScheme.onSurface.withValues(alpha: .38),
      );
    },
  );
  for (final combined in [false, true]) {
    for (final contractual in [false, true]) {
      testWidgets(
        'A9 paid readback retains ${combined ? 'combined' : 'direct'} exact Retry contract=$contractual',
        (tester) async {
          await tester.binding.setSurfaceSize(const Size(800, 1200));
          addTearDown(() => tester.binding.setSurfaceSize(null));
          final loader = _MutableAttemptRoute(combined: combined);
          final payments = _RetryRepository();
          final atomic = _RetryCombinedRepository();
          await tester.pumpWidget(
            MaterialApp(
              home: CollectorRoutePage(
                session: _session,
                loader: loader,
                paymentRepository: payments,
                combinedPaymentRepository: atomic,
                deviceIdentityProvider: _deviceIdentityProvider(),
                deviceSequence: MemoryCollectionDeviceSequence(),
              ),
            ),
          );
          await tester.pumpAndSettle();
          final key = Key(
            combined
                ? 'record-client-client-combined'
                : 'record-collection-entry-1',
          );
          await tester.tap(find.byKey(key));
          await tester.pumpAndSettle();
          expect(combined ? atomic.attempts.length : payments.drafts.length, 1);
          final original = combined
              ? atomic.attempts.single.toJson()
              : payments.drafts.single.toJson();
          loader.paid = true;
          loader.contractual = contractual;
          await tester.tap(find.byTooltip('Refresh route'));
          await tester.pumpAndSettle();
          expect(
            tester.widget<PopScope<void>>(find.byType(PopScope<void>)).canPop,
            isFalse,
          );
          expect(
            find.text('Retry'),
            findsOneWidget,
            reason: 'Uncorrelated paid route does not resolve a command',
          );
          await tester.tap(find.byKey(key));
          await tester.pumpAndSettle();
          expect(combined ? atomic.attempts.length : payments.drafts.length, 2);
          expect(
            combined
                ? atomic.attempts.last.toJson()
                : payments.drafts.last.toJson(),
            original,
          );
          if (combined) expect(atomic.previews, hasLength(1));
        },
      );
    }
    for (final inFlight in [false, true]) {
      testWidgets(
        'A9 same-client details blocked ${combined ? 'combined' : 'direct'} inFlight=$inFlight',
        (tester) async {
          await tester.binding.setSurfaceSize(const Size(800, 1200));
          addTearDown(() => tester.binding.setSurfaceSize(null));
          final payments = _DelayedDirectAttempt();
          final atomic = _DelayedCombinedAttempt();
          await tester.pumpWidget(
            MaterialApp(
              home: CollectorRoutePage(
                session: _session,
                loader: combined
                    ? _CombinedRouteLoader()
                    : _RouteLoader(isFromCache: false),
                paymentRepository: payments,
                combinedPaymentRepository: atomic,
                deviceIdentityProvider: _deviceIdentityProvider(),
                deviceSequence: MemoryCollectionDeviceSequence(),
              ),
            ),
          );
          await tester.pumpAndSettle();
          await tester.tap(
            find.byKey(
              Key(
                combined
                    ? 'record-client-client-combined'
                    : 'record-collection-entry-1',
              ),
            ),
          );
          await tester.pump();
          await tester.pump(const Duration(milliseconds: 300));
          if (!inFlight) {
            if (combined) {
              atomic.pending.completeError(
                const SpinaApiException(
                  'Uncertain',
                  code: 'network_unavailable',
                ),
              );
            } else {
              payments.pending.completeError(
                const SpinaApiException(
                  'Uncertain',
                  code: 'network_unavailable',
                ),
              );
            }
            await tester.pumpAndSettle();
          }
          await tester.tap(
            find.byKey(
              Key(
                combined
                    ? 'route-client-client-combined'
                    : 'route-client-client-1',
              ),
            ),
            warnIfMissed: false,
          );
          await tester.pump();
          await tester.pump(const Duration(milliseconds: 300));
          final tile = find.byKey(
            Key(
              combined
                  ? 'collection-details-regular-combined'
                  : 'collection-details-entry-1',
            ),
          );
          expect(tile, findsOneWidget);
          expect(
            tester.widget<ListTile>(tile).enabled,
            isFalse,
            reason: 'No fresh command while same client has unresolved attempt',
          );
          expect(tester.widget<ListTile>(tile).onTap, isNull);
          expect(find.byType(CollectionEntryPage), findsNothing);
          expect(
            combined ? atomic.submissions.length : payments.drafts.length,
            1,
          );
          if (inFlight) {
            if (combined) {
              atomic.pending.completeError(
                const SpinaApiException(
                  'Uncertain',
                  code: 'network_unavailable',
                ),
              );
            } else {
              payments.pending.completeError(
                const SpinaApiException(
                  'Uncertain',
                  code: 'network_unavailable',
                ),
              );
            }
            await tester.pumpAndSettle();
          }
        },
      );
    }
  }
  for (final combined in [false, true]) {
    testWidgets(
      'A9 refreshed grouping preserves retained ${combined ? 'combined' : 'direct'} command type',
      (tester) async {
        await tester.binding.setSurfaceSize(const Size(800, 1200));
        addTearDown(() => tester.binding.setSurfaceSize(null));
        final loader = _MutableAttemptRoute(combined: combined);
        final payments = _RetryRepository();
        final atomic = _RetryCombinedRepository();
        await tester.pumpWidget(
          MaterialApp(
            home: CollectorRoutePage(
              session: _session,
              loader: loader,
              paymentRepository: payments,
              combinedPaymentRepository: atomic,
              deviceIdentityProvider: _deviceIdentityProvider(),
              deviceSequence: MemoryCollectionDeviceSequence(),
            ),
          ),
        );
        await tester.pumpAndSettle();
        final key = Key(
          combined
              ? 'record-client-client-combined'
              : 'record-collection-entry-1',
        );
        await tester.tap(find.byKey(key));
        await tester.pumpAndSettle();
        final original = combined
            ? atomic.attempts.single.toJson()
            : payments.drafts.single.toJson();
        loader.changedGrouping = true;
        await tester.tap(find.byTooltip('Refresh route'));
        await tester.pumpAndSettle();
        expect(find.text('Retry'), findsOneWidget);
        await tester.tap(find.byKey(key));
        await tester.pumpAndSettle();
        expect(combined ? atomic.attempts.length : payments.drafts.length, 2);
        expect(
          combined
              ? atomic.attempts.last.toJson()
              : payments.drafts.last.toJson(),
          original,
        );
        expect(combined ? payments.drafts : atomic.attempts, isEmpty);
        expect(atomic.previews, hasLength(combined ? 1 : 0));
      },
    );
  }
  for (final combined in [false, true]) {
    for (final offstage in [false, true]) {
      testWidgets(
        'A9 actual app retains ${combined ? 'combined' : 'direct'} uncertainty across unrelated grant loss offstage=$offstage',
        (tester) async {
          await tester.binding.setSurfaceSize(const Size(800, 1200));
          addTearDown(() => tester.binding.setSurfaceSize(null));
          final auth = _GrantRefreshAuth();
          final store = MemorySessionStore();
          await store.write(auth.initial);
          final payments = _RetryRepository();
          final combinedWire = <Map<String, dynamic>>[];
          var previews = 0;
          final provider = _deviceIdentityProvider();
          final service = EmployeeOperationsService(
            deviceIdentityProvider: provider,
            outbox: AttendanceOutbox(MemoryAttendanceVault()),
          );
          addTearDown(service.dispose);
          final blockedClient = MockClient((request) async {
            expect(request.method, 'POST');
            if (request.url.path.endsWith('/combined/preview')) {
              previews++;
              return http.Response(
                jsonEncode({
                  'data': {
                    'status': 'exact',
                    'requires_review': false,
                    'allocation_hash': _allocationHash,
                    'cash_received_amount': '150.00',
                    'expected_total_amount': '150.00',
                    'short_amount': '0.00',
                    'extra_amount': '0.00',
                    'legs': [
                      for (final leg in _exactCombinedPreview.legs)
                        {
                          'loan_id': leg.loanId,
                          'loan_type': leg.loanType,
                          'scheduled_amount': leg.scheduledAmount,
                          'extra_amount': leg.extraAmount,
                          'total_amount': leg.totalAmount,
                        },
                    ],
                  },
                }),
                200,
              );
            }
            expect(request.url.path, endsWith('/combined'));
            combinedWire.add(jsonDecode(request.body) as Map<String, dynamic>);
            throw const SpinaApiException(
              'Synthetic uncertain response',
              code: 'network_unavailable',
            );
          });
          await http.runWithClient(() async {
            await tester.pumpWidget(
              GilbicApp(
                sessionStore: store,
                authRepository: auth,
                collectorRouteLoader: combined
                    ? _CombinedRouteLoader()
                    : _RouteLoader(isFromCache: false),
                paymentSubmissionRepository: payments,
                deviceIdentityProvider: provider,
                collectionDeviceSequence: MemoryCollectionDeviceSequence(),
                imageRecoveryController: testAppImageRecovery(),
                employeeOperationsService: service,
              ),
            );
            await tester.pumpAndSettle();
            final pay = find.byKey(
              Key(
                combined
                    ? 'record-client-client-combined'
                    : 'record-collection-entry-1',
              ),
            );
            await tester.ensureVisible(pay);
            await tester.tap(pay);
            await tester.pumpAndSettle();
            expect(combined ? combinedWire.length : payments.drafts.length, 1);
            final original = combined
                ? Map<String, dynamic>.of(combinedWire.single)
                : payments.drafts.single.toJson();
            if (offstage) {
              await tester.tap(find.text('Office & staff'));
              await tester.pumpAndSettle();
              expect(find.text('Employee Dashboard'), findsOneWidget);
            }
            final oldRouteState = tester.state(
              find.byType(CollectorRoutePage, skipOffstage: false),
            );
            final oldDashboard = tester.element(
              find.byType(EnhancedRoleDashboard),
            );
            tester.binding.handleAppLifecycleStateChanged(
              AppLifecycleState.inactive,
            );
            tester.binding.handleAppLifecycleStateChanged(
              AppLifecycleState.resumed,
            );
            await tester.pumpAndSettle();
            expect(auth.validations, 2);
            expect(
              identical(
                oldDashboard,
                tester.element(find.byType(EnhancedRoleDashboard)),
              ),
              isTrue,
            );
            expect(
              identical(
                oldRouteState,
                tester.state(
                  find.byType(CollectorRoutePage, skipOffstage: false),
                ),
              ),
              isTrue,
            );
            expect(find.text('Office & staff'), findsNothing);
            expect(
              find.text('Retry'),
              findsOneWidget,
              reason:
                  'Still-authorized Collector command must survive actual MaterialApp reset',
            );
            expect(
              combined ? combinedWire.length : payments.drafts.length,
              1,
              reason: 'Resume is not financial retry',
            );
            await tester.ensureVisible(pay);
            await tester.tap(pay);
            await tester.pumpAndSettle();
            expect(combined ? combinedWire.length : payments.drafts.length, 2);
            expect(
              combined ? combinedWire.last : payments.drafts.last.toJson(),
              original,
            );
            if (combined) expect(previews, 1);
            await tester.pumpWidget(const SizedBox());
            auth.initial.clearRefreshOverride();
          }, () => blockedClient);
        },
      );
    }
  }
  testWidgets(
    'A9 grant drain contains old dialog pops late pushes replacements and private alert queues',
    (tester) async {
      final auth = _GrantRefreshAuth();
      await _pumpA9DirectApp(tester, auth);
      final rootState = tester.state(find.byType(CollectorRoutePage));
      final navigator = tester.state<NavigatorState>(find.byType(Navigator));
      final messenger = tester.state<ScaffoldMessengerState>(
        find.byType(ScaffoldMessenger),
      );
      var disposed = 0;
      var continuations = 0;
      final private = MaterialPageRoute<void>(
        builder: (_) => _A9PrivateProbe(onDispose: () => disposed++),
      );
      unawaited(
        navigator.push<void>(private).then((_) {
          continuations++;
          navigator
              .pop(); // The page future resumes before its overlay unmounts.
          unawaited(
            navigator.pushReplacement<void, void>(
              MaterialPageRoute<void>(
                builder: (_) => const Scaffold(body: Text('stale replacement')),
              ),
            ),
          );
          unawaited(
            navigator.push<void>(
              DialogRoute<void>(
                context: navigator.context,
                builder: (_) =>
                    const AlertDialog(content: Text('stale late dialog')),
              ),
            ),
          );
          messenger.showSnackBar(
            const SnackBar(content: Text('stale queued snack')),
          );
          messenger.showMaterialBanner(
            MaterialBanner(
              content: const Text('stale queued banner'),
              actions: [
                TextButton(
                  onPressed: () {},
                  child: const Text('private action'),
                ),
              ],
            ),
          );
        }),
      );
      await tester.pumpAndSettle();
      unawaited(
        navigator.push<void>(
          DialogRoute<void>(
            context: navigator.context,
            builder: (_) =>
                const AlertDialog(content: Text('old private dialog')),
          ),
        ),
      );
      await tester.pump(
        const Duration(milliseconds: 30),
      ); // drain during dialog entrance
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pumpAndSettle();
      expect(continuations, 1);
      expect(disposed, 1);
      expect(
        identical(rootState, tester.state(find.byType(CollectorRoutePage))),
        isTrue,
      );
      for (final text in [
        'old private dialog',
        'private attendance probe',
        'stale replacement',
        'stale late dialog',
        'stale queued snack',
        'stale queued banner',
        'Updating access…',
      ]) {
        expect(find.text(text, skipOffstage: false), findsNothing);
      }
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets('A9 unchanged grants preserve authorized pushed route', (
    tester,
  ) async {
    final auth = _GrantRefreshAuth(keepGrants: true);
    await _pumpA9DirectApp(tester, auth);
    final navigator = tester.state<NavigatorState>(find.byType(Navigator));
    var disposed = false;
    unawaited(
      navigator.push<void>(
        MaterialPageRoute<void>(
          builder: (_) => _A9PrivateProbe(onDispose: () => disposed = true),
        ),
      ),
    );
    await tester.pumpAndSettle();
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pumpAndSettle();
    expect(auth.validations, 2);
    expect(disposed, isFalse);
    expect(find.text('private attendance probe'), findsOneWidget);
  });
  for (final refresh in [false, true]) {
    testWidgets(
      'A9 wrong-actor ${refresh ? 'refresh' : 'validation'} never persists foreign credentials and fails closed',
      (tester) async {
        final auth = _GrantRefreshAuth(
          refreshable: refresh,
          after: _a9Worker(
            userId: 'different-worker',
            permissions: ['route.view', 'collection.create'],
          ),
        );
        final store = _A9RecordingStore();
        final identity = _A9Identity(MemoryDeviceIdentityStore());
        await _pumpA9DirectApp(tester, auth, store: store, identity: identity);
        final root = tester.state(find.byType(CollectorRoutePage));
        var responseCalls = -1;
        auth.beforeReturn = () => responseCalls = identity.calls;
        if (refresh) {
          await tester.pump(const Duration(minutes: 1, seconds: 1));
        } else {
          tester.binding.handleAppLifecycleStateChanged(
            AppLifecycleState.inactive,
          );
          tester.binding.handleAppLifecycleStateChanged(
            AppLifecycleState.resumed,
          );
        }
        await tester.pumpAndSettle();
        expect(store.writes, isNot(contains('different-worker')));
        expect(await store.read(), isNull);
        expect(
          identity.calls,
          responseCalls,
          reason: 'No foreign actor device classification/binding',
        );
        expect(root.mounted, isFalse);
        expect(
          find.byType(EnhancedRoleDashboard, skipOffstage: false),
          findsNothing,
        );
        expect(find.text('Updating access…'), findsNothing);
        expect(find.text('Sign in'), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );
  }
  testWidgets(
    'A9 stale root replacement fails closed to new navigation ownership',
    (tester) async {
      final auth = _GrantRefreshAuth();
      await _pumpA9DirectApp(tester, auth);
      final root = tester.state(find.byType(CollectorRoutePage));
      final rootRoute = ModalRoute.of(
        tester.element(find.byType(CollectorRoutePage)),
      )!;
      final navigator = tester.state<NavigatorState>(find.byType(Navigator));
      unawaited(
        navigator
            .push<void>(
              MaterialPageRoute<void>(
                builder: (_) =>
                    const Scaffold(body: Text('private replacing page')),
              ),
            )
            .then((_) {
              navigator.replace(
                oldRoute: rootRoute,
                newRoute: MaterialPageRoute<void>(
                  builder: (_) =>
                      const Scaffold(body: Text('stale replaced root')),
                ),
              );
            }),
      );
      await tester.pumpAndSettle();
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pumpAndSettle();
      expect(root.mounted, isFalse);
      expect(
        identical(
          navigator,
          tester.state<NavigatorState>(find.byType(Navigator)),
        ),
        isFalse,
      );
      expect(
        find.text('stale replaced root', skipOffstage: false),
        findsNothing,
      );
      expect(find.text('Office & staff'), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );
  for (final reset in [
    'collector-loss',
    'installation',
    'unknown-installation',
    'management-priority',
  ]) {
    testWidgets(
      'A9 incompatible $reset disposes root and Navigator ownership',
      (tester) async {
        final auth = _GrantRefreshAuth(
          after: reset == 'collector-loss'
              ? _a9Worker(permissions: ['employee.portal.view'])
              : reset == 'management-priority'
              ? _a9Worker(
                  permissions: [
                    'route.view',
                    'collection.create',
                    'management.dashboard.view',
                  ],
                  management: true,
                )
              : null,
        );
        final identityStore = MemoryDeviceIdentityStore();
        final identity = _A9Identity(identityStore);
        await _pumpA9DirectApp(tester, auth, identity: identity);
        final rootState = tester.state(find.byType(CollectorRoutePage));
        final navigator = tester.state<NavigatorState>(find.byType(Navigator));
        await tester.tap(find.byKey(const Key('record-collection-entry-1')));
        await tester.pumpAndSettle();
        if (reset == 'installation') {
          await identityStore.writeInstallationId('synthetic-new-installation');
        }
        if (reset == 'unknown-installation') identity.fail = true;
        tester.binding.handleAppLifecycleStateChanged(
          AppLifecycleState.inactive,
        );
        tester.binding.handleAppLifecycleStateChanged(
          AppLifecycleState.resumed,
        );
        await tester.pumpAndSettle();
        expect(rootState.mounted, isFalse);
        expect(
          identical(
            navigator,
            tester.state<NavigatorState>(find.byType(Navigator)),
          ),
          isFalse,
        );
        expect(
          find.descendant(
            of: find.byKey(const Key('record-collection-entry-1')),
            matching: find.text('Retry'),
          ),
          findsNothing,
        );
      },
    );
  }
  testWidgets(
    'A9 in-flight result spanning grant refresh preserves one command',
    (tester) async {
      final auth = _GrantRefreshAuth();
      final payments = _DelayedDirectAttempt();
      await _pumpA9DirectApp(tester, auth, payments: payments);
      final rootState = tester.state(find.byType(CollectorRoutePage));
      await tester.tap(find.byKey(const Key('record-collection-entry-1')));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      final original = payments.drafts.single.toJson();
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      for (var frame = 0; frame < 12; frame++) {
        await tester.pump(const Duration(milliseconds: 50));
      }
      expect(
        identical(rootState, tester.state(find.byType(CollectorRoutePage))),
        isTrue,
      );
      expect(payments.drafts, hasLength(1));
      payments.pending.completeError(
        const SpinaApiException('Uncertain', code: 'network_unavailable'),
      );
      await tester.pumpAndSettle();
      expect(find.text('Retry'), findsOneWidget);
      expect(payments.drafts.single.toJson(), original);
    },
  );
  testWidgets(
    'A9 compatible rebind suppresses paint focus semantics mirror and invalidates old picker immediately',
    (tester) async {
      final auth = _GrantRefreshAuth();
      final identity = _A9Identity(MemoryDeviceIdentityStore());
      final images = testAppImageRecovery();
      final payments = _RetryRepository();
      final mirror = MirrorController(FakeMirrorRepository(), automatic: false);
      addTearDown(mirror.dispose);
      await _pumpA9DirectApp(
        tester,
        auth,
        identity: identity,
        images: images,
        mirror: mirror,
        payments: payments,
      );
      final root = tester.state(find.byType(CollectorRoutePage));
      await tester.tap(find.byKey(const Key('record-collection-entry-1')));
      await tester.pumpAndSettle();
      final original = payments.drafts.single.toJson();
      final selected = Completer<XFile?>();
      final oldPicker = images.pick(
        const ImagePickContext(
          purpose: 'proof',
          target: 'synthetic-loan',
          label: 'Private old proof',
        ),
        () => selected.future,
      );
      await tester.pump();
      identity.delayed = Completer<DeviceIdentity>();
      final classification = identity.delayed!;
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      for (
        var frame = 0;
        frame < 12 && (!identity.held || images.ready);
        frame++
      ) {
        await tester.pump();
      }
      expect(identity.held, isTrue);
      expect(images.ready, isFalse);
      expect(mirror.canReady, isFalse);
      selected.complete(XFile('/synthetic-private-old.jpg'));
      expect(
        await oldPicker,
        isNull,
        reason: 'Picker invalidated before awaited installation classification',
      );
      identity.delayed = Completer<DeviceIdentity>();
      identity.held = false;
      classification.complete(await identity.unheld());
      for (var frame = 0; frame < 12 && !identity.held; frame++) {
        await tester.pump();
      }
      expect(identity.held, isTrue);
      expect(find.text('Ana Client'), findsNothing);
      expect(root.mounted, isTrue);
      await tester.pump(const Duration(milliseconds: 400));
      expect(
        root.mounted,
        isTrue,
        reason: 'Ordinary delayed binding exceeds six frame waits',
      );
      expect(
        identical(
          root,
          tester.state(find.byType(CollectorRoutePage, skipOffstage: false)),
        ),
        isTrue,
      );
      final semantics = tester.ensureSemantics();
      expect(find.bySemanticsLabel(RegExp('Ana Client')), findsNothing);
      expect(
        find.byWidgetPredicate(
          (widget) => widget is ExcludeFocus && widget.excluding,
          skipOffstage: false,
        ),
        findsWidgets,
      );
      semantics.dispose();
      expect(
        () => images.pick(
          const ImagePickContext(
            purpose: 'proof',
            target: 'synthetic-loan',
            label: 'new selection',
          ),
          () async => null,
        ),
        throwsStateError,
      );
      identity.delayed!.complete(await identity.unheld());
      await tester.pumpAndSettle();
      expect(images.ready, isTrue);
      expect(
        identical(root, tester.state(find.byType(CollectorRoutePage))),
        isTrue,
      );
      expect(find.text('Office & staff'), findsNothing);
      expect(payments.drafts, hasLength(1));
      expect(payments.drafts.single.toJson(), original);
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets(
    'A9 actual app combined in-flight result spanning grants retains original command and preview',
    (tester) async {
      final pending = Completer<http.Response>();
      final requests = <Map<String, dynamic>>[];
      var previews = 0;
      await http.runWithClient(
        () async {
          final auth = _GrantRefreshAuth();
          await _pumpA9DirectApp(tester, auth, loader: _CombinedRouteLoader());
          final root = tester.state(find.byType(CollectorRoutePage));
          final pay = find.byKey(const Key('record-client-client-combined'));
          await tester.tap(pay);
          await tester.pump();
          await tester.pump(const Duration(milliseconds: 300));
          final original = Map<String, dynamic>.of(requests.single);
          tester.binding.handleAppLifecycleStateChanged(
            AppLifecycleState.inactive,
          );
          tester.binding.handleAppLifecycleStateChanged(
            AppLifecycleState.resumed,
          );
          for (var frame = 0; frame < 12; frame++) {
            await tester.pump(const Duration(milliseconds: 50));
          }
          expect(
            identical(root, tester.state(find.byType(CollectorRoutePage))),
            isTrue,
          );
          expect(requests, hasLength(1));
          pending.completeError(
            const SpinaApiException(
              'Synthetic uncertainty',
              code: 'network_unavailable',
            ),
          );
          await tester.pumpAndSettle();
          expect(find.text('Retry'), findsOneWidget);
          await tester.tap(pay);
          await tester.pumpAndSettle();
          expect(requests, hasLength(2));
          expect(requests.last, original);
          expect(previews, 1);
        },
        () => MockClient((request) async {
          expect(request.method, 'POST');
          if (request.url.path.endsWith('/combined/preview')) {
            previews++;
            return _a9CombinedPreviewResponse();
          }
          expect(request.url.path, endsWith('/combined'));
          requests.add(jsonDecode(request.body) as Map<String, dynamic>);
          return pending.future;
        }),
      );
    },
  );
  testWidgets(
    'A9 signout during covered classification invalidates stale cleanup generation',
    (tester) async {
      final auth = _GrantRefreshAuth();
      final identity = _A9Identity(MemoryDeviceIdentityStore());
      final images = testAppImageRecovery();
      await _pumpA9DirectApp(tester, auth, identity: identity, images: images);
      final root = tester.state(find.byType(CollectorRoutePage));
      final signOut = tester
          .widget<EnhancedRoleDashboard>(find.byType(EnhancedRoleDashboard))
          .onSignOut;
      identity.delayed = Completer<DeviceIdentity>();
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      for (var frame = 0; frame < 12 && images.ready; frame++) {
        await tester.pump();
      }
      expect(images.ready, isFalse);
      unawaited(signOut());
      await tester.pumpAndSettle();
      expect(root.mounted, isFalse);
      identity.delayed!.completeError(
        StateError('Stale installation completion after signout'),
      );
      await tester.pumpAndSettle();
      expect(find.byType(EnhancedRoleDashboard), findsNothing);
      expect(find.text('Updating access…'), findsNothing);
      expect(find.text('Sign in'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets(
    'A9 revoked renewal access rejects retained alert and action callbacks',
    (tester) async {
      var reads = 0;
      await http.runWithClient(
        () async {
          final auth = _GrantRefreshAuth(
            extraPermissions: ['renewal.cash_custody.assigned'],
          );
          await _pumpA9DirectApp(tester, auth);
          final oldAlert = tester
              .widget<CollectorCashStatusCard>(
                find.byType(CollectorCashStatusCard),
              )
              .onCashReleaseAlert!;
          final request = CollectorRenewalRequest.fromPayload({
            'request_id': 'synthetic-release',
            'client_id': 'synthetic-client',
            'client_code': 'SYNTHETIC',
            'client_name': 'Synthetic Borrower',
            'area': 'Cardona',
            'loan_id': 'synthetic-loan',
            'loan_number': 'SYNTHETIC-1',
            'loan_type_name': 'Regular',
            'current_principal': '1000',
            'remaining_balance': '100',
            'paid_cash': '900',
            'requested_amount': '1000',
            'status': 'approved',
            'submitted_at': '2026-10-01T00:00:00Z',
            'cash_released_to_collector_at': '2026-10-02T00:00:00Z',
            'net_release_amount': '900',
            'signer_readiness_status': 'complete',
            'handover_proof_status': 'pending',
            'activation_status': 'pending',
          });
          oldAlert(request);
          await tester.pumpAndSettle();
          final oldAction = tester
              .widget<TextButton>(
                find.byKey(const Key('collector-cash-release-banner-view')),
              )
              .onPressed!;
          tester.binding.handleAppLifecycleStateChanged(
            AppLifecycleState.inactive,
          );
          tester.binding.handleAppLifecycleStateChanged(
            AppLifecycleState.resumed,
          );
          await tester.pumpAndSettle();
          final before = reads;
          oldAlert(request);
          oldAction();
          await tester.pumpAndSettle();
          expect(find.byType(CollectorRenewalCashReleasePage), findsNothing);
          expect(find.textContaining('Synthetic Borrower'), findsNothing);
          expect(
            reads,
            before,
            reason: 'Revoked old callbacks cannot refetch private renewal',
          );
          await tester.pump(const Duration(seconds: 7));
        },
        () => MockClient((request) async {
          expect(request.method, 'GET');
          reads++;
          return http.Response(
            '{"message":"Explicit blocked synthetic read"}',
            503,
          );
        }),
      );
    },
  );
  testWidgets(
    'root More and secondary Back preserve the exact pending payment',
    (tester) async {
      final repository = _RetryRepository();
      final platformCalls = <String>[];
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
        SystemChannels.platform,
        (call) async {
          platformCalls.add(call.method);
          return null;
        },
      );
      addTearDown(
        () => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
          SystemChannels.platform,
          null,
        ),
      );
      await tester.binding.setSurfaceSize(const Size(800, 1200));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        MaterialApp(
          home: CollectorFieldHomePage(
            session: _session,
            onSignOut: () async {},
            collectorRouteLoader: _RouteLoader(isFromCache: false),
            paymentSubmissionRepository: repository,
            deviceIdentityProvider: _deviceIdentityProvider(),
            collectionDeviceSequence: MemoryCollectionDeviceSequence(),
          ),
        ),
      );
      await tester.pumpAndSettle();
      final pay = find.byKey(const Key('record-collection-entry-1'));
      await tester.ensureVisible(pay);
      await tester.tap(pay);
      await tester.pumpAndSettle();
      expect(repository.drafts, hasLength(1));
      await tester.tap(find.byKey(const Key('collector-more-tab')));
      await tester.pumpAndSettle();
      final offline = find.byKey(const Key('collector-more-offline'));
      await tester.ensureVisible(offline);
      await tester.pumpAndSettle();
      await tester.tap(offline);
      await tester.pumpAndSettle();
      expect(find.text('Daily Collection'), findsNothing);
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      expect(find.text('Retry'), findsOneWidget);
      expect(repository.drafts, hasLength(1));
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      expect(platformCalls, isNot(contains('SystemNavigator.pop')));
      await tester.tap(pay);
      await tester.pumpAndSettle();
      expect(repository.drafts, hasLength(2));
      expect(repository.drafts.last.toJson(), repository.drafts.first.toJson());
      expect(repository.drafts.last.toJson()['amount'], '200.00');
      expect(repository.drafts.last.deviceSequence, 1);
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      expect(platformCalls, contains('SystemNavigator.pop'));
    },
  );

  testWidgets(
    'mixed worker switch preserves the same pending payment identity',
    (tester) async {
      final repository = _RetryRepository();
      await tester.binding.setSurfaceSize(const Size(800, 1200));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      var session = const UserSession(
        userId: 'worker',
        username: 'worker',
        displayName: 'Worker',
        role: AppRole.collector,
        rawRole: 'Collector',
        roles: ['Collector', 'Employee'],
        accessToken: 'synthetic-token',
        permissions: [
          'route.view',
          'collection.create',
          'employee.portal.view',
        ],
      );
      late StateSetter refreshSession;
      final provider = _deviceIdentityProvider();
      final sequence = MemoryCollectionDeviceSequence();
      await tester.pumpWidget(
        MaterialApp(
          home: StatefulBuilder(
            builder: (_, setState) {
              refreshSession = setState;
              return EnhancedRoleDashboard(
                session: session,
                onSignOut: () async {},
                collectorRouteLoader: _RouteLoader(isFromCache: false),
                paymentSubmissionRepository: repository,
                deviceIdentityProvider: provider,
                collectionDeviceSequence: sequence,
              );
            },
          ),
        ),
      );
      await tester.pumpAndSettle();
      final pay = find.byKey(const Key('record-collection-entry-1'));
      await tester.ensureVisible(pay);
      await tester.tap(pay);
      await tester.pumpAndSettle();
      expect(repository.drafts, hasLength(1));
      await tester.tap(find.text('Office & staff'));
      await tester.pumpAndSettle();
      expect(find.text('Employee Dashboard'), findsOneWidget);
      expect(repository.drafts, hasLength(1));
      await tester.tap(find.text('Collector'));
      await tester.pumpAndSettle();
      refreshSession(
        () => session = const UserSession(
          userId: 'worker',
          username: 'worker',
          displayName: 'Worker',
          role: AppRole.collector,
          rawRole: 'Collector',
          roles: ['Collector', 'Employee'],
          accessToken: 'refreshed-token',
          permissions: ['route.view', 'collection.create'],
        ),
      );
      await tester.pumpAndSettle();
      await tester.ensureVisible(pay);
      await tester.tap(pay);
      await tester.pumpAndSettle();
      expect(repository.drafts, hasLength(2));
      expect(repository.drafts.last.toJson(), repository.drafts.first.toJson());
      expect(repository.drafts.last.deviceSequence, 1);
    },
  );

  testWidgets(
    'pushed route Back cannot discard an uncertain combined attempt',
    (tester) async {
      final repository = _RetryCombinedRepository();
      await tester.binding.setSurfaceSize(const Size(800, 1200));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => Scaffold(
              body: TextButton(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => CollectorRoutePage(
                      session: _session,
                      loader: _CombinedRouteLoader(),
                      combinedPaymentRepository: repository,
                      deviceIdentityProvider: _deviceIdentityProvider(),
                      deviceSequence: MemoryCollectionDeviceSequence(),
                    ),
                  ),
                ),
                child: const Text('Open route'),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Open route'));
      await tester.pumpAndSettle();
      final pay = find.byKey(const Key('record-client-client-combined'));
      await tester.tap(pay);
      await tester.pumpAndSettle();
      expect(repository.attempts, hasLength(1));
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      expect(find.text('Daily Collection'), findsOneWidget);
      expect(repository.attempts, hasLength(1));
      await tester.tap(pay);
      await tester.pumpAndSettle();
      expect(repository.previews, hasLength(1));
      expect(repository.attempts, hasLength(2));
      expect(
        repository.attempts.last.toJson(),
        repository.attempts.first.toJson(),
      );
      expect(repository.attempts.last.reviewedAllocationHash, _allocationHash);
      expect(
        repository.attempts.last.toJson()['cash_received_amount'],
        '150.00',
      );
      expect(repository.attempts.last.deviceSequence, 1);
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      expect(find.text('Open route'), findsOneWidget);
    },
  );
  testWidgets('offline route keeps collection button disabled', (tester) async {
    final repository = _RetryRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: CollectorRoutePage(
          session: _session,
          loader: _RouteLoader(isFromCache: true),
          paymentRepository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    final button = tester.widget<FilledButton>(
      find.byKey(const Key('record-collection-entry-1')),
    );
    expect(button.onPressed, isNull);
    expect(repository.drafts, isEmpty);
    expect(
      find.byKey(const Key('collector-offline-read-only')),
      findsOneWidget,
    );
    expect(
      find.textContaining('no payment is accepted or queued'),
      findsOneWidget,
    );

    await tester.tap(find.byKey(const Key('route-client-client-1')));
    await tester.pumpAndSettle();

    expect(
      find.textContaining('Offline route copies are read-only'),
      findsOneWidget,
    );
    expect(repository.drafts, isEmpty);
  });

  testWidgets('one tap Pay posts the scheduled amount without opening a form', (
    tester,
  ) async {
    final repository = _RecordingRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: CollectorRoutePage(
          session: _session,
          loader: _RouteLoader(isFromCache: false),
          paymentRepository: repository,
          deviceIdentityProvider: _deviceIdentityProvider(),
          deviceSequence: MemoryCollectionDeviceSequence(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    final button = tester.widget<FilledButton>(
      find.byKey(const Key('record-collection-entry-1')),
    );
    expect(button.onPressed, isNotNull);
    expect(find.text('Pay'), findsOneWidget);

    await tester.tap(find.byKey(const Key('record-collection-entry-1')));
    await tester.pumpAndSettle();

    expect(find.text('Record Collection'), findsNothing);
    expect(repository.drafts, hasLength(1));
    expect(repository.drafts.single.entryType, CollectionEntryType.payment);
    expect(repository.drafts.single.toJson()['amount'], '200.00');
    expect(repository.drafts.single.coveredDates, hasLength(1));
  });

  testWidgets('expanded route keeps special payment details available', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(800, 1200));
    addTearDown(() async {
      await tester.binding.setSurfaceSize(null);
    });

    await tester.pumpWidget(
      MaterialApp(
        home: CollectorRoutePage(
          session: _session,
          loader: _RouteLoader(isFromCache: false),
          paymentRepository: _RecordingRepository(),
          deviceIdentityProvider: _deviceIdentityProvider(),
          deviceSequence: MemoryCollectionDeviceSequence(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('signed-contract verification'), findsNothing);
    await tester.tap(find.byKey(const Key('route-client-client-1')));
    await tester.pumpAndSettle();

    expect(
      find.textContaining('Contract schedule: signed-contract verification'),
      findsOneWidget,
    );
    expect(find.byKey(const Key('collection-details-entry-1')), findsOneWidget);
  });

  testWidgets('7x7 stays desktop-only when server gate is false', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: CollectorRoutePage(
          session: _session,
          loader: _RouteLoader(
            isFromCache: false,
            entry: _sevenBySevenEntry(enabled: false),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    final button = tester.widget<FilledButton>(
      find.byKey(const Key('record-collection-entry-7x7')),
    );
    expect(button.onPressed, isNull);
    expect(find.text('Desk'), findsOneWidget);

    await tester.tap(find.byKey(const Key('route-client-client-7x7')));
    await tester.pumpAndSettle();
    expect(
      find.textContaining('protected server allocator explicitly enables'),
      findsOneWidget,
    );
  });

  testWidgets('server-enabled 7x7 Pay posts directly from the route', (
    tester,
  ) async {
    final repository = _RecordingRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: CollectorRoutePage(
          session: _session,
          loader: _RouteLoader(
            isFromCache: false,
            entry: _sevenBySevenEntry(enabled: true),
          ),
          paymentRepository: repository,
          deviceIdentityProvider: _deviceIdentityProvider(),
          deviceSequence: MemoryCollectionDeviceSequence(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    final button = tester.widget<FilledButton>(
      find.byKey(const Key('record-collection-entry-7x7')),
    );
    expect(button.onPressed, isNotNull);
    expect(find.text('Pay'), findsOneWidget);

    await tester.tap(find.byKey(const Key('record-collection-entry-7x7')));
    await tester.pumpAndSettle();

    expect(find.text('Record Collection'), findsNothing);
    expect(repository.drafts, hasLength(1));
    expect(repository.drafts.single.toJson()['amount'], '35.00');
  });

  testWidgets(
    'a partial contractual receipt leaves Pay active for the lacking amount',
    (tester) async {
      final repository = _RecordingRepository();
      const entry = CollectorRouteEntry(
        id: 'entry-partial',
        clientId: 'client-partial',
        loanId: 'loan-partial',
        clientName: 'Partial Client',
        area: 'Cardona',
        loanType: 'Regular',
        dailyAmount: 200,
        balance: 4700,
        status: 'Recorded today',
        passCount: 0,
        routeRevision: 'loan:loan-partial:v2',
        contractAllocationEnabled: true,
        contractScheduleVerified: true,
        contractDpdStatus: 'ready',
        contractBalanceReconciled: true,
        contractScheduleReady: true,
        contractCollectionReady: true,
        contractTodayScheduledAmount: 200,
        contractTodayUnpaidAmount: 100,
        processedToday: true,
        todayEntryType: 'payment',
        todayAmount: 100,
        todayCollectorName: 'Other Collector',
        todayTransactionId: 'tx-partial',
      );

      await tester.pumpWidget(
        MaterialApp(
          home: CollectorRoutePage(
            session: _session,
            loader: _RouteLoader(isFromCache: false, entry: entry),
            paymentRepository: repository,
            deviceIdentityProvider: _deviceIdentityProvider(),
            deviceSequence: MemoryCollectionDeviceSequence(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('LACKING'), findsOneWidget);
      final button = tester.widget<FilledButton>(
        find.byKey(const Key('record-collection-entry-partial')),
      );
      expect(button.onPressed, isNotNull);
      expect(find.text('Pay'), findsOneWidget);

      await tester.tap(
        find.byKey(const Key('record-collection-entry-partial')),
      );
      await tester.pumpAndSettle();

      expect(repository.drafts, hasLength(1));
      expect(repository.drafts.single.toJson()['amount'], '100.00');
    },
  );

  testWidgets('a fully satisfied contractual day disables another normal Pay', (
    tester,
  ) async {
    const entry = CollectorRouteEntry(
      id: 'entry-paid',
      clientId: 'client-paid',
      loanId: 'loan-paid',
      clientName: 'Paid Client',
      area: 'Cardona',
      loanType: 'Regular',
      dailyAmount: 200,
      balance: 4600,
      status: 'Recorded today',
      passCount: 0,
      routeRevision: 'loan:loan-paid:v2',
      contractAllocationEnabled: true,
      contractScheduleVerified: true,
      contractDpdStatus: 'ready',
      contractBalanceReconciled: true,
      contractScheduleReady: true,
      contractCollectionReady: true,
      contractTodayScheduledAmount: 200,
      contractTodayUnpaidAmount: 0,
      processedToday: true,
      todayEntryType: 'payment',
      todayAmount: 200,
      todayTransactionId: 'tx-paid',
    );

    await tester.pumpWidget(
      MaterialApp(
        home: CollectorRoutePage(
          session: _session,
          loader: _RouteLoader(isFromCache: false, entry: entry),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Paid'), findsOneWidget);
    final button = tester.widget<FilledButton>(
      find.byKey(const Key('record-collection-entry-paid')),
    );
    expect(button.onPressed, isNull);
  });

  testWidgets('route retry reuses the exact payment key and device sequence', (
    tester,
  ) async {
    final repository = _RetryRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: CollectorRoutePage(
          session: _session,
          loader: _RouteLoader(isFromCache: false),
          paymentRepository: repository,
          deviceIdentityProvider: _deviceIdentityProvider(),
          deviceSequence: MemoryCollectionDeviceSequence(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    final pay = find.byKey(const Key('record-collection-entry-1'));
    await tester.tap(pay);
    await tester.pumpAndSettle();

    expect(repository.drafts, hasLength(1));
    expect(find.text('Retry'), findsOneWidget);
    expect(find.textContaining('not confirmed'), findsOneWidget);

    await tester.tap(pay);
    await tester.pumpAndSettle();

    expect(repository.drafts, hasLength(2));
    expect(
      repository.drafts.first.idempotencyKey,
      repository.drafts.last.idempotencyKey,
    );
    expect(repository.drafts.first.deviceSequence, 1);
    expect(repository.drafts.last.deviceSequence, 1);
  });

  testWidgets(
    'combined Pay silently previews one total then saves atomically',
    (tester) async {
      final repository = _CombinedRecordingRepository();
      await tester.binding.setSurfaceSize(const Size(430, 1100));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        MaterialApp(
          home: CollectorRoutePage(
            session: _session,
            loader: _CombinedRouteLoader(),
            combinedPaymentRepository: repository,
            deviceIdentityProvider: _deviceIdentityProvider(),
            deviceSequence: MemoryCollectionDeviceSequence(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('record-client-client-combined')));
      await _pumpCombinedSheet(tester);

      expect(find.byKey(const Key('combined-payment-total')), findsNothing);
      expect(repository.previews, hasLength(1));
      expect(
        repository.previews.single.toJson()['cash_received_amount'],
        '150.00',
      );
      expect(
        repository.previews.single.legs.any(
          (leg) => leg.toJson().containsKey('amount'),
        ),
        isFalse,
      );
      expect(repository.submissions, hasLength(1));
      expect(
        repository.submissions.single.reviewedAllocationHash,
        _allocationHash,
      );
    },
  );

  testWidgets(
    'combined Pay waits for preview and sends changed server state to details',
    (tester) async {
      final repository = _DelayedCombinedRepository();
      await pumpAndroidRoleFixture(
        tester,
        size: const Size(320, 640),
        textScaler: TextScaler.linear(2),
        home: CollectorRoutePage(
          session: _session,
          loader: _CombinedRouteLoader(),
          combinedPaymentRepository: repository,
          deviceIdentityProvider: _deviceIdentityProvider(),
          deviceSequence: MemoryCollectionDeviceSequence(),
        ),
      );
      await tester.pumpAndSettle();

      await tester.ensureVisible(
        find.byKey(const Key('record-client-client-combined')),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('record-client-client-combined')));
      await tester.pump();
      expect(repository.requests, hasLength(1));
      expect(find.byKey(const Key('combined-payment-total')), findsNothing);
      await captureAndroidWorkflow(tester, 'C4-combined-preview-pending');

      repository.completers.first.complete(_shortCombinedPreview);
      await _pumpCombinedSheet(tester);

      expect(find.byKey(const Key('combined-payment-total')), findsNothing);
      expect(
        find.textContaining('Payment details / other amount'),
        findsOneWidget,
      );
      await captureAndroidWorkflowScroll(tester, 'C4-combined-short');
    },
  );

  testWidgets('combined Pay surfaces a server cash custody review in one tap', (
    tester,
  ) async {
    final repository = _CombinedCustodyReviewRepository();
    await pumpAndroidRoleFixture(
      tester,
      size: const Size(320, 640),
      textScaler: TextScaler.linear(2),
      home: CollectorRoutePage(
        session: _session,
        loader: _CombinedRouteLoader(),
        combinedPaymentRepository: repository,
        deviceIdentityProvider: _deviceIdentityProvider(),
        deviceSequence: MemoryCollectionDeviceSequence(),
      ),
    );
    await tester.pumpAndSettle();
    await tester.ensureVisible(
      find.byKey(const Key('record-client-client-combined')),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('record-client-client-combined')));
    await _pumpCombinedSheet(tester);

    expect(find.textContaining('CASH CUSTODY REVIEW REQUIRED'), findsOneWidget);
    expect(find.textContaining('10.00 remains unallocated'), findsOneWidget);
    expect(find.textContaining('saved • Receipts'), findsNothing);
    await captureAndroidWorkflowScroll(tester, 'C4-combined-custody-review');
  });

  testWidgets(
    'combined Pay leaves true-extra borrower choices to payment details',
    (tester) async {
      final repository = _RecoverableExtraChoiceRepository();
      await pumpAndroidRoleFixture(
        tester,
        size: const Size(320, 640),
        textScaler: TextScaler.linear(2),
        home: CollectorRoutePage(
          session: _session,
          loader: _CombinedRouteLoader(),
          combinedPaymentRepository: repository,
          deviceIdentityProvider: _deviceIdentityProvider(),
          deviceSequence: MemoryCollectionDeviceSequence(),
        ),
      );
      await tester.pumpAndSettle();
      await tester.ensureVisible(
        find.byKey(const Key('record-client-client-combined')),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('record-client-client-combined')));
      await _pumpCombinedSheet(tester);

      expect(find.byKey(const Key('combined-payment-total')), findsNothing);
      expect(
        find.textContaining('Payment details / other amount'),
        findsOneWidget,
      );
      expect(repository.submitCount, 0);
      await captureAndroidWorkflowScroll(tester, 'C4-combined-extra');
    },
  );

  testWidgets(
    'combined Pay stays gated when the backend preview capability is unavailable',
    (tester) async {
      final repository = _UnavailableCombinedRepository();
      await tester.binding.setSurfaceSize(const Size(430, 1100));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        MaterialApp(
          home: CollectorRoutePage(
            session: _session,
            loader: _CombinedRouteLoader(),
            combinedPaymentRepository: repository,
            deviceIdentityProvider: _deviceIdentityProvider(),
            deviceSequence: MemoryCollectionDeviceSequence(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('record-client-client-combined')));
      await _pumpCombinedSheet(tester);

      expect(repository.previewCount, 1);
      expect(find.textContaining('backend update is required'), findsOneWidget);
      expect(find.byKey(const Key('combined-payment-total')), findsNothing);
      expect(repository.submitCount, 0);
    },
  );

  testWidgets(
    'revoked-device route failure gives an action instead of raw text',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: CollectorRoutePage(
            session: _session,
            loader: _FailingRouteLoader(
              const SpinaApiException(
                'This device has been revoked.',
                statusCode: 403,
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(
        find.text(
          'This device is no longer approved. Ask Management to approve this device, then sign in again.',
        ),
        findsOneWidget,
      );
      expect(find.text('This device has been revoked.'), findsNothing);
      expect(find.text('Try again'), findsNothing);
      expect(find.text('Access unavailable'), findsOneWidget);
      expect(
        find.widgetWithText(OutlinedButton, 'Access unavailable'),
        findsNothing,
      );
      expect(
        tester
            .widget<IconButton>(
              find.byWidgetPredicate(
                (widget) =>
                    widget is IconButton && widget.tooltip == 'Refresh route',
              ),
            )
            .onPressed,
        isNull,
      );
    },
  );

  testWidgets('stale payment tells the Collector to refresh and review', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: CollectorRoutePage(
          session: _session,
          loader: _RouteLoader(isFromCache: false),
          paymentRepository: _StaleRouteRepository(),
          deviceIdentityProvider: _deviceIdentityProvider(),
          deviceSequence: MemoryCollectionDeviceSequence(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('record-collection-entry-1')));
    await tester.pumpAndSettle();

    expect(
      find.text(
        'This route changed after you opened it. Refresh the route, review the client, then try again.',
      ),
      findsOneWidget,
    );
    expect(find.text('Internal route revision conflict.'), findsNothing);
  });

  testWidgets('daily route stays usable at 360x640 with 1.3 text scale', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(360, 640));
    addTearDown(() async => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        home: MediaQuery(
          data: const MediaQueryData(textScaler: TextScaler.linear(1.3)),
          child: CollectorRoutePage(
            session: _session,
            loader: _RouteLoader(isFromCache: false),
            paymentRepository: _RecordingRepository(),
            deviceIdentityProvider: _deviceIdentityProvider(),
            deviceSequence: MemoryCollectionDeviceSequence(),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect(find.byKey(const Key('route-client-client-1')), findsOneWidget);
    await tester.tap(find.byKey(const Key('route-client-client-1')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('collection-details-entry-1')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}

Future<void> _pumpCombinedSheet(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 500));
  await tester.pump();
}

const UserSession _session = UserSession(
  userId: 'collector-1',
  username: 'collector.one',
  displayName: 'Test Collector',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'test-token',
  permissions: <String>['route.view', 'collection.create'],
);

const CollectorRouteEntry _regularEntry = CollectorRouteEntry(
  id: 'entry-1',
  clientId: 'client-1',
  loanId: 'loan-1',
  clientName: 'Ana Client',
  area: 'Cardona',
  loanType: 'Regular',
  dailyAmount: 200,
  balance: 4800,
  status: 'Pending',
  passCount: 0,
  routeRevision: 'revision-1',
  collectionMessage:
      'Ready for mobile collection. Contract schedule: signed-contract verification is still required.',
  contractReadinessMessage:
      'Contract schedule: signed-contract verification is still required.',
);

CollectorRouteEntry _sevenBySevenEntry({required bool enabled}) {
  return CollectorRouteEntry(
    id: 'entry-7x7',
    clientId: 'client-7x7',
    loanId: 'loan-7x7',
    clientName: 'Seven Client',
    area: 'Cardona',
    loanType: '7x7',
    dailyAmount: 35,
    balance: 5000,
    status: 'Pending',
    passCount: 0,
    routeRevision: 'loan:loan-7x7:v0',
    canCollectMobile: enabled,
    canEnterPayment: enabled,
    sevenBySevenMobileEnabled: enabled,
    collectionMessage: enabled
        ? 'Ready for protected 7x7 mobile collection.'
        : 'Use SPINA desktop for this 7x7 loan.',
  );
}

DeviceIdentityProvider _deviceIdentityProvider() {
  return DeviceIdentityProvider(
    store: MemoryDeviceIdentityStore(),
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
    randomByteGenerator: (length) => List<int>.filled(length, 7),
  );
}

class _GrantRefreshAuth
    implements
        AuthRepository,
        SessionValidationRepository,
        SessionRefreshRepository {
  _GrantRefreshAuth({
    this.after,
    this.keepGrants = false,
    this.extraPermissions = const [],
    this.refreshable = false,
  });
  final UserSession? after;
  final bool keepGrants;
  final List<String> extraPermissions;
  final bool refreshable;
  VoidCallback? beforeReturn;
  int validations = 0;
  UserSession get initial => _worker(true);
  UserSession _worker(bool employee) => UserSession(
    userId: 'worker',
    username: 'worker',
    displayName: 'Worker',
    role: AppRole.collector,
    rawRole: 'Collector',
    roles: const ['Collector', 'Employee'],
    accessToken: employee ? 'initial-synthetic' : 'refreshed-synthetic',
    refreshToken: refreshable ? 'synthetic-refresh-token' : null,
    expiresAt: DateTime.now().toUtc().add(
      refreshable ? const Duration(minutes: 3) : const Duration(hours: 1),
    ),
    permissions: [
      'route.view',
      'collection.create',
      if (employee) 'employee.portal.view',
      if (employee) ...extraPermissions,
    ],
  );
  @override
  Future<UserSession> validate(UserSession session) async {
    if (++validations == 1) return initial;
    beforeReturn?.call();
    return after ?? _worker(keepGrants);
  }

  @override
  Future<UserSession> refresh(UserSession session) async {
    beforeReturn?.call();
    return after ?? _worker(keepGrants);
  }

  @override
  Future<UserSession> signIn({
    required String username,
    required String password,
  }) async => throw StateError('No real sign-in');
  @override
  Future<void> signOut(UserSession session) async {}
}

UserSession _a9Worker({
  String userId = 'worker',
  required List<String> permissions,
  bool management = false,
}) => UserSession(
  userId: userId,
  username: 'worker',
  displayName: 'Worker',
  role: AppRole.collector,
  rawRole: 'Collector',
  roles: ['Collector', 'Employee', if (management) 'Management'],
  accessToken: 'refreshed-synthetic',
  permissions: permissions,
  expiresAt: DateTime.now().toUtc().add(const Duration(hours: 1)),
);

Future<void> _pumpA9DirectApp(
  WidgetTester tester,
  _GrantRefreshAuth auth, {
  DeviceIdentityProvider? identity,
  PaymentSubmissionRepository? payments,
  ImageRecoveryController? images,
  MirrorController? mirror,
  CollectorRouteLoader? loader,
  MemorySessionStore? store,
}) async {
  await tester.binding.setSurfaceSize(const Size(800, 1200));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  addTearDown(() => auth.initial.clearRefreshOverride());
  final sessionStore = store ?? MemorySessionStore();
  await sessionStore.write(auth.initial);
  final provider = identity ?? _deviceIdentityProvider();
  final service = EmployeeOperationsService(
    deviceIdentityProvider: provider,
    outbox: AttendanceOutbox(MemoryAttendanceVault()),
  );
  addTearDown(service.dispose);
  await tester.pumpWidget(
    GilbicApp(
      sessionStore: sessionStore,
      authRepository: auth,
      collectorRouteLoader: loader ?? _RouteLoader(isFromCache: false),
      paymentSubmissionRepository: payments ?? _RetryRepository(),
      deviceIdentityProvider: provider,
      collectionDeviceSequence: MemoryCollectionDeviceSequence(),
      imageRecoveryController: images ?? testAppImageRecovery(),
      mirrorController: mirror,
      employeeOperationsService: service,
    ),
  );
  await tester.pumpAndSettle();
}

http.Response _a9CombinedPreviewResponse() => http.Response(
  jsonEncode({
    'data': {
      'status': 'exact',
      'requires_review': false,
      'allocation_hash': _allocationHash,
      'cash_received_amount': '150.00',
      'expected_total_amount': '150.00',
      'short_amount': '0.00',
      'extra_amount': '0.00',
      'legs': [
        for (final leg in _exactCombinedPreview.legs)
          {
            'loan_id': leg.loanId,
            'loan_type': leg.loanType,
            'scheduled_amount': leg.scheduledAmount,
            'extra_amount': leg.extraAmount,
            'total_amount': leg.totalAmount,
          },
      ],
    },
  }),
  200,
);

class _A9Identity extends DeviceIdentityProvider {
  _A9Identity(DeviceIdentityStore store)
    : super(
        store: store,
        platformResolver: () => 'android',
        appVersionResolver: () async => '1.0.0',
        randomByteGenerator: (n) => List.filled(n, 9),
      );
  bool fail = false;
  Completer<DeviceIdentity>? delayed;
  bool held = false;
  int calls = 0;
  Future<DeviceIdentity> unheld() => super.load();
  @override
  Future<DeviceIdentity> load() async {
    calls++;
    if (fail) throw StateError('Synthetic unknown device');
    if (delayed != null && !delayed!.isCompleted) {
      held = true;
      return delayed!.future;
    }
    return super.load();
  }
}

class _A9RecordingStore extends MemorySessionStore {
  final writes = <String>[];
  @override
  Future<void> write(UserSession session) async {
    writes.add(session.userId);
    await super.write(session);
  }
}

class _A9PrivateProbe extends StatefulWidget {
  const _A9PrivateProbe({required this.onDispose});
  final VoidCallback onDispose;
  @override
  State<_A9PrivateProbe> createState() => _A9PrivateProbeState();
}

class _A9PrivateProbeState extends State<_A9PrivateProbe> {
  @override
  void dispose() {
    widget.onDispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => const PopScope(
    canPop: false,
    child: Scaffold(body: Text('private attendance probe')),
  );
}

class _MutableAttemptRoute implements CollectorRouteLoader {
  _MutableAttemptRoute({required this.combined});
  final bool combined;
  bool paid = false;
  bool contractual = false;
  bool changedGrouping = false;
  bool ready = true;
  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async {
    final original =
        await (combined
                ? _CombinedRouteLoader()
                : _RouteLoader(isFromCache: false))
            .loadToday(session);
    if (changedGrouping) {
      final entries = combined
          ? [
              for (final entry in original.route.entries)
                CollectorRouteEntry.fromPayload({
                  ...entry.toJson(),
                  'processed_today': entry.loanType == '7x7',
                  'route_revision': 'changed-${entry.loanId}',
                })!,
            ]
          : [
              ...original.route.entries,
              CollectorRouteEntry.fromPayload({
                ..._sevenBySevenEntry(enabled: true).toJson(),
                'client_id': _regularEntry.clientId,
                'client_name': _regularEntry.clientName,
              })!,
            ];
      return CollectorRouteLoadResult(
        route: CollectorRoute(
          routeDate: original.route.routeDate,
          collectorName: original.route.collectorName,
          areas: original.route.areas,
          expectedTotal: 235,
          entries: entries,
        ),
        syncedAt: original.syncedAt,
        isFromCache: false,
      );
    }
    if (!paid) return original;
    return CollectorRouteLoadResult(
      route: CollectorRoute(
        routeDate: original.route.routeDate,
        collectorName: original.route.collectorName,
        areas: original.route.areas,
        expectedTotal: 0,
        entries: [
          for (final entry in original.route.entries)
            CollectorRouteEntry.fromPayload({
              ...entry.toJson(),
              'processed_today': true,
              'status': 'Paid',
              'route_revision': 'fresh-paid-revision',
              // Producer flags describe reconciliation/mobile feature readiness; paid
              // today alone does not revoke either flag (collector_route_repository.py).
              'can_collect_mobile': ready, 'can_enter_payment': ready,
              'contract_collection_ready': contractual,
              'contract_allocation_enabled': contractual,
              'contract_schedule_verified': contractual,
              'contract_schedule_ready': contractual,
              'contract_today_scheduled_amount': entry.dailyAmount,
              'contract_today_unpaid_amount': '0.00',
            })!,
        ],
      ),
      syncedAt: original.syncedAt,
      isFromCache: false,
    );
  }
}

class _DelayedDirectAttempt implements PaymentSubmissionRepository {
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
}

class _DelayedCombinedAttempt extends _CombinedRecordingRepository {
  final pending = Completer<CombinedPaymentSubmissionResult>();
  @override
  Future<CombinedPaymentSubmissionResult> submit(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  ) {
    submissions.add(draft);
    return pending.future;
  }
}

class _RouteLoader implements CollectorRouteLoader {
  _RouteLoader({required this.isFromCache, this.entry = _regularEntry});

  final bool isFromCache;
  final CollectorRouteEntry entry;

  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async {
    return CollectorRouteLoadResult(
      route: CollectorRoute(
        routeDate: DateTime(2026, 8, 1),
        collectorName: 'Test Collector',
        areas: const <String>['Cardona'],
        expectedTotal: entry.dailyAmount,
        entries: <CollectorRouteEntry>[entry],
      ),
      syncedAt: DateTime.utc(2026, 8, 1, 3),
      isFromCache: isFromCache,
    );
  }
}

class _FailingRouteLoader implements CollectorRouteLoader {
  const _FailingRouteLoader(this.error);

  final Object error;

  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) {
    return Future<CollectorRouteLoadResult>.error(error);
  }
}

class _RecordingRepository implements PaymentSubmissionRepository {
  final List<PaymentSubmissionDraft> drafts = <PaymentSubmissionDraft>[];

  @override
  Future<PaymentSubmissionResult> submit(
    UserSession session,
    PaymentSubmissionDraft draft,
  ) async {
    drafts.add(draft);
    return PaymentSubmissionResult(
      disposition: PaymentSubmissionDisposition.accepted,
      idempotencyKey: draft.idempotencyKey,
      message: 'Payment saved.',
      receiptNumber: 'R-2001',
      officialBalance: 4600,
    );
  }
}

class _RetryRepository implements PaymentSubmissionRepository {
  final List<PaymentSubmissionDraft> drafts = <PaymentSubmissionDraft>[];

  @override
  Future<PaymentSubmissionResult> submit(
    UserSession session,
    PaymentSubmissionDraft draft,
  ) async {
    drafts.add(draft);
    if (drafts.length == 1) {
      throw const SpinaApiException(
        'The collection could not reach the SPINA server.',
        code: 'network_unavailable',
      );
    }
    return PaymentSubmissionResult(
      disposition: PaymentSubmissionDisposition.duplicate,
      idempotencyKey: draft.idempotencyKey,
      message: 'Already recorded.',
      receiptNumber: 'R-2001',
      officialBalance: 4600,
    );
  }
}

class _StaleRouteRepository implements PaymentSubmissionRepository {
  @override
  Future<PaymentSubmissionResult> submit(
    UserSession session,
    PaymentSubmissionDraft draft,
  ) {
    throw const SpinaApiException(
      'Internal route revision conflict.',
      statusCode: 409,
      code: 'route_revision_changed',
    );
  }
}

class _CombinedRouteLoader implements CollectorRouteLoader {
  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async {
    return CollectorRouteLoadResult(
      route: CollectorRoute(
        routeDate: DateTime(2026, 8, 1),
        collectorName: 'Test Collector',
        areas: const <String>['Cardona'],
        expectedTotal: 150,
        entries: const <CollectorRouteEntry>[
          CollectorRouteEntry(
            id: 'regular-combined',
            clientId: 'client-combined',
            loanId: 'loan-regular',
            clientName: 'Combined Client',
            area: 'Cardona',
            loanType: 'Regular',
            dailyAmount: 100,
            balance: 4800,
            status: 'Pending',
            passCount: 0,
            routeRevision: 'loan:loan-regular:v0',
          ),
          CollectorRouteEntry(
            id: 'seven-combined',
            clientId: 'client-combined',
            loanId: 'loan-seven',
            clientName: 'Combined Client',
            area: 'Cardona',
            loanType: '7x7',
            dailyAmount: 50,
            balance: 3000,
            status: 'Pending',
            passCount: 0,
            routeRevision: 'loan:loan-seven:v0',
            sevenBySevenMobileEnabled: true,
          ),
        ],
      ),
      syncedAt: DateTime.utc(2026, 8, 1, 3),
      isFromCache: false,
    );
  }
}

const String _allocationHash =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';

const CombinedPaymentAllocationPreview _exactCombinedPreview =
    CombinedPaymentAllocationPreview(
      status: 'exact',
      requiresReview: false,
      allocationHash: _allocationHash,
      cashReceivedAmount: 150,
      expectedTotalAmount: 150,
      shortAmount: 0,
      extraAmount: 0,
      extraChoiceRequired: false,
      regularPastDueFollowupRequired: false,
      message: 'Exact Regular + 7x7 amount.',
      legs: <CombinedPaymentAllocationLeg>[
        CombinedPaymentAllocationLeg(
          loanId: 'loan-seven',
          loanType: 'seven_by_seven',
          scheduledAmount: 50,
          extraAmount: 0,
          totalAmount: 50,
        ),
        CombinedPaymentAllocationLeg(
          loanId: 'loan-regular',
          loanType: 'regular',
          scheduledAmount: 100,
          extraAmount: 0,
          totalAmount: 100,
        ),
      ],
    );

const CombinedPaymentAllocationPreview _shortCombinedPreview =
    CombinedPaymentAllocationPreview(
      status: 'short',
      requiresReview: true,
      allocationHash:
          'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
      cashReceivedAmount: 140,
      expectedTotalAmount: 150,
      shortAmount: 10,
      extraAmount: 0,
      extraChoiceRequired: false,
      regularPastDueFollowupRequired: true,
      message: 'Short preview for the updated total.',
      legs: <CombinedPaymentAllocationLeg>[
        CombinedPaymentAllocationLeg(
          loanId: 'loan-seven',
          loanType: 'seven_by_seven',
          scheduledAmount: 50,
          extraAmount: 0,
          totalAmount: 50,
        ),
        CombinedPaymentAllocationLeg(
          loanId: 'loan-regular',
          loanType: 'regular',
          scheduledAmount: 90,
          extraAmount: 0,
          totalAmount: 90,
        ),
      ],
    );

const CombinedPaymentAllocationPreview _extraChoicePreview =
    CombinedPaymentAllocationPreview(
      status: 'extra_choice_required',
      requiresReview: true,
      allocationHash:
          'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
      cashReceivedAmount: 170,
      expectedTotalAmount: 150,
      shortAmount: 0,
      extraAmount: 20,
      extraChoiceRequired: true,
      regularPastDueFollowupRequired: false,
      message: 'Choose how the true extra should be allocated.',
      legs: <CombinedPaymentAllocationLeg>[
        CombinedPaymentAllocationLeg(
          loanId: 'loan-seven',
          loanType: 'seven_by_seven',
          scheduledAmount: 50,
          extraAmount: 0,
          totalAmount: 50,
        ),
        CombinedPaymentAllocationLeg(
          loanId: 'loan-regular',
          loanType: 'regular',
          scheduledAmount: 100,
          extraAmount: 0,
          totalAmount: 100,
        ),
      ],
    );

class _DelayedCombinedRepository
    implements CombinedPaymentSubmissionRepository {
  final List<CombinedPaymentSubmissionDraft> requests =
      <CombinedPaymentSubmissionDraft>[];
  final List<Completer<CombinedPaymentAllocationPreview>> completers =
      <Completer<CombinedPaymentAllocationPreview>>[];

  @override
  Future<CombinedPaymentAllocationPreview> preview(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  ) {
    requests.add(draft);
    final completer = Completer<CombinedPaymentAllocationPreview>();
    completers.add(completer);
    return completer.future;
  }

  @override
  Future<CombinedPaymentSubmissionResult> submit(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  ) {
    throw UnimplementedError('The stale-preview test never submits.');
  }
}

class _CombinedRecordingRepository
    implements CombinedPaymentSubmissionRepository {
  final List<CombinedPaymentSubmissionDraft> previews =
      <CombinedPaymentSubmissionDraft>[];
  final List<CombinedPaymentSubmissionDraft> submissions =
      <CombinedPaymentSubmissionDraft>[];

  @override
  Future<CombinedPaymentAllocationPreview> preview(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  ) async {
    previews.add(draft);
    return _exactCombinedPreview;
  }

  @override
  Future<CombinedPaymentSubmissionResult> submit(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  ) async {
    submissions.add(draft);
    return const CombinedPaymentSubmissionResult(
      status: 'accepted',
      duplicate: false,
      idempotencyKey: 'combined-test',
      clientId: 'client-combined',
      totalAmount: 150,
      appliedTotalAmount: 150,
      unallocatedTotalAmount: 0,
      cashAllocationState: 'fully_allocated',
      legs: <CombinedPaymentLegResult>[
        CombinedPaymentLegResult(
          loanId: 'loan-seven',
          transactionId: 'tx-seven',
          receiptNumber: 'R-7',
          officialBalance: 3000,
          appliedAmount: 50,
          unallocatedAmount: 0,
          allocationState: 'fully_allocated',
          protectedResult: <String, dynamic>{},
        ),
        CombinedPaymentLegResult(
          loanId: 'loan-regular',
          transactionId: 'tx-regular',
          receiptNumber: 'R-R',
          officialBalance: 4700,
          appliedAmount: 100,
          unallocatedAmount: 0,
          allocationState: 'fully_allocated',
          protectedResult: <String, dynamic>{},
        ),
      ],
      message: 'Saved atomically.',
    );
  }
}

class _RetryCombinedRepository extends _CombinedRecordingRepository {
  final attempts = <CombinedPaymentSubmissionDraft>[];
  @override
  Future<CombinedPaymentSubmissionResult> submit(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  ) async {
    attempts.add(draft);
    if (attempts.length == 1) {
      throw const SpinaApiException(
        'Synthetic interrupted response',
        code: 'network_unavailable',
      );
    }
    return super.submit(session, draft);
  }
}

class _UnavailableCombinedRepository
    implements CombinedPaymentSubmissionRepository {
  int previewCount = 0;
  int submitCount = 0;

  @override
  Future<CombinedPaymentAllocationPreview> preview(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  ) async {
    previewCount += 1;
    throw const SpinaApiException(
      'Combined Pay is unavailable because a backend update is required.',
      statusCode: 404,
      code: 'combined_preview_unavailable',
    );
  }

  @override
  Future<CombinedPaymentSubmissionResult> submit(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  ) {
    submitCount += 1;
    throw StateError('Submit must stay disabled without a server preview.');
  }
}

class _CombinedCustodyReviewRepository
    implements CombinedPaymentSubmissionRepository {
  @override
  Future<CombinedPaymentAllocationPreview> preview(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  ) async => _exactCombinedPreview;

  @override
  Future<CombinedPaymentSubmissionResult> submit(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  ) async {
    return const CombinedPaymentSubmissionResult(
      status: 'accepted',
      duplicate: false,
      idempotencyKey: 'combined-custody-test',
      clientId: 'client-combined',
      totalAmount: 150,
      appliedTotalAmount: 140,
      unallocatedTotalAmount: 10,
      cashAllocationState: 'needs_review',
      legs: <CombinedPaymentLegResult>[
        CombinedPaymentLegResult(
          loanId: 'loan-regular',
          transactionId: 'tx-regular',
          receiptNumber: 'R-REVIEW',
          officialBalance: 0,
          appliedAmount: 140,
          unallocatedAmount: 10,
          allocationState: 'partially_allocated',
          protectedResult: <String, dynamic>{},
        ),
      ],
      message: '10.00 remains unallocated and needs custody review.',
    );
  }
}

class _RecoverableExtraChoiceRepository
    implements CombinedPaymentSubmissionRepository {
  int submitCount = 0;

  @override
  Future<CombinedPaymentAllocationPreview> preview(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  ) async => _extraChoicePreview;

  @override
  Future<CombinedPaymentSubmissionResult> submit(
    UserSession session,
    CombinedPaymentSubmissionDraft draft,
  ) {
    submitCount += 1;
    throw StateError('A true-extra preview must never auto-submit.');
  }
}
