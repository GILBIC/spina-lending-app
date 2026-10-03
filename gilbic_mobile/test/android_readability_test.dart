import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_grouping.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan.dart';
import 'package:gilbic_mobile/src/features/client/client_dashboard.dart';
import 'package:gilbic_mobile/src/features/collector/collector_client_ledger.dart';
import 'package:gilbic_mobile/src/features/collector/collector_client_tools_sheet.dart';
import 'package:gilbic_mobile/src/features/collector/collector_route_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_cash_status_card.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/android_role_fixture.dart';
import 'support/android_readability_capture.dart';
import 'support/client_fixture.dart';
import 'support/role_homes.dart';

void main() {
  for (final configuration in [(320.0, 2.0), (412.0, 1.0)]) {
    testWidgets(
      'long_identity_has_reachable_full_detail on actual route ${configuration.$1.toInt()} scale ${configuration.$2}',
      (tester) async {
        final requests = <String>[];
        final client = _longClient();
        final loader = _ReadabilityRoute(client);
        await http.runWithClient(
          () async {
            await pumpAndroidRoleFixture(
              tester,
              size: Size(configuration.$1, 640),
              textScaler: TextScaler.linear(configuration.$2),
              home: CollectorRoutePage(
                session: roleSession(AppRole.collector),
                loader: loader,
                deviceIdentityProvider: clientIdentity(),
              ),
            );
            await tester.pumpAndSettle();
            final identity = find.text(_longName);
            await tester.scrollUntilVisible(
              identity,
              180,
              scrollable: find.byType(Scrollable).first,
            );
            await Scrollable.ensureVisible(
              tester.element(identity),
              alignment: .5,
            );
            await tester.pumpAndSettle();
            expect(identity.hitTestable(), findsOneWidget);
            await tester.tap(identity);
            await tester.pumpAndSettle();
            expect(find.byType(CollectorClientToolsSheet), findsOneWidget);
            final fullName = find.descendant(
              of: find.byType(CollectorClientToolsSheet),
              matching: find.text(_longName),
            );
            _expectReadable(tester, fullName, configuration.$2);
            expect(loader.calls, 1);
            final location = find.text('Collection location');
            await tester.scrollUntilVisible(
              location,
              180,
              scrollable: find.descendant(
                of: find.byType(CollectorClientToolsSheet),
                matching: find.byType(Scrollable),
              ),
            );
            expect(location.hitTestable(), findsOneWidget);
            expect(
              requests,
              isEmpty,
              reason:
                  'Opening full identity and scrolling its tools must not submit or read private detail',
            );
            // The fixture capture boundary excludes Navigator overlays. Reuse the
            // actual loaded sheet as home to capture its production pixels directly.
            final sheet = tester.widget<CollectorClientToolsSheet>(
              find.byType(CollectorClientToolsSheet),
            );
            await tester.binding.handlePopRoute();
            await tester.pumpAndSettle();
            expect(find.byType(CollectorClientToolsSheet), findsNothing);
            await pumpAndroidRoleFixture(
              tester,
              size: Size(configuration.$1, 640),
              textScaler: TextScaler.linear(configuration.$2),
              home: Scaffold(body: sheet),
            );
            await tester.pumpAndSettle();
            await captureAndroidReadability(
              tester,
              'client-tools-${configuration.$1.toInt()}-scale-${configuration.$2}',
            );
            final balance = find.text('Balance ₱123,456,789.01');
            _expectReadable(tester, balance, configuration.$2);
            await Scrollable.ensureVisible(
              tester.element(balance),
              alignment: .3,
            );
            await tester.pumpAndSettle();
            await captureAndroidReadability(
              tester,
              'client-tools-balance-${configuration.$1.toInt()}-scale-${configuration.$2}',
            );
          },
          () => MockClient((request) async {
            requests.add('${request.method} ${request.url.path}');
            return http.Response('{}', 500);
          }),
        );
      },
    );
  }
  for (final width in [320.0, 360.0, 412.0]) {
    for (final scale in [1.0, 1.3, 2.0]) {
      final configuration = '${width.toInt()} scale $scale';
      testWidgets(
        'collector_amounts_and_pay_label_remain_legible $configuration',
        (tester) async {
          final singles = <CollectorRouteEntry>[];
          final combined = <CollectorRouteClientGroup>[];
          final client = _longClient();
          await pumpAndroidRoleFixture(
            tester,
            size: Size(width, 640),
            textScaler: TextScaler.linear(scale),
            home: Scaffold(
              body: SingleChildScrollView(
                child: CollectorClientLedgerSection(
                  group: CollectorRouteAreaGroup(
                    area: 'Area',
                    clients: [client],
                  ),
                  expandedClients: const {},
                  directPayBlockedReasonFor: (_) => null,
                  payingLoanIds: const {},
                  pendingDirectLoanIds: const {},
                  onToggleClient: (_) {},
                  onRecord: singles.add,
                  onRecordCombined: combined.add,
                  detailsBuilder: (_) => const SizedBox.shrink(),
                ),
              ),
            ),
          );
          await tester.pumpAndSettle();
          _expectReadable(tester, find.text('REG: ₱123,456,789.01'), scale);
          _expectReadable(tester, find.text('7x7: ₱21'), scale);
          _expectReadable(tester, find.text('₱123,456,810.01'), scale);
          final pay = find.byKey(const Key('record-client-long-client'));
          await tester.ensureVisible(pay);
          await tester.pumpAndSettle();
          expect(pay.hitTestable(), findsOneWidget);
          _expectReadable(tester, find.text('Pay'), scale);
          await captureAndroidReadability(tester, 'collector-$configuration');
          await tester.tap(pay);
          expect(singles, isEmpty);
          expect(combined, hasLength(1));
          expect(identical(combined.single, client), isTrue);
          expect(combined.single.loans.map((e) => e.loanId), [
            'regular-loan',
            'seven-loan',
          ]);
          expect(combined.single.loans.map((e) => e.routeRevision), [
            'r:1',
            's:1',
          ]);
          expect(tester.takeException(), isNull);
        },
      );

      testWidgets('management_metrics_grow_without_scale_down $configuration', (
        tester,
      ) async {
        await pumpAndroidRoleFixture(
          tester,
          size: Size(width, 640),
          textScaler: TextScaler.linear(scale),
          home: roleHome(AppRole.management),
        );
        await tester.pumpAndSettle();
        final metric = find.byKey(
          const Key('management-overview-metric-outstandingBalance'),
        );
        await tester.scrollUntilVisible(
          metric,
          200,
          scrollable: find.byType(Scrollable).first,
        );
        await tester.pumpAndSettle();
        final amounts = find.descendant(
          of: metric,
          matching: find.text('₱123,456,789.01'),
        );
        _expectReadable(tester, amounts, scale);
        expect(tester.getSize(metric).height, greaterThanOrEqualTo(104));
        expect(find.byType(FittedBox), findsNothing);
        await captureAndroidReadability(tester, 'management-$configuration');
        expect(tester.takeException(), isNull);
      });

      testWidgets('client_long_amount_stacks $configuration', (tester) async {
        final original = clientPortfolio();
        final repository = FakeClientLoanRepository(
          ClientLoanPortfolio(
            clientId: original.clientId,
            clientCode: original.clientCode,
            clientName: _longName,
            clientStatus: original.clientStatus,
            loans: [
              regularLoan(remainingBalance: '123456789.01'),
              original.loans.last,
            ],
          ),
        );
        await pumpAndroidRoleFixture(
          tester,
          size: Size(width, 640),
          textScaler: TextScaler.linear(scale),
          home: ClientDashboard(
            session: clientSession(),
            onSignOut: () async {},
            deviceIdentityProvider: clientIdentity(),
            loanRepository: repository,
            scheduleRepository: FakeClientScheduleRepository(),
          ),
        );
        await tester.pumpAndSettle();
        final card = find.byKey(const Key('client-home-loan-regular-loan'));
        await tester.scrollUntilVisible(
          card,
          200,
          scrollable: find.byType(Scrollable).first,
        );
        final amount = find.text('₱123,456,789.01');
        final label = find.descendant(
          of: card,
          matching: find.text('Official remaining balance'),
        );
        _expectReadable(tester, amount, scale);
        expect(
          tester.getRect(amount).top,
          greaterThanOrEqualTo(tester.getRect(label).bottom),
        );
        expect(
          find.byKey(const Key('client-home-loan-seven-by-seven-loan')),
          findsOneWidget,
        );
        expect(repository.userId, 'client-1');
        expect(repository.deviceId, 'client-home-device');
        await tester.ensureVisible(amount);
        await tester.pumpAndSettle();
        await captureAndroidReadability(tester, 'client-$configuration');
        expect(tester.takeException(), isNull);
      });

      testWidgets('long_identity_has_reachable_full_detail $configuration', (
        tester,
      ) async {
        final client = _longClient();
        final toggles = <String>[];
        final recorded = <CollectorRouteEntry>[];
        var expanded = false;
        await pumpAndroidRoleFixture(
          tester,
          size: Size(width, 640),
          textScaler: TextScaler.linear(scale),
          home: Scaffold(
            body: StatefulBuilder(
              builder: (context, setState) => SingleChildScrollView(
                child: CollectorClientLedgerSection(
                  group: CollectorRouteAreaGroup(
                    area: 'Area',
                    clients: [client],
                  ),
                  expandedClients: expanded ? {'long-client'} : {},
                  directPayBlockedReasonFor: (_) => null,
                  payingLoanIds: const {},
                  pendingDirectLoanIds: const {},
                  onToggleClient: (id) {
                    toggles.add(id);
                    setState(() => expanded = !expanded);
                  },
                  onRecord: recorded.add,
                  onRecordCombined: (_) => fail('Opening details must not pay'),
                  detailsBuilder: (entry) => Text(
                    'Authorized detail ${entry.loanId}: ${entry.routeRevision}',
                  ),
                ),
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        _expectReadable(tester, find.text(_longName), scale);
        final identity = find.byKey(const Key('route-client-long-client'));
        await tester.tap(identity, warnIfMissed: true);
        await tester.pumpAndSettle();
        expect(toggles, ['long-client']);
        expect(recorded, isEmpty);
        final balance = find.text('Balance ₱123,456,789.01');
        await tester.ensureVisible(balance);
        await tester.pumpAndSettle();
        _expectReadable(tester, balance, scale);
        await captureAndroidReadability(
          tester,
          'identity-long-balance-$configuration',
        );
        final detail = find.text('Authorized detail seven-loan: s:1');
        await tester.scrollUntilVisible(
          detail,
          200,
          scrollable: find.byType(Scrollable).first,
        );
        _expectReadable(tester, detail, scale);
        await captureAndroidReadability(
          tester,
          'identity-expanded-$configuration',
        );
      });

      testWidgets('interactive_targets_at_least_48 $configuration', (
        tester,
      ) async {
        final recorded = <CollectorRouteEntry>[];
        final client = _longClient();
        final single = CollectorRouteClientGroup(
          clientId: client.clientId,
          clientName: client.clientName,
          area: client.area,
          loans: [client.loans.first],
        );
        await pumpAndroidRoleFixture(
          tester,
          size: Size(width, 640),
          textScaler: TextScaler.linear(scale),
          home: Scaffold(
            body: SingleChildScrollView(
              child: CollectorClientLedgerSection(
                group: CollectorRouteAreaGroup(area: 'Area', clients: [single]),
                expandedClients: const {},
                directPayBlockedReasonFor: (_) => null,
                payingLoanIds: const {},
                pendingDirectLoanIds: const {},
                onToggleClient: (_) {},
                onRecord: recorded.add,
                onRecordCombined: (_) =>
                    fail('One loan must retain single payment'),
                detailsBuilder: (_) => const SizedBox.shrink(),
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        final pay = find.byKey(const Key('record-collection-regular'));
        await tester.ensureVisible(pay);
        await tester.pumpAndSettle();
        for (final target in [
          pay,
          find.byKey(const Key('route-client-long-client')),
        ]) {
          expect(tester.getSize(target).width, greaterThanOrEqualTo(48));
          expect(tester.getSize(target).height, greaterThanOrEqualTo(48));
        }
        expect(pay.hitTestable(), findsOneWidget);
        await tester.tap(pay);
        expect(recorded, hasLength(1));
        expect(identical(recorded.single, client.loans.first), isTrue);
        expect(recorded.single.loanId, 'regular-loan');
        expect(recorded.single.routeRevision, 'r:1');
        expect(tester.takeException(), isNull);
      });
    }
  }
  for (final status in [401, 403]) {
    testWidgets(
      'cash read $status explains recovery without same-token retry',
      (tester) async {
        var calls = 0;
        await http.runWithClient(
          () async {
            await pumpAndroidRoleFixture(
              tester,
              size: const Size(360, 640),
              textScaler: TextScaler.linear(1),
              home: Scaffold(
                body: CollectorCashStatusCard(
                  session: const UserSession(
                    userId: 'collector',
                    username: 'synthetic',
                    displayName: 'Synthetic',
                    role: AppRole.collector,
                    rawRole: 'Collector',
                    accessToken: 'synthetic',
                    permissions: ['remittance.view'],
                  ),
                  deviceIdentityProvider: clientIdentity(),
                  onOpenRemittance: () {},
                  onOpenRenewals: () {},
                  onOpenCashToReceive: () {},
                  onOpenCashToClient: () {},
                ),
              ),
            );
            await tester.pumpAndSettle();
            expect(
              find.textContaining(
                status == 401 ? 'Sign in again' : 'Access unavailable',
              ),
              findsOneWidget,
            );
            final refresh = tester.widget<IconButton>(
              find.byKey(const Key('collector-cash-status-refresh')),
            );
            expect(refresh.onPressed, isNull);
            expect(calls, 1);
          },
          () => MockClient((_) async {
            calls++;
            return http.Response('{"detail":"private_secret"}', status);
          }),
        );
      },
    );
  }
  testWidgets('collector_cash_long_full_amount_remains_legible', (
    tester,
  ) async {
    await http.runWithClient(
      () async {
        await pumpAndroidRoleFixture(
          tester,
          size: const Size(320, 640),
          textScaler: TextScaler.linear(2),
          home: Scaffold(
            body: ListView(
              children: [
                CollectorCashStatusCard(
                  session: const UserSession(
                    userId: 'collector',
                    username: 'synthetic',
                    displayName: 'Synthetic',
                    role: AppRole.collector,
                    rawRole: 'Collector',
                    accessToken: 'synthetic',
                    permissions: ['remittance.view'],
                  ),
                  deviceIdentityProvider: clientIdentity(),
                  onOpenRemittance: () {},
                  onOpenRenewals: () {},
                  onOpenCashToReceive: () {},
                  onOpenCashToClient: () {},
                ),
              ],
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.text('₱123,456,789.01'), findsOneWidget);
        _expectReadable(tester, find.text('₱123,456,789.01'), 2);
        await captureAndroidReadability(tester, 'collector-cash-320-scale-2.0');
        expect(tester.takeException(), isNull);
      },
      () => MockClient((request) async {
        expect(request.method, 'GET');
        return http.Response(
          jsonEncode({
            'success': true,
            'data': {
              'total_cash_held': '123456789.01',
              'assigned_area_cash_held': '123456000.00',
              'other_area_cash_held': '789.01',
              'other_area_by_collector': [],
              'ready_to_remit_amount': '123456789.01',
              'ready_to_remit_count': 1,
              'awaiting_acceptance_amount': '0.00',
              'awaiting_acceptance_count': 0,
            },
          }),
          200,
        );
      }),
    );
  });
}

const _longName =
    'Synthetic Borrower With A Long Full Name Maria Alexandra Dela Cruz Santos';

class _ReadabilityRoute implements CollectorRouteLoader {
  _ReadabilityRoute(this.client);
  final CollectorRouteClientGroup client;
  int calls = 0;
  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async {
    calls++;
    return CollectorRouteLoadResult(
      route: CollectorRoute(
        routeDate: DateTime(2026, 10, 2),
        collectorName: 'Synthetic Collector',
        areas: ['Area'],
        entries: client.loans,
        expectedTotal: 123456810.01,
      ),
      syncedAt: DateTime.utc(2026, 10, 2),
      isFromCache: false,
    );
  }
}

CollectorRouteClientGroup _longClient() => CollectorRouteClientGroup(
  clientId: 'long-client',
  clientName: _longName,
  area: 'Area',
  loans: const [
    CollectorRouteEntry(
      id: 'regular',
      clientId: 'long-client',
      loanId: 'regular-loan',
      clientName: _longName,
      area: 'Area',
      loanType: 'Regular',
      dailyAmount: 123456789.01,
      balance: 123456789.01,
      status: 'Pending',
      passCount: 0,
      routeRevision: 'r:1',
    ),
    CollectorRouteEntry(
      id: 'seven',
      clientId: 'long-client',
      loanId: 'seven-loan',
      clientName: _longName,
      area: 'Area',
      loanType: '7x7',
      dailyAmount: 21,
      balance: 3000,
      status: 'Pending',
      passCount: 0,
      routeRevision: 's:1',
      sevenBySevenMobileEnabled: true,
    ),
  ],
);

void _expectReadable(WidgetTester tester, Finder finder, double scale) {
  expect(finder, findsOneWidget);
  final paragraph = tester.renderObject<RenderParagraph>(finder);
  expect(
    MediaQuery.textScalerOf(tester.element(finder)).scale(10),
    closeTo(scale * 10, .001),
  );
  expect(paragraph.didExceedMaxLines, isFalse);
  final painter = TextPainter(
    text: paragraph.text,
    textDirection: paragraph.textDirection,
    textScaler: paragraph.textScaler,
  )..layout(maxWidth: paragraph.size.width);
  for (final line in painter.computeLineMetrics()) {
    expect(
      line.width,
      lessThanOrEqualTo(paragraph.size.width + .5),
      reason: 'Full text must stay within its available width',
    );
  }
  expect(painter.height, lessThanOrEqualTo(paragraph.size.height + .5));
  painter.dispose();
}
