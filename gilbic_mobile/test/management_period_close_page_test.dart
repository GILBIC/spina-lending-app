import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/period_close.dart';
import 'package:gilbic_mobile/src/core/management/period_close_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_period_close_page.dart';

void main() {
  testWidgets(
    'shows authoritative summary, blocker, and intersected permissions',
    (tester) async {
      final repository = _FakePeriodCloseRepository(
        overview: _overview(
          items: <PeriodCloseItem>[_readyItem, _blockedItem, _preparedItem],
          permissions: const PeriodClosePermissions(
            closePrepare: true,
            closePost: true,
          ),
        ),
      );

      await _pumpPage(tester, repository, session: _prepareOnlySession);

      expect(find.byKey(const Key('period-close-summary')), findsOneWidget);
      expect(find.text('Resolve the draft journals first.'), findsOneWidget);
      expect(
        find.byKey(
          const Key('prepare-period-11111111-1111-4111-8111-111111111111'),
        ),
        findsOneWidget,
      );
      expect(
        find.byKey(
          const Key('post-period-22222222-2222-4222-8222-222222222222'),
        ),
        findsNothing,
      );
      expect(find.text('Posting permission is not assigned.'), findsOneWidget);
    },
  );

  testWidgets(
    'prepare review cancellation writes nothing, then confirmation prepares',
    (tester) async {
      final repository = _FakePeriodCloseRepository(
        overview: _overview(items: <PeriodCloseItem>[_readyItem]),
      );
      await _pumpPage(tester, repository);

      final prepare = find.byKey(
        const Key('prepare-period-11111111-1111-4111-8111-111111111111'),
      );
      await tester.tap(prepare);
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('management-review-period-close')),
        findsOneWidget,
      );
      expect(find.text('August 2026'), findsWidgets);
      expect(find.text('2026-08-31'), findsOneWidget);
      await tester.tap(find.byKey(const Key('cancel-period-close')));
      await tester.pumpAndSettle();
      expect(repository.prepareCalls, 0);

      await tester.tap(prepare);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-period-close')));
      await tester.pumpAndSettle();

      expect(repository.prepareCalls, 1);
      expect(
        repository.preparedPeriodId,
        '11111111-1111-4111-8111-111111111111',
      );
      expect(
        find.byKey(
          const Key('post-period-11111111-1111-4111-8111-111111111111'),
        ),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'post review shows exact evidence and uncertain retry reuses token',
    (tester) async {
      final repository = _FakePeriodCloseRepository(
        overview: _overview(items: <PeriodCloseItem>[_preparedItem]),
        failFirstPost: true,
      );
      var generated = 0;
      await _pumpPage(
        tester,
        repository,
        confirmationTokenGenerator: () {
          generated += 1;
          return List<String>.filled(64, 'c').join();
        },
      );

      final post = find.byKey(
        const Key('post-period-22222222-2222-4222-8222-222222222222'),
      );
      await tester.tap(post);
      await tester.pumpAndSettle();
      expect(find.text('Net profit / loss'), findsOneWidget);
      expect(find.text('60.00'), findsOneWidget);
      expect(find.text('Retained Earnings account'), findsOneWidget);
      expect(find.text('3100'), findsOneWidget);
      expect(find.text('Temporary accounts'), findsOneWidget);
      expect(find.text('2'), findsOneWidget);
      expect(find.text(_digest), findsOneWidget);
      expect(
        find.textContaining('immutably post the retained-earnings close'),
        findsOneWidget,
      );

      await tester.tap(find.byKey(const Key('cancel-period-close')));
      await tester.pumpAndSettle();
      expect(repository.postCalls, 0);

      await tester.tap(post);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-period-close')));
      await tester.pumpAndSettle();
      expect(repository.postCalls, 1);
      expect(
        find.text('Connection interrupted after submission.'),
        findsOneWidget,
      );

      await tester.tap(post);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-period-close')));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 500));

      expect(repository.postCalls, 2);
      expect(generated, 1);
      expect(repository.confirmationTokens, hasLength(2));
      expect(repository.confirmationTokens.toSet(), hasLength(1));
      expect(repository.postedItems, everyElement(same(_preparedItem)));
      expect(find.text('Protected period close posted.'), findsOneWidget);
    },
  );

  testWidgets('server denial hides prepare even when the session permits it', (
    tester,
  ) async {
    final repository = _FakePeriodCloseRepository(
      overview: _overview(
        items: <PeriodCloseItem>[_readyItem],
        permissions: const PeriodClosePermissions(
          closePrepare: false,
          closePost: true,
        ),
      ),
    );
    await _pumpPage(tester, repository);

    expect(
      find.byKey(
        const Key('prepare-period-11111111-1111-4111-8111-111111111111'),
      ),
      findsNothing,
    );
    expect(
      find.text('Preparation permission is not assigned.'),
      findsOneWidget,
    );
  });
}

