import 'support/android_workflow_capture.dart';
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_grouping.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_loan.dart';
import 'package:gilbic_mobile/src/core/management/management_loan_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collector_client_ledger.dart';
import 'package:gilbic_mobile/src/features/management/management_loan_portfolio_page.dart';
import 'package:gilbic_mobile/src/features/shared/spina_status.dart';
import 'support/android_role_fixture.dart';

void main() {
  for (final (size, scale) in [
    (const Size(320, 640), 2.0),
    (const Size(412, 915), 1.0),
  ]) {
    for (final (rawStatus, overdue, label, tone) in [
      ('future_state', false, 'Future_state', SpinaStatusTone.information),
      ('active', false, 'Active', SpinaStatusTone.information),
      ('active', true, 'Overdue', SpinaStatusTone.attention),
    ]) {
      testWidgets(
        'Management status $rawStatus overdue=$overdue at ${size.width}/$scale',
        (tester) async {
          final repository = _StatusPortfolioRepository(rawStatus, overdue);
          final handle = tester.ensureSemantics();
          await pumpAndroidRoleFixture(
            tester,
            size: size,
            textScaler: TextScaler.linear(scale),
            home: ManagementLoanPortfolioPage(
              session: const UserSession(
                userId: 'management-1',
                username: 'manager',
                displayName: 'Management',
                role: AppRole.management,
                rawRole: 'Management',
                accessToken: 'test-token',
                permissions: [],
              ),
              deviceIdentityProvider: DeviceIdentityProvider(
                store: MemoryDeviceIdentityStore()
                  ..value = 'status-test-device',
                platformResolver: () => 'android',
                appVersionResolver: () async => 'test',
              ),
              repository: repository,
            ),
          );
          await tester.pumpAndSettle();
          final card = find.byKey(const Key('management-loan-exact-loan'));
          await tester.scrollUntilVisible(
            card,
            250,
            scrollable: find.byType(Scrollable).first,
          );
          await tester.pumpAndSettle();
          expect(
            find.byIcon(Icons.check_circle),
            findsNothing,
            reason:
                'A non-overdue or unknown loan status must not claim success.',
          );
          final status = find.descendant(
            of: card,
            matching: find.byType(SpinaStatusLabel),
          );
          expect(status, findsOneWidget);
          if (scale == 2) {
            final name = find.descendant(
              of: card,
              matching: find.text(repository.loan.clientName),
            );
            expect(
              tester.getSize(name).width,
              greaterThanOrEqualTo(size.width * .65),
              reason: 'Large-text loan identity uses a readable header width',
            );
          }
          expect(tester.widget<SpinaStatusLabel>(status).label, label);
          expect(tester.widget<SpinaStatusLabel>(status).tone, tone);
          expect(repository.calls, 1);
          expect(repository.requestedStatus, 'active');
          expect(repository.requestedDeviceId, 'status-test-device');
          expect(repository.loan.loanStatus, rawStatus);
          expect(repository.loan.loanId, 'exact-loan');
          expect(repository.loan.stateVersion, 7);
          await tester.tap(status);
          await tester.pumpAndSettle();
          expect(repository.calls, 1);
          expect(tester.takeException(), isNull);
          await captureAndroidWorkflowScroll(
            tester,
            'M3-$rawStatus-overdue-$overdue-${size.width}-$scale',
          );
          handle.dispose();
        },
      );
    }
  }
  for (final note in [
    'Not paid through GCash',
    'Do not use GCash',
    'GCash tomorrow',
  ]) {
    testWidgets('note_mentions_never_verify_gcash: $note', (tester) async {
      final handle = tester.ensureSemantics();
      final entry = CollectorRouteEntry(
        id: 'entry',
        clientId: 'client',
        loanId: 'loan',
        clientName: 'Client',
        area: 'Area',
        loanType: 'Regular',
        dailyAmount: 100,
        balance: 1000,
        status: 'future_state',
        note: note,
        passCount: 0,
      );
      var submitted = 0;
      await pumpAndroidRoleFixture(
        tester,
        size: const Size(412, 915),
        textScaler: TextScaler.linear(1),
        home: Scaffold(
          body: CollectorClientLedgerSection(
            group: CollectorRouteAreaGroup(
              area: 'Area',
              clients: [
                CollectorRouteClientGroup(
                  clientId: 'client',
                  clientName: 'Client',
                  area: 'Area',
                  loans: [entry],
                ),
              ],
            ),
            expandedClients: const {'client'},
            directPayBlockedReasonFor: (_) => null,
            payingLoanIds: const {},
            pendingDirectLoanIds: const {},
            onToggleClient: (_) {},
            onRecord: (_) => submitted++,
            onRecordCombined: (_) => submitted++,
            detailsBuilder: (value) => Text(value.note),
          ),
        ),
      );
      expect(find.text('GCASH'), findsNothing);
      expect(find.text('NOTE'), findsOneWidget);
      expect(find.text(note), findsOneWidget);
      expect(find.text('NOT COLLECTED'), findsOneWidget);
      expect(submitted, 0);
      expect(tester.takeException(), isNull);
      await expectLater(tester, meetsGuideline(textContrastGuideline));
      handle.dispose();
    });
  }

  testWidgets('domain_states_remain_distinct and unknown is never success', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    final cases = [
      (_entry(), 'NOT COLLECTED', SpinaStatusTone.attention),
      (_entry(processed: true), 'COLLECTED', SpinaStatusTone.success),
      (
        _entry(processed: true, locked: true),
        'REMITTED',
        SpinaStatusTone.success,
      ),
      (_entry(entryType: 'pass'), 'UNABLE', SpinaStatusTone.attention),
      (
        _entry(processed: true, contractReady: true, unpaid: 20),
        'LACKING',
        SpinaStatusTone.attention,
      ),
    ];
    for (final (entry, label, tone) in cases) {
      final original = entry.toJson();
      await _pumpLedger(tester, [entry]);
      final status = find.byWidgetPredicate(
        (widget) => widget is SpinaStatusLabel && widget.label == label,
      );
      expect(status, findsOneWidget);
      expect(tester.widget<SpinaStatusLabel>(status).tone, tone);
      expect(find.text('Cash received'), findsNothing);
      expect(find.text('GCASH'), findsNothing);
      expect(entry.toJson(), original);
      expect(tester.takeException(), isNull);
    }
    handle.dispose();
  });

  testWidgets('status_label_respects_text_scaling and exposes full meaning', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    const statuses = [
      (
        'Payment recorded; cash receipt is separate',
        SpinaStatusTone.success,
        Icons.check_circle_outline,
      ),
      (
        'Saved on device; awaiting server acceptance',
        SpinaStatusTone.attention,
        Icons.pending_outlined,
      ),
      (
        'Access unavailable; no payment conclusion',
        SpinaStatusTone.blocked,
        Icons.block_outlined,
      ),
      (
        'Future status; details remain available',
        SpinaStatusTone.information,
        Icons.info_outline,
      ),
    ];
    await pumpAndroidRoleFixture(
      tester,
      size: const Size(320, 640),
      textScaler: TextScaler.linear(2),
      home: Scaffold(
        body: ListView(
          children: [
            for (final (label, tone, _) in statuses)
              SpinaStatusLabel(label: label, tone: tone),
          ],
        ),
      ),
    );
    for (final (label, _, icon) in statuses) {
      final text = find.text(label);
      final context = tester.element(text);
      final semantics = tester.getSemantics(text).getSemanticsData();
      expect(semantics.label, label);
      expect(semantics.hasAction(SemanticsAction.tap), isFalse);
      expect(find.byIcon(icon), findsOneWidget);
      expect(MediaQuery.textScalerOf(context).scale(14), 28);
      expect(
        tester.widget<Text>(text).style!.fontSize,
        Theme.of(context).textTheme.labelMedium!.fontSize,
      );
      expect(tester.widget<Text>(text).maxLines, isNull);
      expect(tester.widget<Text>(text).overflow, isNull);
    }
    expect(find.byType(FilledButton), findsNothing);
    expect(tester.takeException(), isNull);
    await expectLater(tester, meetsGuideline(textContrastGuideline));
    handle.dispose();
  });

  for (final combined in [false, true]) {
    testWidgets(
      'status_decoration_does_not_submit; exact ${combined ? 'combined' : 'single'} Pay callback',
      (tester) async {
        final entries = [
          _entry(note: 'Not paid through GCash'),
          if (combined)
            _entry(id: 'seven', loanId: 'loan-seven', loanType: '7x7'),
        ];
        final original = entries.map((entry) => entry.toJson()).toList();
        final singleCalls = <CollectorRouteEntry>[];
        final combinedCalls = <CollectorRouteClientGroup>[];
        var opened = 0;
        await _pumpLedger(
          tester,
          entries,
          onToggle: () => opened++,
          onRecord: singleCalls.add,
          onCombined: combinedCalls.add,
        );
        await tester.tap(find.text('NOTE'));
        await tester.pump();
        expect(opened, 1);
        expect(singleCalls, isEmpty);
        expect(combinedCalls, isEmpty);
        await tester.ensureVisible(find.text('Pay'));
        await tester.tap(find.text('Pay'));
        await tester.pump();
        if (combined) {
          expect(singleCalls, isEmpty);
          expect(combinedCalls, hasLength(1));
          expect(combinedCalls.single.clientId, 'client');
          expect(combinedCalls.single.loans.map((entry) => entry.loanId), [
            'loan',
            'loan-seven',
          ]);
          for (var index = 0; index < entries.length; index++) {
            expect(
              identical(combinedCalls.single.loans[index], entries[index]),
              isTrue,
            );
          }
        } else {
          expect(combinedCalls, isEmpty);
          expect(singleCalls, hasLength(1));
          expect(identical(singleCalls.single, entries.single), isTrue);
          expect(singleCalls.single.loanId, 'loan');
        }
        expect(entries.map((entry) => entry.toJson()).toList(), original);
        expect(tester.takeException(), isNull);
      },
    );
  }
}

