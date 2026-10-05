import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_protected_accounting_page.dart';

String id(int n) => '00000000-0000-4000-8000-${n.toString().padLeft(12, '0')}';
String get digest => 'a' * 64;
UserSession session({String token = 'token', bool manage = true}) =>
    UserSession(
      userId: id(2),
      username: 'manager',
      displayName: 'Manager',
      role: AppRole.management,
      rawRole: 'Management',
      accessToken: token,
      permissions: [
        'accounting.view',
        if (manage) ...[
          'accounting.journal.manage',
          'accounting.period.close.prepare',
          'accounting.period.close.post',
        ],
      ],
    );
Map<String, dynamic> get book => {
  'status': 'configured',
  'book_id': id(1),
  'kind': 'owner_operations',
  'entity_label': 'Actual owner',
};
Map<String, dynamic> get source => {
  'book_id': id(1),
  'treasury_account_id': id(3),
  'application_id': id(4),
  'receipt_id': id(5),
  'transaction_id': id(6),
  'event_id': id(7),
  'loan_id': id(8),
  'fiscal_period_id': id(9),
  'posting_date': '2026-09-30',
  'source_digest': digest,
  'amount': '100.00',
  'product_model': 'seven_by_seven',
  'accounting_policy_version': 'treasury_seven_by_seven_application_v1',
  'lines': <dynamic>[
    {
      'line_number': 1,
      'account_code': '2200',
      'debit': '100.00',
      'credit': '0.00',
      'account_snapshot': {'name': 'Unapplied Borrower Funds'},
    },
    {
      'line_number': 2,
      'account_code': '1110',
      'debit': '0.00',
      'credit': '90.00',
      'account_snapshot': {'name': 'Loans Receivable'},
    },
    {
      'line_number': 3,
      'account_code': '4010',
      'debit': '0.00',
      'credit': '10.00',
      'account_snapshot': {'name': 'Interest Income'},
    },
    {
      'line_number': 4,
      'account_code': '1120',
      'debit': '10.00',
      'credit': '0.00',
      'account_snapshot': {'name': 'Interest Receivable'},
    },
    {
      'line_number': 5,
      'account_code': '1120',
      'debit': '0.00',
      'credit': '10.00',
      'account_snapshot': {'name': 'Interest Receivable'},
    },
  ],
  'origin': {'secret': 'DO NOT DISPLAY'},
};
Map<String, dynamic> candidate(bool ready) => {
  'book': book,
  'period_id': id(9),
  'loan_id': id(8),
  'ready': ready,
  'blockers': ready ? [] : ['elapsed_eir_boundary_adapter_required'],
  'source_digest': ready ? digest : null,
  'current_confirmation': false,
  'preparation_id': null,
  'confirmation_id': null,
  'cutoff_date': ready ? '2026-09-30' : null,
  'policy_version': ready ? 'regular_release_day_cutoff_assessment_v1' : null,
  'measurement': ready
      ? {
          'id': id(10),
          'date': '2026-09-30',
          'version': 1,
          'calculation_digest': digest,
          'ecl_amount': '4.00',
        }
      : null,
  'balances': ready
      ? {'1100': '100.00', '1110': '0.00', '1120': '0.00', '1190': '4.00'}
      : null,
  'boundary': ready
      ? {
          'anchor_date': '2026-09-30',
          'release_source_key': 'loan-release:actual',
        }
      : null,
  'comprehensive_source_coverage': false,
};

