import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/ecl_allowance_posting.dart';
import 'package:gilbic_mobile/src/core/management/ecl_allowance_posting_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_ecl_allowance_posting_page.dart';

void main() {
  testWidgets('shows server states and intersects exact session permissions', (
    tester,
  ) async {
    final repository = _FakeRepository(
      initialItems: <EclAllowancePostingItem>[
        _item('preparation_required'),
        _item('preparation_blocked', loanSuffix: '2'),
        _item('posting_ready', loanSuffix: '3'),
      ],
    );
    await _pump(tester, repository, session: _prepareOnlySession);

    expect(find.byKey(const Key('ecl-allowance-summary')), findsOneWidget);
    expect(
      find.text('Preparation blocked — verify open period and accounts'),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('prepare-ecl-22222222-2222-4222-8222-222222222222')),
      findsOneWidget,
    );
    expect(find.text('Posting permission is not assigned.'), findsOneWidget);
    expect(
      find.byKey(const Key('post-ecl-77777777-7777-4777-8777-777777777777')),
      findsNothing,
    );
  });

  testWidgets('prepare cancellation writes nothing and success reloads queue', (
    tester,
  ) async {
    final repository = _FakeRepository(
      initialItems: <EclAllowancePostingItem>[_item('preparation_required')],
    );
    await _pump(tester, repository);
    final prepare = find.byKey(
      const Key('prepare-ecl-22222222-2222-4222-8222-222222222222'),
    );

    await tester.tap(prepare);
    await tester.pumpAndSettle();
    expect(
      find.byKey(const Key('management-review-ecl-allowance')),
      findsOneWidget,
    );
    expect(find.text('125.50'), findsOneWidget);
    expect(find.text(_calculationDigest), findsOneWidget);
    await tester.tap(find.byKey(const Key('cancel-ecl-allowance')));
    await tester.pumpAndSettle();
    expect(repository.prepareCalls, 0);

    await tester.tap(prepare);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('confirm-ecl-allowance')));
    await tester.pumpAndSettle();

    expect(repository.prepareCalls, 1);
    expect(repository.loadCalls, 2);
    expect(
      find.byKey(const Key('post-ecl-77777777-7777-4777-8777-777777777777')),
      findsOneWidget,
    );
  });

  testWidgets('post shows exact evidence and uncertain retry reuses token', (
    tester,
  ) async {
    final repository = _FakeRepository(
      initialItems: <EclAllowancePostingItem>[_item('posting_ready')],
      failFirstPost: true,
    );
    var generated = 0;
    await _pump(
      tester,
      repository,
      reviewTokenGenerator: () {
        generated += 1;
        return List<String>.filled(64, 'e').join();
      },
    );
    final post = find.byKey(
      const Key('post-ecl-77777777-7777-4777-8777-777777777777'),
    );

    await tester.tap(post);
    await tester.pumpAndSettle();
    expect(find.text('Allowance amount'), findsOneWidget);
    expect(find.text('125.50'), findsOneWidget);
    expect(find.text('Credit Loss Expense'), findsOneWidget);
    expect(find.text('5000'), findsOneWidget);
    expect(find.text('ECL Allowance'), findsOneWidget);
    expect(find.text('1190'), findsOneWidget);
    expect(find.text(_preparationDigest), findsOneWidget);
    expect(
      find.textContaining('immutably post the initial ECL allowance'),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const Key('confirm-ecl-allowance')));
    await tester.pumpAndSettle();
    expect(repository.postCalls, 1);
    expect(
      find.text('Connection interrupted after submission.'),
      findsOneWidget,
    );

    await tester.tap(post);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('confirm-ecl-allowance')));
    await tester.pumpAndSettle();

    expect(repository.postCalls, 2);
    expect(repository.tokens.toSet(), hasLength(1));
    expect(generated, 1);
    expect(repository.loadCalls, 2);
    expect(find.text('Posted — current protected allowance'), findsOneWidget);
  });

  testWidgets('server denial hides prepare even when session permits it', (
    tester,
  ) async {
    final repository = _FakeRepository(
      initialItems: <EclAllowancePostingItem>[_item('preparation_required')],
      permissions: const EclAllowancePostingPermissions(
        prepare: false,
        post: true,
      ),
    );
    await _pump(tester, repository);

    expect(
      find.text('Preparation permission is not assigned.'),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('prepare-ecl-22222222-2222-4222-8222-222222222222')),
      findsNothing,
    );
  });
}

