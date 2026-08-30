import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/ecl_a5_accounting.dart';
import 'package:gilbic_mobile/src/core/management/ecl_a5_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_ecl_a5_accounting_page.dart';

void main() {
  testWidgets('shows A5 states and intersects server and session permissions', (
    tester,
  ) async {
    final repository = _FakeRepository(<EclA5ActionItem>[
      _item('remeasurement_required'),
      _item('writeoff_ready', suffix: '2'),
      _item('blocked', suffix: '3'),
    ]);
    await _pump(tester, repository, session: _remeasureOnlySession);

    expect(find.byKey(const Key('ecl-a5-summary')), findsOneWidget);
    expect(find.text('Blocked: 1'), findsOneWidget);
    expect(
      find.byKey(
        const Key('remeasure-ecl-11111111-1111-4111-8111-111111111111'),
      ),
      findsOneWidget,
    );
    expect(find.text('Write-off permission is not assigned.'), findsOneWidget);
    expect(
      find.byKey(
        const Key('writeoff-ecl-11111111-1111-4111-8111-111111111112'),
      ),
      findsNothing,
    );
  });

  testWidgets(
    'remeasurement requires review and uncertain retry reuses token',
    (tester) async {
      final repository = _FakeRepository(<EclA5ActionItem>[
        _item('remeasurement_required'),
      ], failFirstRemeasurement: true);
      var generated = 0;
      await _pump(
        tester,
        repository,
        tokenGenerator: () {
          generated += 1;
          return List<String>.filled(64, 'e').join();
        },
      );
      final action = find.byKey(
        const Key('remeasure-ecl-11111111-1111-4111-8111-111111111111'),
      );

      await tester.scrollUntilVisible(
        action,
        500,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(action);
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('management-review-ecl-a5')), findsOneWidget);
      expect(find.text('Prior allowance'), findsOneWidget);
      expect(find.text('100.00'), findsWidgets);
      expect(find.text('Target allowance'), findsOneWidget);
      expect(find.text('125.50'), findsWidgets);
      expect(find.text(_digest), findsOneWidget);
      await tester.tap(find.byKey(const Key('confirm-ecl-a5')));
      await tester.pumpAndSettle();
      expect(repository.remeasurementCalls, 1);
      expect(
        find.text('Connection interrupted after submission.'),
        findsOneWidget,
      );

      await tester.tap(action);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-ecl-a5')));
      await tester.pumpAndSettle();

      expect(repository.remeasurementCalls, 2);
      expect(repository.tokens.toSet(), hasLength(1));
      expect(generated, 1);
      expect(repository.loadCalls, 2);
    },
  );

  testWidgets('recovery review retains evidence before exact confirmation', (
    tester,
  ) async {
    final repository = _FakeRepository(<EclA5ActionItem>[
      _item('recovery_review_required'),
    ]);
    await _pump(tester, repository);
    final action = find.byKey(
      const Key('review-recovery-11111111-1111-4111-8111-111111111111'),
    );

    await tester.scrollUntilVisible(
      action,
      500,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(action);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('recovery-evidence-reference')),
      'OR-2026-0042',
    );
    await tester.enterText(
      find.byKey(const Key('recovery-review-note')),
      'Management matched the official receipt to protected later cash.',
    );
    await tester.tap(find.byKey(const Key('continue-recovery-review')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('management-review-ecl-a5')), findsOneWidget);
    expect(find.text('OR-2026-0042'), findsOneWidget);
    expect(find.text('20.00'), findsWidgets);
    expect(find.textContaining('does not post a journal'), findsOneWidget);
    await tester.tap(find.byKey(const Key('confirm-ecl-a5')));
    await tester.pumpAndSettle();

    expect(repository.recoveryReviewCalls, 1);
    expect(repository.evidenceReference, 'OR-2026-0042');
    expect(repository.reviewNote, contains('official receipt'));
    expect(repository.loadCalls, 2);
  });

  testWidgets('server denial keeps a permitted session read only', (
    tester,
  ) async {
    final repository = _FakeRepository(
      <EclA5ActionItem>[_item('post_writeoff_recovery_ready')],
      permissions: const EclA5Permissions(
        remeasurementPost: true,
        writeoffPost: true,
        recoveryReview: true,
        recoveryPost: false,
      ),
    );
    await _pump(tester, repository);

    expect(
      find.text('Recovery posting permission is not assigned.'),
      findsOneWidget,
    );
    expect(
      find.byKey(
        const Key('post-recovery-11111111-1111-4111-8111-111111111111'),
      ),
      findsNothing,
    );
  });
}