Future<void> _pumpPage(
  WidgetTester tester,
  _FakePeriodCloseRepository repository, {
  UserSession session = _fullSession,
  String Function()? confirmationTokenGenerator,
}) async {
  await tester.binding.setSurfaceSize(const Size(390, 844));
  addTearDown(() async => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(
    MaterialApp(
      home: ManagementPeriodClosePage(
        session: session,
        deviceIdentityProvider: _deviceIdentityProvider(),
        repository: repository,
        confirmationTokenGenerator: confirmationTokenGenerator,
      ),
    ),
  );
  await tester.pumpAndSettle();
}

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'management-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

const _fullSession = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>[
    'accounting.period.close.prepare',
    'accounting.period.close.post',
  ],
);

const _prepareOnlySession = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>['accounting.period.close.prepare'],
);

const _digest =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';

final _readyItem = PeriodCloseItem(
  fiscalPeriodId: '11111111-1111-4111-8111-111111111111',
  label: 'August 2026',
  startDate: DateTime(2026, 8, 1),
  endDate: DateTime(2026, 8, 31),
  fiscalPeriodStatus: 'review',
  closedByUserId: null,
  closedAt: null,
  preparationId: null,
  journalEntryId: null,
  temporaryAccountCount: null,
  netIncome: null,
  retainedEarningsBalanceBefore: null,
  closeDigest: null,
  closePostingId: null,
  closingEntryNumber: null,
  retainedEarningsBalanceAfter: null,
  closeStatus: 'ready_to_prepare',
  closeBlocker: null,
  protectedPeriodCloseEnabled: true,
  retainedEarningsCloseEnabled: true,
  closedPeriodPostingProtectionEnabled: true,
  periodReopenEnabled: false,
  automaticSourcePosting: false,
);

final _preparedItem = PeriodCloseItem(
  fiscalPeriodId: '22222222-2222-4222-8222-222222222222',
  label: 'July 2026',
  startDate: DateTime(2026, 7, 1),
  endDate: DateTime(2026, 7, 31),
  fiscalPeriodStatus: 'review',
  closedByUserId: null,
  closedAt: null,
  preparationId: '33333333-3333-4333-8333-333333333333',
  journalEntryId: '44444444-4444-4444-8444-444444444444',
  temporaryAccountCount: 2,
  netIncome: '60.00',
  retainedEarningsBalanceBefore: '1000.00',
  closeDigest: _digest,
  closePostingId: null,
  closingEntryNumber: null,
  retainedEarningsBalanceAfter: null,
  closeStatus: 'prepared_confirmation_required',
  closeBlocker: null,
  protectedPeriodCloseEnabled: true,
  retainedEarningsCloseEnabled: true,
  closedPeriodPostingProtectionEnabled: true,
  periodReopenEnabled: false,
  automaticSourcePosting: false,
);

final _blockedItem = PeriodCloseItem(
  fiscalPeriodId: '55555555-5555-4555-8555-555555555555',
  label: 'June 2026',
  startDate: DateTime(2026, 6, 1),
  endDate: DateTime(2026, 6, 30),
  fiscalPeriodStatus: 'review',
  closedByUserId: null,
  closedAt: null,
  preparationId: null,
  journalEntryId: null,
  temporaryAccountCount: null,
  netIncome: null,
  retainedEarningsBalanceBefore: null,
  closeDigest: null,
  closePostingId: null,
  closingEntryNumber: null,
  retainedEarningsBalanceAfter: null,
  closeStatus: 'blocked_draft_journals',
  closeBlocker: 'Resolve the draft journals first.',
  protectedPeriodCloseEnabled: true,
  retainedEarningsCloseEnabled: true,
  closedPeriodPostingProtectionEnabled: true,
  periodReopenEnabled: false,
  automaticSourcePosting: false,
);