Future<void> _pump(
  WidgetTester tester,
  _FakeRepository repository, {
  UserSession session = _session,
  String Function()? reviewTokenGenerator,
}) async {
  await tester.binding.setSurfaceSize(const Size(390, 844));
  addTearDown(() async => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(
    MaterialApp(
      home: ManagementEclAllowancePostingPage(
        session: session,
        deviceIdentityProvider: _deviceProvider(),
        repository: repository,
        reviewTokenGenerator: reviewTokenGenerator,
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

class _FakeRepository implements EclAllowancePostingRepository {
  _FakeRepository({
    required this.initialItems,
    this.permissions = const EclAllowancePostingPermissions(
      prepare: true,
      post: true,
    ),
    this.failFirstPost = false,
  });

  final List<EclAllowancePostingItem> initialItems;
  final EclAllowancePostingPermissions permissions;
  final bool failFirstPost;
  int loadCalls = 0;
  int prepareCalls = 0;
  int postCalls = 0;
  final List<String> tokens = <String>[];

  @override
  Future<EclAllowancePostingOverview> load(
    UserSession session, {
    required String deviceId,
    String status = 'all',
    int limit = 100,
    int offset = 0,
  }) async {
    loadCalls += 1;
    final items = postCalls >= 2
        ? <EclAllowancePostingItem>[_item('posted_current')]
        : prepareCalls > 0
        ? <EclAllowancePostingItem>[_item('posting_ready')]
        : initialItems;
    return EclAllowancePostingOverview(
      summary: _summary,
      items: items,
      permissions: permissions,
      notice: 'Exact A4 server queue.',
      filter: status,
      limit: limit,
      offset: offset,
    );
  }

  @override
  Future<EclAllowanceActionReceipt> prepare(
    UserSession session, {
    required String deviceId,
    required EclAllowancePostingItem item,
    required String reviewToken,
  }) async {
    prepareCalls += 1;
    tokens.add(reviewToken);
    return const EclAllowanceActionReceipt(
      id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      automaticSourcePosting: false,
    );
  }

  @override
  Future<EclAllowanceActionReceipt> post(
    UserSession session, {
    required String deviceId,
    required EclAllowancePostingItem item,
    required String reviewToken,
  }) async {
    postCalls += 1;
    tokens.add(reviewToken);
    if (failFirstPost && postCalls == 1) {
      throw const SpinaApiException(
        'Connection interrupted after submission.',
        code: 'network_unavailable',
      );
    }
    return const EclAllowanceActionReceipt(
      id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
      automaticSourcePosting: false,
    );
  }
}

EclAllowancePostingItem _item(String status, {String loanSuffix = '1'}) {
  final prepared = status == 'posting_ready' || status == 'posted_current';
  final posted = status == 'posted_current';
  return EclAllowancePostingItem.fromPayload(<String, Object?>{
    'loan_id': '11111111-1111-4111-8111-11111111111$loanSuffix',
    'loan_number': 'LN-2026-000$loanSuffix',
    'loan_status': 'active',
    'loan_type_code': 'regular',
    'loan_type_name': 'Regular',
    'calculation_mode': 'fixed_daily',
    'measurement_id': '22222222-2222-4222-8222-222222222222',
    'measurement_version': 3,
    'measurement_date': '2026-08-31',
    'loss_horizon': 'lifetime',
    'calculation_digest': _calculationDigest,
    'measurement_status': 'measured_read_only',
    'authoritative_ecl_amount': '125.50',
    'preparation_id': prepared ? '77777777-7777-4777-8777-777777777777' : null,
    'journal_entry_id': prepared
        ? '88888888-8888-4888-8888-888888888888'
        : null,
    'source_event_key': 'ecl_allowance:22222222-2222-4222-8222-222222222222',
    'posting_date': '2026-08-31',
    'fiscal_period_id': '44444444-4444-4444-8444-444444444444',
    'credit_loss_expense_account_id': '55555555-5555-4555-8555-555555555555',
    'allowance_account_id': '66666666-6666-4666-8666-666666666666',
    'allowance_amount': '125.50',
    'prior_allowance_balance': '0.00',
    'preparation_review_token': prepared ? _prepareToken : null,
    'preparation_digest': prepared ? _preparationDigest : null,
    'draft_policy_version': 'ecl_allowance_initial_journal_draft_v1',
    'journal_status': prepared ? (posted ? 'posted' : 'draft') : null,
    'entry_number': posted ? 'GJ-2026-0012' : null,
    'posting_id': posted ? '99999999-9999-4999-8999-999999999999' : null,
    'posting_review_token': posted ? _postToken : null,
    'posting_policy_version': posted
        ? 'ecl_allowance_initial_journal_posting_v1'
        : null,
    'current_allowance_balance': posted ? '125.50' : '0.00',
    'allowance_posting_status': status,
    'protected_allowance_action_ready':
        status == 'preparation_required' || status == 'posting_ready',
    'account_1190_posting_enabled': true,
    'automatic_source_posting': false,
  });
}

const _summary = EclAllowancePostingSummary(
  loanCount: 3,
  measurementNotAuthoritativeCount: 0,
  noAllowanceRequiredCount: 0,
  preparationRequiredCount: 1,
  postingReadyCount: 1,
  postedCurrentCount: 0,
  a5RemeasurementRequiredCount: 0,
  postingAuditIncompleteCount: 0,
  protectedAllowanceBalanceTotal: '0.00',
  account1190PostingEnabled: true,
  automaticSourcePosting: false,
);

const _calculationDigest =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const _preparationDigest =
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
const _prepareToken =
    'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc';
const _postToken =
    'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd';

const _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>[
    'accounting.ecl.allowance.prepare',
    'accounting.ecl.allowance.post',
  ],
);

const _prepareOnlySession = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>['accounting.ecl.allowance.prepare'],
);