CollectorRouteEntry _entry({
  String id = 'entry',
  String loanId = 'loan',
  String loanType = 'Regular',
  String note = '',
  bool processed = false,
  bool locked = false,
  String entryType = '',
  bool contractReady = false,
  double unpaid = 0,
}) => CollectorRouteEntry(
  id: id,
  clientId: 'client',
  loanId: loanId,
  clientName: 'Client',
  area: 'Area',
  loanType: loanType,
  dailyAmount: 100,
  balance: 1000,
  status: 'future_state',
  note: note,
  passCount: 0,
  processedToday: processed,
  todayIsLocked: locked,
  todayEntryType: entryType,
  contractCollectionReady: contractReady,
  contractTodayScheduledAmount: contractReady ? 100 : 0,
  contractTodayUnpaidAmount: unpaid,
  routeRevision: 'exact-$loanId-v7',
  sevenBySevenMobileEnabled: true,
);

Future<void> _pumpLedger(
  WidgetTester tester,
  List<CollectorRouteEntry> entries, {
  VoidCallback? onToggle,
  ValueChanged<CollectorRouteEntry>? onRecord,
  ValueChanged<CollectorRouteClientGroup>? onCombined,
}) => pumpAndroidRoleFixture(
  tester,
  size: const Size(320, 640),
  textScaler: TextScaler.linear(2),
  home: Scaffold(
    body: SingleChildScrollView(
      child: CollectorClientLedgerSection(
        group: CollectorRouteAreaGroup(
          area: 'Area',
          clients: [
            CollectorRouteClientGroup(
              clientId: 'client',
              clientName: 'Client',
              area: 'Area',
              loans: entries,
            ),
          ],
        ),
        expandedClients: const {},
        directPayBlockedReasonFor: (_) => null,
        payingLoanIds: const {},
        pendingDirectLoanIds: const {},
        onToggleClient: (_) => onToggle?.call(),
        onRecord: onRecord ?? (_) {},
        onRecordCombined: onCombined ?? (_) {},
        detailsBuilder: (entry) => Text(entry.note),
      ),
    ),
  ),
);