void main() {
  testWidgets(
    'Regular application shows reviewed product policy and retries the exact preparation before separate posting',
    (tester) async {
      final repo = ProtectedAccountingFixtureRepository()
        ..applicationSource = regularApplicationSource()
        ..failWrites = true;
      await pump(tester, repo, ProtectedAccountingMode.applications);
      await lookup(tester, true);
      await tap(tester, 'protected-prepare-application');
      expect(find.text('Regular daily loan'), findsOneWidget);
      expect(find.text('Original first cash application (v1)'), findsOneWidget);
      expect(find.textContaining('DO NOT DISPLAY'), findsNothing);
      expect(repo.writes, isEmpty);
      await tap(tester, 'protected-confirm');
      expect(repo.writes, hasLength(1));
      repo.failWrites = false;
      await tap(tester, 'protected-retry');
      expect(repo.writes, hasLength(2));
      expect(repo.writes.first.$1, repo.writes.last.$1);
      expect(repo.writes.first.$2, repo.writes.last.$2);
      await tap(tester, 'protected-post-application');
      expect(repo.writes, hasLength(2));
      expect(find.text('Regular daily loan'), findsOneWidget);
      await tap(tester, 'protected-confirm');
      expect(repo.writes, hasLength(3));
      expect(repo.writes.last.$2['confirm'], isTrue);
    },
  );
  testWidgets(
    'saved 7x7 preparation retains explicit projected policy and separate posting confirmation',
    (tester) async {
      final repo = ProtectedAccountingFixtureRepository();
      repo.prep = applicationPreparation(source, requestId: id(30));
      await pump(tester, repo, ProtectedAccountingMode.applications);
      await lookup(tester, true);
      await enter(tester, 'protected-reference', id(20));
      await tap(tester, 'protected-recover');
      await tap(tester, 'protected-post-application');
      expect(find.text('7×7 loan'), findsOneWidget);
      expect(find.text('7×7 retained-funds application (v1)'), findsOneWidget);
      expect(repo.writes, isEmpty);
      await tap(tester, 'protected-confirm');
      expect(repo.writes, hasLength(1));
      expect(repo.writes.single.$2['source_digest'], digest);
      expect(repo.writes.single.$2['confirmation_token'], 'b' * 64);
    },
  );
  testWidgets(
    'preparation with a changed product policy cannot advance to posting',
    (tester) async {
      final repo = ProtectedAccountingFixtureRepository()
        ..preparationSource = regularApplicationSource();
      await pump(tester, repo, ProtectedAccountingMode.applications);
      await lookup(tester, true);
      await tap(tester, 'protected-prepare-application');
      await tap(tester, 'protected-confirm');
      expect(repo.writes, hasLength(1));
      expect(find.byKey(const Key('protected-post-application')), findsNothing);
      expect(find.textContaining('DO NOT DISPLAY'), findsNothing);
      await visible(tester, 'protected-retry');
    },
  );
  testWidgets(
    'preparation with changed valid loan coordinates cannot replace the confirmed review',
    (tester) async {
      final changed = source;
      final lines = changed['lines'] as List;
      lines[1]['credit'] = '89.00';
      lines[2]['credit'] = '11.00';
      lines[3]['debit'] = '11.00';
      lines[4]['credit'] = '11.00';
      final repo = ProtectedAccountingFixtureRepository()
        ..preparationSource = changed;
      await pump(tester, repo, ProtectedAccountingMode.applications);
      await lookup(tester, true);
      await tap(tester, 'protected-prepare-application');
      await tap(tester, 'protected-confirm');
      expect(repo.writes, hasLength(1));
      expect(find.byKey(const Key('protected-post-application')), findsNothing);
      await visible(tester, 'protected-retry');
    },
  );
  testWidgets(
    'application accounting retains separate preparation and posting decisions without cash',
    (tester) async {
      final repo = ProtectedAccountingFixtureRepository();
      await pump(tester, repo, ProtectedAccountingMode.applications);
      await lookup(tester, true);
      expect(find.textContaining('DO NOT DISPLAY'), findsNothing);
      await tap(tester, 'protected-prepare-application');
      expect(repo.writes, isEmpty);
      await tap(tester, 'protected-confirm');
      expect(repo.writes, hasLength(1));
      await tap(tester, 'protected-post-application');
      expect(repo.writes, hasLength(1));
      await tap(tester, 'protected-confirm');
      expect(repo.writes, hasLength(2));
      await tester.scrollUntilVisible(
        find.text('Application accounting posted'),
        220,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      expect(
        find.text('Application accounting posted').hitTestable(),
        findsOneWidget,
      );
      expect(repo.writes.last.$2['confirm'], isTrue);
    },
  );
  testWidgets(
    'unsupported applications display their reason without preparation controls',
    (tester) async {
      final repo = ProtectedAccountingFixtureRepository()..unsupported = true;
      await pump(tester, repo, ProtectedAccountingMode.applications);
      await lookup(tester, true);
      expect(
        find.textContaining(
          'Regular loan application accounting is not supported',
        ),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('protected-prepare-application')),
        findsNothing,
      );
      expect(repo.writes, isEmpty);
    },
  );
  testWidgets(
    'dated cutoff preparation retries exact rationale and then requires a separate confirmation',
    (tester) async {
      final repo = ProtectedAccountingFixtureRepository()..failWrites = true;
      await pump(tester, repo, ProtectedAccountingMode.assessments);
      await lookup(tester, false);
      await enter(
        tester,
        'protected-rationale',
        'Reviewed actual dated allowance and protected release evidence.',
      );
      await tap(tester, 'protected-prepare-assessment');
      expect(repo.writes, isEmpty);
      await tap(tester, 'protected-confirm');
      repo.failWrites = false;
      await tap(tester, 'protected-retry');
      expect(repo.writes.first.$2, repo.writes.last.$2);
      await tap(tester, 'protected-confirm-assessment');
      expect(repo.writes, hasLength(2));
      await tap(tester, 'protected-confirm');
      expect(repo.writes, hasLength(3));
      expect(repo.writes.last.$2, {
        'expected_book_id': id(1),
        'source_digest': digest,
        'confirm': true,
      });
    },
  );
  testWidgets(
    'unsupported cutoff proof has no monetary summary or waiver controls',
    (tester) async {
      final repo = ProtectedAccountingFixtureRepository()..ready = false;
      await pump(tester, repo, ProtectedAccountingMode.assessments);
      await lookup(tester, false);
      expect(
        find.byKey(const Key('protected-prepare-assessment')),
        findsNothing,
      );
      expect(find.textContaining('Measured allowance'), findsNothing);
      expect(find.textContaining('No waiver'), findsOneWidget);
      expect(repo.writes, isEmpty);
    },
  );
  testWidgets('session change discards a late private application review', (
    tester,
  ) async {
    final repo = ProtectedAccountingFixtureRepository()
      ..delayed = Completer<Map<String, dynamic>>();
    final identity = device();
    await pump(
      tester,
      repo,
      ProtectedAccountingMode.applications,
      identity: identity,
    );
    await lookup(tester, true, settle: false);
    await tester.pumpWidget(
      MaterialApp(
        home: ManagementProtectedAccountingPage(
          session: session(token: 'new', manage: false),
          deviceIdentityProvider: identity,
          mode: ProtectedAccountingMode.applications,
          repository: repo,
        ),
      ),
    );
    await tester.pumpAndSettle();
    repo.delayed!.complete(source);
    await tester.pumpAndSettle();
    expect(find.textContaining('Interest Income'), findsNothing);
    expect(find.byKey(const Key('protected-confirm')), findsNothing);
    expect(repo.writes, isEmpty);
  });
}

