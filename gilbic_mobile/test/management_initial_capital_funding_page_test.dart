import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/initial_capital_funding.dart';
import 'package:gilbic_mobile/src/core/management/initial_capital_funding_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_initial_capital_funding_page.dart';

void main() {
  testWidgets('shows compact server queue and intersects exact permissions', (
    tester,
  ) async {
    final repository = _FakeRepository(
      initialItems: <InitialCapitalFundingItem>[
        _item('evidence_ready'),
        _item('prepared_not_posted', suffix: '3'),
        _item('blocked_no_open_period', suffix: '4'),
      ],
    );
    await _pump(tester, repository, session: _prepareOnlySession);

    expect(find.byKey(const Key('initial-capital-summary')), findsOneWidget);
    expect(find.text('Total evidence: 3'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('Funding date is not inside an open accounting period.'),
      200,
    );
    expect(
      find.text('Funding date is not inside an open accounting period.'),
      findsOneWidget,
    );
    expect(
      find.byKey(
        const Key(
          'prepare-initial-capital-22222222-2222-4222-8222-222222222222',
        ),
      ),
      findsOneWidget,
    );
    expect(find.text('Posting permission is not assigned.'), findsOneWidget);
    expect(
      find.byKey(const Key('record-initial-capital-evidence')),
      findsNothing,
    );
  });

  testWidgets('records evidence through review and reloads authority', (
    tester,
  ) async {
    final repository = _FakeRepository(
      initialItems: const <InitialCapitalFundingItem>[],
    );
    await _pump(
      tester,
      repository,
      uuidGenerator: () => '11111111-1111-4111-8111-111111111111',
      now: () => DateTime(2026, 8, 30),
    );

    await tester.tap(find.byKey(const Key('record-initial-capital-evidence')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('initial-capital-amount')),
      '250000.00',
    );
    await tester.enterText(
      find.byKey(const Key('initial-capital-source')),
      'Bank deposit slip',
    );
    await tester.enterText(
      find.byKey(const Key('initial-capital-reference')),
      'BPI-2026-0001',
    );
    await tester.enterText(
      find.byKey(const Key('initial-capital-digest')),
      _evidenceDigest,
    );
    await tester.enterText(
      find.byKey(const Key('initial-capital-note')),
      'Verified owner funding deposited into the selected company account.',
    );
    await tester.tap(find.byKey(const Key('review-initial-capital-evidence')));
    await tester.pumpAndSettle();

    expect(
      find.byKey(const Key('management-review-initial-capital')),
      findsOneWidget,
    );
    expect(find.text('250000.00'), findsOneWidget);
    expect(find.text('1000 Cash - Office'), findsAtLeastNWidgets(1));
    await tester.tap(find.byKey(const Key('confirm-initial-capital')));
    await tester.pumpAndSettle();

    expect(repository.recordCalls, 1);
    expect(
      repository.idempotencyKeys.single,
      '11111111-1111-4111-8111-111111111111',
    );
    expect(repository.lastDraft?.fundingDate, '2026-08-30');
    expect(repository.loadCalls, 2);
  });

  testWidgets(
    'post review shows exact coordinates and uncertain retry reuses token',
    (tester) async {
      final repository = _FakeRepository(
        initialItems: <InitialCapitalFundingItem>[_item('prepared_not_posted')],
        failFirstPost: true,
      );
      var generated = 0;
      await _pump(
        tester,
        repository,
        tokenGenerator: () {
          generated += 1;
          return _confirmationToken;
        },
      );
      final post = find.byKey(
        const Key('post-initial-capital-22222222-2222-4222-8222-222222222222'),
      );

      await tester.tap(post);
      await tester.pumpAndSettle();
      expect(find.text('Debit account'), findsOneWidget);
      expect(find.text('1000 Cash - Office'), findsAtLeastNWidgets(1));
      expect(find.text('Credit account'), findsOneWidget);
      expect(find.text('3000 Capital'), findsOneWidget);
      expect(find.text('2026-08-30'), findsAtLeastNWidgets(1));
      await tester.tap(find.byKey(const Key('confirm-initial-capital')));
      await tester.pumpAndSettle();
      expect(
        find.text('Connection interrupted after submission.'),
        findsOneWidget,
      );

      await tester.tap(post);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-initial-capital')));
      await tester.pumpAndSettle();

      expect(repository.postCalls, 2);
      expect(repository.tokens.toSet(), hasLength(1));
      expect(generated, 1);
      expect(repository.loadCalls, 2);
      expect(find.text('Posted'), findsOneWidget);
    },
  );

  testWidgets(
    'server denial hides evidence recording even when session permits',
    (tester) async {
      final repository = _FakeRepository(
        initialItems: const <InitialCapitalFundingItem>[],
        permissions: const InitialCapitalFundingPermissions(
          evidenceRecord: false,
          prepare: true,
          post: true,
        ),
      );
      await _pump(tester, repository);

      expect(
        find.byKey(const Key('record-initial-capital-evidence')),
        findsNothing,
      );
      expect(
        find.text('Evidence-record permission is not assigned.'),
        findsOneWidget,
      );
    },
  );
}

Future<void> _pump(
  WidgetTester tester,
  _FakeRepository repository, {
  UserSession session = _session,
  String Function()? uuidGenerator,
  String Function()? tokenGenerator,
  DateTime Function()? now,
}) async {
  await tester.binding.setSurfaceSize(const Size(390, 844));
  addTearDown(() async => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(
    MaterialApp(
      home: ManagementInitialCapitalFundingPage(
        session: session,
        deviceIdentityProvider: _deviceProvider(),
        repository: repository,
        uuidGenerator: uuidGenerator,
        confirmationTokenGenerator: tokenGenerator,
        now: now,
      ),
    ),
  );
  await tester.pumpAndSettle();
}

DeviceIdentityProvider _deviceProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'management-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

class _FakeRepository implements InitialCapitalFundingRepository {
  _FakeRepository({
    required this.initialItems,
    this.permissions = const InitialCapitalFundingPermissions(
      evidenceRecord: true,
      prepare: true,
      post: true,
    ),
    this.failFirstPost = false,
  });

  final List<InitialCapitalFundingItem> initialItems;
  final InitialCapitalFundingPermissions permissions;
  final bool failFirstPost;
  int loadCalls = 0;
  int recordCalls = 0;
  int prepareCalls = 0;
  int postCalls = 0;
  InitialCapitalEvidenceDraft? lastDraft;
  final List<String> idempotencyKeys = <String>[];
  final List<String> tokens = <String>[];

  @override
  Future<InitialCapitalFundingOverview> load(
    UserSession session, {
    required String deviceId,
    int limit = 100,
    int offset = 0,
  }) async {
    loadCalls += 1;
    final items = postCalls >= 2
        ? <InitialCapitalFundingItem>[_item('posted')]
        : recordCalls > 0
        ? <InitialCapitalFundingItem>[_item('evidence_ready')]
        : prepareCalls > 0
        ? <InitialCapitalFundingItem>[_item('prepared_not_posted')]
        : initialItems;
    return InitialCapitalFundingOverview(
      items: items,
      summary: InitialCapitalFundingSummary(
        evidenceCount: items.length,
        evidenceReadyCount: items.where((item) => item.isEvidenceReady).length,
        preparedNotPostedCount: items.where((item) => item.isPrepared).length,
        postedCount: items.where((item) => item.isPosted).length,
        blockedNoOpenPeriodCount: items
            .where((item) => item.accountingStatus == 'blocked_no_open_period')
            .length,
        totalAmount: items.isEmpty ? '0.00' : '250000.00',
        postedAmount: items.any((item) => item.isPosted) ? '250000.00' : '0.00',
      ),
      cashAccounts: const <InitialCapitalCashAccount>[
        InitialCapitalCashAccount(code: '1000', name: 'Cash - Office'),
      ],
      permissions: permissions,
      limit: limit,
      offset: offset,
      protectedInitialCapitalFundingEnabled: true,
      syntheticOpeningBalanceRequired: false,
      automaticSourcePosting: false,
      notice: 'Exact retained funding evidence is required.',
    );
  }

  @override
  Future<InitialCapitalFundingItem> recordEvidence(
    UserSession session, {
    required String deviceId,
    required InitialCapitalEvidenceDraft draft,
    required String idempotencyKey,
  }) async {
    recordCalls += 1;
    lastDraft = draft;
    idempotencyKeys.add(idempotencyKey);
    return _item('evidence_ready');
  }

  @override
  Future<InitialCapitalFundingItem> prepare(
    UserSession session, {
    required String deviceId,
    required InitialCapitalFundingItem item,
  }) async {
    prepareCalls += 1;
    return _item('prepared_not_posted');
  }

  @override
  Future<InitialCapitalFundingItem> post(
    UserSession session, {
    required String deviceId,
    required InitialCapitalFundingItem item,
    required String confirmationToken,
  }) async {
    postCalls += 1;
    tokens.add(confirmationToken);
    if (failFirstPost && postCalls == 1) {
      throw const SpinaApiException(
        'Connection interrupted after submission.',
        code: 'network_unavailable',
      );
    }
    return _item('posted');
  }
}

InitialCapitalFundingItem _item(String status, {String suffix = '2'}) {
  final prepared = status == 'prepared_not_posted' || status == 'posted';
  final posted = status == 'posted';
  return InitialCapitalFundingItem.fromPayload(<String, Object?>{
    'evidence_id': '22222222-2222-4222-8222-22222222222$suffix',
    'funding_date': '2026-08-30',
    'amount': '250000.00',
    'cash_account_code': '1000',
    'cash_account_name': 'Cash - Office',
    'capital_account_code': '3000',
    'evidence_source': 'Bank deposit slip',
    'evidence_reference': 'BPI-2026-0001',
    'evidence_digest': _evidenceDigest,
    'evidence_note':
        'Verified owner funding deposited into the selected company account.',
    'recorded_by_user_id': '44444444-4444-4444-8444-444444444444',
    'recorded_at': '2026-08-30T02:00:00+00:00',
    'journal_entry_id': prepared
        ? '55555555-5555-4555-8555-555555555555'
        : null,
    'journal_status': prepared ? (posted ? 'posted' : 'draft') : null,
    'entry_number': posted ? 'GJ-2026-0010' : null,
    'fiscal_period_id': prepared
        ? '33333333-3333-4333-8333-333333333333'
        : null,
    'prepared_by_user_id': prepared
        ? '66666666-6666-4666-8666-666666666666'
        : null,
    'prepared_at': prepared ? '2026-08-30T02:10:00+00:00' : null,
    'confirmation_digest': posted ? _confirmationDigest : null,
    'posted_by_user_id': posted ? '77777777-7777-4777-8777-777777777777' : null,
    'posted_at': posted ? '2026-08-30T02:20:00+00:00' : null,
    'accounting_status': status,
    'accounting_blocker': status == 'blocked_no_open_period'
        ? 'Funding date is not inside an open accounting period.'
        : null,
    'protected_initial_capital_funding_enabled': true,
    'synthetic_opening_balance_required': false,
    'automatic_source_posting': false,
  });
}

const _evidenceDigest =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const _confirmationToken =
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
const _confirmationDigest =
    'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc';

const _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>[
    'accounting.initial_capital.evidence.record',
    'accounting.initial_capital.prepare',
    'accounting.initial_capital.post',
  ],
);

const _prepareOnlySession = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>['accounting.initial_capital.prepare'],
);