class _StatusPortfolioRepository implements ManagementLoanRepository {
  _StatusPortfolioRepository(String status, bool overdue)
    : loan = ManagementLoanItem.fromPayload({
        'loan_id': 'exact-loan',
        'loan_number': 'SYNTHETIC-STATUS-1',
        'client_id': 'exact-client',
        'client_code': 'SYNTHETIC-CLIENT-1',
        'client_name': 'Synthetic Status Client',
        'client_status': 'active',
        'loan_type_name': 'Regular',
        'calculation_mode': 'fixed_daily',
        'principal': '1000.00',
        'daily_amount': '10.00',
        'remaining_balance': '900.00',
        'paid_amount': '100.00',
        'paid_percent': 10,
        'loan_status': status,
        'pass_count': 0,
        'payment_count': 10,
        'state_version': 7,
        'is_overdue': overdue,
      });
  final ManagementLoanItem loan;
  int calls = 0;
  String? requestedStatus;
  String? requestedDeviceId;

  @override
  Future<ManagementLoanPortfolio> loadPortfolio(
    UserSession session, {
    required String deviceId,
    required String query,
    required String status,
  }) async {
    calls++;
    requestedStatus = status;
    requestedDeviceId = deviceId;
    return ManagementLoanPortfolio(
      summary: const ManagementLoanSummary(
        activeLoanCount: 1,
        activeClientCount: 1,
        activePrincipalTotal: 1000,
        activeRemainingTotal: 900,
        overdueActiveCount: 0,
        activeSevenBySevenCount: 0,
        approvedRenewalCount: 0,
      ),
      loans: [loan],
      notice: 'Loan Management is view-only in mobile.',
    );
  }
}