DeviceIdentityProvider device() => DeviceIdentityProvider(
  store: MemoryDeviceIdentityStore()..value = 'installation',
  platformResolver: () => 'android',
  appVersionResolver: () async => '1.0.0',
);
Future<void> pump(
  WidgetTester tester,
  ProtectedAccountingFixtureRepository repo,
  ProtectedAccountingMode mode, {
  DeviceIdentityProvider? identity,
}) async {
  await tester.binding.setSurfaceSize(const Size(420, 800));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(
    MaterialApp(
      home: ManagementProtectedAccountingPage(
        session: session(),
        deviceIdentityProvider: identity ?? device(),
        mode: mode,
        repository: repo,
        uuidGenerator: () => id(30),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> visible(WidgetTester tester, String key) async {
  final target = find.byKey(Key(key));
  await tester.scrollUntilVisible(
    target,
    220,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pumpAndSettle();
  expect(target.hitTestable(), findsOneWidget);
}

Future<void> tap(WidgetTester tester, String key) async {
  await visible(tester, key);
  await tester.tap(find.byKey(Key(key)));
  await tester.pumpAndSettle();
}

Future<void> enter(WidgetTester tester, String key, String value) async {
  await visible(tester, key);
  await tester.enterText(find.byKey(Key(key)), value);
  await tester.pumpAndSettle();
}

Future<void> lookup(
  WidgetTester tester,
  bool application, {
  bool settle = true,
}) async {
  await tap(tester, 'protected-scope');
  await tester.tap(
    find.text(application ? 'Authorized wallet' : 'September').last,
  );
  await tester.pumpAndSettle();
  await enter(tester, 'protected-reference', application ? id(4) : id(8));
  await visible(tester, 'protected-load');
  await tester.tap(find.byKey(const Key('protected-load')));
  if (settle) {
    await tester.pumpAndSettle();
  } else {
    await tester.pump();
  }
}

class ProtectedAccountingFixtureRepository
    implements SourceAccountingRepository {
  bool unsupported = false, ready = true, failWrites = false;
  Completer<Map<String, dynamic>>? delayed;
  Map<String, dynamic>? prep;
  Map<String, dynamic> applicationSource = source;
  Map<String, dynamic>? preparationSource;
  final writes = <(String, Map<String, dynamic>)>[];
  @override
  Future<Map<String, dynamic>> read(
    UserSession session, {
    required String deviceId,
    required String path,
  }) async {
    if (path.endsWith('/book')) return {'book': book};
    if (path.endsWith('/workspace')) {
      return {
        'contract_version': 1,
        'actor': {'user_id': id(2), 'device_id': id(90)},
        'enabled': true,
        'owner_configured': true,
        'accounts': [
          {
            'id': id(3),
            'alias': 'Authorized wallet',
            'kind': 'gcash',
            'balance': <String, dynamic>{},
            'active': true,
          },
        ],
      };
    }
    if (path.endsWith('/review')) {
      if (unsupported) {
        throw const SpinaApiException(
          'Regular loan application accounting is not supported.',
          statusCode: 409,
        );
      }
      return delayed == null ? applicationSource : await delayed!.future;
    }
    if (path.contains('/application-preparations/')) {
      return {'preparation': prep, 'posting': null};
    }
    if (path.contains('/period-assessments/')) return candidate(ready);
    return {
      'fiscal_periods': [
        {'period_id': id(9), 'label': 'September'},
      ],
    };
  }

  @override
  Future<Map<String, dynamic>> write(
    UserSession session, {
    required String deviceId,
    required String path,
    required Map<String, dynamic> body,
  }) async {
    writes.add((path, jsonDecode(jsonEncode(body)) as Map<String, dynamic>));
    if (failWrites) {
      throw const SpinaApiException(
        'Connection lost.',
        code: 'network_unavailable',
      );
    }
    if (path.contains('/applications/')) {
      prep = applicationPreparation(
        preparationSource ?? applicationSource,
        requestId: body['request_id'] as String,
      );
      return {'preparation': prep, 'posting': null};
    }
    if (path.endsWith('/post')) {
      return {
        'preparation': prep,
        'journal_entry_id': id(21),
        'posting': {
          ...prep!,
          'preparation_id': id(20),
          'journal_entry_id': id(21),
          'event_id': id(7),
          'exact_posted': true,
          'correction_pending': false,
        },
      };
    }
    return path.endsWith('/prepare')
        ? {'preparation_id': id(20)}
        : {'confirmation_id': id(21)};
  }
}

Map<String, dynamic> regularApplicationSource() {
  final value = source;
  value['product_model'] = 'fixed_daily';
  value['accounting_policy_version'] =
      'treasury_regular_original_first_cash_v1';
  for (final row in value['lines'] as List) {
    if (row['account_code'] == '1110') {
      row['account_code'] = '1100';
    }
    if (row['account_code'] == '4010') {
      row['account_code'] = '4000';
    }
  }
  return value;
}

Map<String, dynamic> applicationPreparation(
  Map<String, dynamic> review, {
  required String requestId,
}) {
  final snapshot = {...review}..remove('source_digest');
  return {
    'id': id(20),
    'request_id': requestId,
    for (final key in [
      'book_id',
      'application_id',
      'transaction_id',
      'receipt_id',
      'treasury_account_id',
      'loan_id',
    ])
      key: snapshot[key],
    'source_digest': review['source_digest'],
    'snapshot': snapshot,
    'actor_user_id': id(2),
    'confirmation_token': 'b' * 64,
  };
}