Future<void> _pump(
  WidgetTester tester,
  _FakeRepository repository, {
  UserSession session = _session,
  String Function()? tokenGenerator,
}) async {
  await tester.binding.setSurfaceSize(const Size(390, 844));
  addTearDown(() async => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(
    MaterialApp(
      home: ManagementEclA5AccountingPage(
        session: session,
        deviceIdentityProvider: _deviceProvider(),
        repository: repository,
        reviewTokenGenerator: tokenGenerator,
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

class _FakeRepository implements EclA5AccountingRepository {
  _FakeRepository(
    this.items, {
    this.failFirstRemeasurement = false,
    this.permissions = const EclA5Permissions(
      remeasurementPost: true,
      writeoffPost: true,
      recoveryReview: true,
      recoveryPost: true,
    ),
  });

  final List<EclA5ActionItem> items;
  final bool failFirstRemeasurement;
  final EclA5Permissions permissions;
  int loadCalls = 0;
  int remeasurementCalls = 0;
  int recoveryReviewCalls = 0;
  String? evidenceReference;
  String? reviewNote;
  final List<String> tokens = <String>[];

  @override
  Future<EclA5Overview> load(
    UserSession session, {
    required String deviceId,
    String status = 'all',
    int limit = 100,
    int offset = 0,
  }) async {
    loadCalls += 1;
    return EclA5Overview(
      summary: const EclA5Summary(
        loanCount: 3,
        remeasurementRequiredCount: 1,
        allowanceCurrentCount: 0,
        writeoffReadyCount: 1,
        writtenOffCount: 0,
        recoveryReviewRequiredCount: 1,
        recoveryReadyCount: 1,
        blockedCount: 1,
        remeasurementPostingCount: 0,
        writeoffPostingCount: 0,
        postWriteoffRecoveryCount: 0,
        protectedA5AccountingEnabled: true,
        automaticSourcePosting: false,
      ),
      items: items,
      permissions: permissions,
      notice: 'Exact protected A5 server queue.',
      filter: status,
      limit: limit,
      offset: offset,
    );
  }

  @override
  Future<EclA5ActionReceipt> postRemeasurement(
    UserSession session, {
    required String deviceId,
    required EclA5ActionItem item,
    required String reviewToken,
  }) async {
    remeasurementCalls += 1;
    tokens.add(reviewToken);
    if (failFirstRemeasurement && remeasurementCalls == 1) {
      throw const SpinaApiException(
        'Connection interrupted after submission.',
        code: 'network_unavailable',
      );
    }
    return const EclA5ActionReceipt(
      id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      automaticSourcePosting: false,
    );
  }

  @override
  Future<EclA5ActionReceipt> reviewRecovery(
    UserSession session, {
    required String deviceId,
    required EclA5ActionItem item,
    required String reviewToken,
    required String evidenceReference,
    required String reviewNote,
  }) async {
    recoveryReviewCalls += 1;
    this.evidenceReference = evidenceReference;
    this.reviewNote = reviewNote;
    tokens.add(reviewToken);
    return const EclA5ActionReceipt(id: '19', automaticSourcePosting: false);
  }

  @override
  Future<EclA5ActionReceipt> postFullWriteoff(
    UserSession session, {
    required String deviceId,
    required EclA5ActionItem item,
    required String reviewToken,
  }) => throw UnsupportedError('Not used.');

  @override
  Future<EclA5ActionReceipt> postRecovery(
    UserSession session, {
    required String deviceId,
    required EclA5ActionItem item,
    required String reviewToken,
  }) => throw UnsupportedError('Not used.');
}

EclA5ActionItem _item(String status, {String suffix = '1'}) {
  final recoveryReview = status == 'recovery_review_required';
  final recoveryPost = status == 'post_writeoff_recovery_ready';
  return EclA5ActionItem.fromPayload(<String, Object?>{
    'loan_id': '11111111-1111-4111-8111-11111111111$suffix',
    'loan_number': 'LN-2026-000$suffix',
    'loan_status': 'active',
    'calculation_mode': 'fixed_daily',
    'credit_risk_review_id': recoveryPost ? 19 : 12,
    'stage_label': 'stage_3_credit_impaired',
    'default_label': true,
    'write_off_label': 'supported_no_reasonable_expectation_of_recovery',
    'recovery_label': recoveryPost ? 'cash_recovery_observed' : 'none',
    'measurement_id': '22222222-2222-4222-8222-222222222222',
    'measurement_version': 3,
    'measurement_date': '2026-08-30',
    'calculation_digest': _digest,
    'measurement_status': 'measured_read_only',
    'authoritative_ecl_amount': '125.50',
    'current_allowance_balance': recoveryReview || recoveryPost
        ? '0.00'
        : status == 'writeoff_ready'
        ? '125.50'
        : '100.00',
    'loan_receivable_account_id': '77777777-7777-4777-8777-777777777777',
    'loan_receivable_system_key': 'loans_receivable_regular',
    'accrued_interest_account_id': '88888888-8888-4888-8888-888888888888',
    'loan_component': recoveryReview || recoveryPost ? '0.00' : '100.00',
    'accrued_interest_component': recoveryReview || recoveryPost
        ? '0.00'
        : '25.50',
    'gross_carrying_amount': recoveryReview || recoveryPost ? '0.00' : '125.50',
    'writeoff_id': recoveryReview || recoveryPost
        ? 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
        : null,
    'recovery_transaction_id': recoveryPost
        ? '99999999-9999-4999-8999-999999999999'
        : null,
    'recovery_amount': recoveryPost ? '20.00' : null,
    'recovery_candidate_transaction_id': recoveryReview
        ? '99999999-9999-4999-8999-999999999999'
        : null,
    'recovery_candidate_amount': recoveryReview ? '20.00' : null,
    'recovery_candidate_collection_date': recoveryReview ? '2026-08-30' : null,
    'posting_date': recoveryReview ? null : '2026-08-30',
    'fiscal_period_id': recoveryReview
        ? null
        : '44444444-4444-4444-8444-444444444444',
    'credit_loss_expense_account_id': recoveryReview
        ? null
        : '55555555-5555-4555-8555-555555555555',
    'allowance_account_id': recoveryReview || recoveryPost
        ? null
        : '66666666-6666-4666-8666-666666666666',
    'cash_account_id': recoveryPost
        ? 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
        : null,
    'a5_status': status,
    'protected_a5_accounting_enabled': true,
    'automatic_source_posting': false,
  });
}

const _digest =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';

const _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>[
    'accounting.ecl.remeasurement.post',
    'accounting.ecl.writeoff.post',
    'accounting.ecl.recovery.review',
    'accounting.ecl.recovery.post',
  ],
);

const _remeasureOnlySession = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>['accounting.ecl.remeasurement.post'],
);