PeriodCloseOverview _overview({
  required List<PeriodCloseItem> items,
  PeriodClosePermissions permissions = const PeriodClosePermissions(
    closePrepare: true,
    closePost: true,
  ),
}) {
  return PeriodCloseOverview(
    summary: const PeriodCloseSummary(
      periodCount: 3,
      readyForReviewCount: 0,
      readyToPrepareCount: 1,
      preparedCount: 1,
      protectedClosedCount: 0,
      blockedCount: 1,
      closedNetIncomeTotal: '0.00',
      protectedPeriodCloseEnabled: true,
      retainedEarningsCloseEnabled: true,
      closedPeriodPostingProtectionEnabled: true,
      periodReopenEnabled: false,
      automaticSourcePosting: false,
    ),
    items: items,
    permissions: permissions,
    notice: 'Server-authoritative close queue.',
  );
}

class _FakePeriodCloseRepository implements PeriodCloseRepository {
  _FakePeriodCloseRepository({
    required PeriodCloseOverview overview,
    this.failFirstPost = false,
  }) : _overviewValue = overview;

  PeriodCloseOverview _overviewValue;
  final bool failFirstPost;
  int prepareCalls = 0;
  int postCalls = 0;
  String? preparedPeriodId;
  final List<String> confirmationTokens = <String>[];
  final List<PeriodCloseItem> postedItems = <PeriodCloseItem>[];

  @override
  Future<PeriodCloseOverview> load(
    UserSession session, {
    required String deviceId,
    String status = 'all',
  }) async {
    expect(deviceId, 'management-device');
    return _overviewValue;
  }

  @override
  Future<PeriodCloseItem> prepare(
    UserSession session, {
    required String deviceId,
    required String fiscalPeriodId,
  }) async {
    prepareCalls += 1;
    preparedPeriodId = fiscalPeriodId;
    final prepared = PeriodCloseItem(
      fiscalPeriodId: fiscalPeriodId,
      label: _readyItem.label,
      startDate: _readyItem.startDate,
      endDate: _readyItem.endDate,
      fiscalPeriodStatus: 'review',
      closedByUserId: null,
      closedAt: null,
      preparationId: '66666666-6666-4666-8666-666666666666',
      journalEntryId: '77777777-7777-4777-8777-777777777777',
      temporaryAccountCount: 2,
      netIncome: '60.00',
      retainedEarningsBalanceBefore: '1000.00',
      closeDigest: _digest,
      closePostingId: null,
      closingEntryNumber: null,
      retainedEarningsBalanceAfter: null,
      closeStatus: 'prepared_confirmation_required',
      closeBlocker: null,
      protectedPeriodCloseEnabled: true,
      retainedEarningsCloseEnabled: true,
      closedPeriodPostingProtectionEnabled: true,
      periodReopenEnabled: false,
      automaticSourcePosting: false,
    );
    _overviewValue = _overview(items: <PeriodCloseItem>[prepared]);
    return prepared;
  }

  @override
  Future<PeriodCloseItem> post(
    UserSession session, {
    required String deviceId,
    required PeriodCloseItem item,
    required String confirmationToken,
  }) async {
    postCalls += 1;
    confirmationTokens.add(confirmationToken);
    postedItems.add(item);
    if (failFirstPost && postCalls == 1) {
      throw const SpinaApiException(
        'Connection interrupted after submission.',
        code: 'network_unavailable',
      );
    }
    return PeriodCloseItem(
      fiscalPeriodId: item.fiscalPeriodId,
      label: item.label,
      startDate: item.startDate,
      endDate: item.endDate,
      fiscalPeriodStatus: 'closed',
      closedByUserId: '88888888-8888-4888-8888-888888888888',
      closedAt: DateTime.utc(2026, 8, 30, 8),
      preparationId: item.preparationId,
      journalEntryId: item.journalEntryId,
      temporaryAccountCount: item.temporaryAccountCount,
      netIncome: item.netIncome,
      retainedEarningsBalanceBefore: item.retainedEarningsBalanceBefore,
      closeDigest: item.closeDigest,
      closePostingId: '99999999-9999-4999-8999-999999999999',
      closingEntryNumber: 'GJ-2026-0099',
      retainedEarningsBalanceAfter: '1060.00',
      closeStatus: 'closed_protected',
      closeBlocker: null,
      protectedPeriodCloseEnabled: true,
      retainedEarningsCloseEnabled: true,
      closedPeriodPostingProtectionEnabled: true,
      periodReopenEnabled: false,
      automaticSourcePosting: false,
    );
  }
}
