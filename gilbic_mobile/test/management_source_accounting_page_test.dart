import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_source_accounting_page.dart';
import 'support/reporting_fixture.dart';

String id(int number) =>
    '00000000-0000-4000-8000-${number.toString().padLeft(12, '0')}';
String get digest => 'a' * 64;
UserSession session({String token = 'token', bool manage = true}) =>
    UserSession(
      userId: id(1),
      username: 'manager',
      displayName: 'Manager',
      role: AppRole.management,
      rawRole: 'Management',
      accessToken: token,
      permissions: [
        'accounting.view',
        if (manage) ...['accounting.journal.manage', 'treasury.account.manage'],
      ],
    );
Map<String, dynamic> get book => {
  'status': 'configured',
  'book_id': id(2),
  'kind': 'owner_operations',
  'entity_label': 'Owner operations',
};
Map<String, dynamic> get source => {
  'book_id': id(2),
  'treasury_account_id': id(3),
  'receipt_id': id(4),
  'event_id': id(5),
  'mapping_id': id(6),
  'source_digest': digest,
  'amount': '90071992547409.93',
  'posting_date': '2026-09-30',
  'fiscal_period_id': id(7),
  'mapping': {
    'cash_snapshot': {'code': '1030', 'name': 'Cash - Bank / GCash'},
    'liability_snapshot': {'code': '2200', 'name': 'Unapplied Borrower Funds'},
  },
  'receipt': {'reference': 'Private receipt'},
  'evidence': {'sha256': digest},
};
Map<String, dynamic> get line => {
  'journal_line_id': id(11),
  'journal_entry_id': id(12),
  'entry_number': 'GJ-1',
  'account_code': '2300',
  'posting_date': '2026-09-30',
  'debit': '0.00',
  'credit': '100.00',
  'source_type': 'manual',
  'source_reference': null,
  'reversal_of_entry_id': null,
};
Map<String, dynamic> get schedule => {
  'book': book,
  'as_of': '2026-09-30',
  'obligations': [],
  'movements': [],
  'reconciliation': [],
  'unregistered_lines': [line],
  'registered_controls_reconciled': false,
  'comprehensive_source_coverage': false,
};

void main() {
  testWidgets('opening reversals remain outside cash flow classification', (
    tester,
  ) async {
    final repository = SourceAccountingFixtureRepository()
      ..reportWithPolicy = true
      ..openingReversal = true;
    await pump(tester, repository, SourceAccountingMode.reporting);
    expect(find.byKey(Key('source-classify-${id(32)}')), findsNothing);
    await visible(
      tester,
      find.text(
        'Opening balance adjustment — separate from cash flow classification.',
      ),
    );
    expect(repository.writes, isEmpty);
  });
  testWidgets(
    'a changed cash definition allows a new policy but no classification',
    (tester) async {
      final repository = SourceAccountingFixtureRepository()
        ..reportWithPolicy = true
        ..definitionChanged = true;
      await pump(tester, repository, SourceAccountingMode.reporting);
      expect(find.byKey(const Key('source-report-policy')), findsOneWidget);
      expect(find.byKey(Key('source-classify-${id(32)}')), findsNothing);
      await visible(
        tester,
        find.text('Cash definition changed; review a new policy.'),
      );
      expect(repository.writes, isEmpty);
    },
  );
  testWidgets(
    'reporting policy retains selected cash definition and real notes after review',
    (tester) async {
      final repository = SourceAccountingFixtureRepository();
      await pump(tester, repository, SourceAccountingMode.reporting);
      await tap(tester, find.byKey(const Key('source-report-policy')));
      await enter(tester, 'framework_label', 'Actual reporting basis');
      await tap(tester, find.byKey(const Key('source-cash_1010')));
      await tester.tap(find.text('Include').last);
      await tester.pumpAndSettle();
      await enter(tester, 'evidence_reference', 'Policy record');
      await enter(tester, 'evidence_digest', digest);
      await enter(tester, 'note_0_title', 'Borrowing terms');
      await enter(tester, 'note_0_text', 'Actual retained terms.');
      await enter(tester, 'note_0_evidence_reference', 'Agreement A');
      await enter(tester, 'note_0_evidence_digest', digest);
      await tap(tester, find.byKey(const Key('source-review-editor')));
      expect(repository.writes, isEmpty);
      await tap(tester, find.byKey(const Key('source-confirm')));
      final body = repository.writes.single.$2;
      expect(body['cash_account_codes'], ['1010']);
      expect(body['expected_version'], 0);
      expect((body['notes'] as List).single['text'], 'Actual retained terms.');
      expect(body['reviewed'], isTrue);
    },
  );
  testWidgets(
    'cash classification binds reviewed signed splits to the current line version',
    (tester) async {
      final repository = SourceAccountingFixtureRepository()
        ..reportWithPolicy = true;
      await pump(tester, repository, SourceAccountingMode.reporting);
      await tap(tester, find.byKey(Key('source-classify-${id(32)}')));
      await tap(tester, find.byKey(const Key('source-allocation_0_category')));
      await tester.tap(find.text('Operating').last);
      await tester.pumpAndSettle();
      await enter(tester, 'allocation_0_amount', '-40.00');
      await tap(tester, find.byKey(const Key('source-add-allocation')));
      await tap(tester, find.byKey(const Key('source-allocation_1_category')));
      await tester.tap(find.text('Financing').last);
      await tester.pumpAndSettle();
      await enter(tester, 'allocation_1_amount', '-60.00');
      await enter(tester, 'evidence_reference', 'Cash evidence');
      await enter(tester, 'evidence_digest', digest);
      await tap(tester, find.byKey(const Key('source-review-editor')));
      expect(repository.writes, isEmpty);
      await tap(tester, find.byKey(const Key('source-confirm')));
      final body = repository.writes.single.$2;
      expect(body['policy_id'], id(31));
      expect(body['journal_line_id'], id(32));
      expect(body['expected_version'], 3);
      expect(body['expected_amount'], '-100.00');
      expect(body['allocations'], hasLength(2));
    },
  );
  testWidgets(
    'permanent book identity has a separate review and real entity choices',
    (tester) async {
      final repository = SourceAccountingFixtureRepository()
        ..unconfigured = true;
      await pump(tester, repository, SourceAccountingMode.book);
      await tap(tester, find.byKey(const Key('source-configure-book')));
      await tap(tester, find.byKey(const Key('source-kind')));
      expect(find.text('Synthetic'), findsNothing);
      await tester.tap(find.text('Corporate legal').last);
      await tester.pumpAndSettle();
      await enter(tester, 'entity_label', 'Actual Company');
      await enter(tester, 'evidence_reference', 'Registration record');
      await enter(tester, 'evidence_digest', digest);
      await tap(tester, find.byKey(const Key('source-review-editor')));
      expect(repository.writes, isEmpty);
      expect(find.textContaining('cannot be changed'), findsWidgets);
      await tap(tester, find.byKey(const Key('source-confirm')));
      expect(repository.writes.single.$2['kind'], 'corporate_legal');
      expect(repository.writes.single.$2['confirm'], isTrue);
      expect(find.textContaining('Actual Company'), findsOneWidget);
      expect(find.byKey(const Key('source-configure-book')), findsNothing);
    },
  );
  testWidgets(
    'receipt cash requires preparation then a separate posting confirmation',
    (tester) async {
      final repository = SourceAccountingFixtureRepository();
      await pump(tester, repository, SourceAccountingMode.receipts);
      await selectWallet(tester);
      await tap(tester, find.byKey(Key('source-review-${id(4)}')));
      expect(repository.writes, isEmpty);
      expect(find.text('Prepare receipt accounting'), findsWidgets);
      await tap(tester, find.byKey(const Key('source-confirm')));
      expect(repository.writes, hasLength(1));
      expect(repository.writes.single.$1, endsWith('/prepare'));
      expect(find.text('Receipt prepared for review'), findsOneWidget);
      await tap(tester, find.byKey(const Key('source-review-post')));
      expect(repository.writes, hasLength(1));
      await tap(tester, find.byKey(const Key('source-confirm')));
      expect(repository.writes, hasLength(2));
      expect(repository.writes.last.$2, {
        'source_digest': digest,
        'confirmation_token': 'b' * 64,
        'confirm': true,
      });
      expect(find.text('Receipt cash recognized'), findsOneWidget);
      expect(find.textContaining('90071992547409.93'), findsWidgets);
    },
  );

  testWidgets(
    'liability review has no write on cancellation and retries exact evidence',
    (tester) async {
      final repository = SourceAccountingFixtureRepository()..failWrites = true;
      await pump(tester, repository, SourceAccountingMode.liabilities);
      Future<void> edit() async {
        await tap(tester, find.byKey(Key('source-register-${id(11)}')));
        await enter(tester, 'counterparty', 'Actual lender');
        await enter(tester, 'evidence_reference', 'Agreement A');
        await enter(tester, 'evidence_digest', digest);
        await tap(tester, find.byKey(const Key('source-review-editor')));
      }

      await edit();
      expect(repository.writes, isEmpty);
      await tap(tester, find.byKey(const Key('source-cancel-review')));
      expect(repository.writes, isEmpty);
      await edit();
      await tap(tester, find.byKey(const Key('source-confirm')));
      expect(repository.writes, hasLength(1));
      expect(find.textContaining('outcome is uncertain'), findsOneWidget);
      repository.failWrites = false;
      await tap(tester, find.byKey(const Key('source-retry')));
      expect(repository.writes, hasLength(2));
      expect(repository.writes.first.$2, repository.writes.last.$2);
      expect(repository.writes.first.$2['expected_amount'], '100.00');
      expect(repository.writes.first.$2['kind'], 'borrowing_external');
      expect(repository.writes.first.$2['reviewed'], isTrue);
    },
  );

  testWidgets(
    'cash mapping reviews evidence and expected version before saving',
    (tester) async {
      final repository = SourceAccountingFixtureRepository();
      await pump(tester, repository, SourceAccountingMode.receipts);
      await selectWallet(tester);
      await tap(tester, find.byKey(const Key('source-edit-mapping')));
      await enter(tester, 'evidence_reference', 'Wallet confirmation');
      await enter(tester, 'evidence_digest', digest);
      await tap(tester, find.byKey(const Key('source-review-editor')));
      expect(repository.writes, isEmpty);
      await tap(tester, find.byKey(const Key('source-confirm')));
      final body = repository.writes.single.$2;
      expect(body['cash_code'], '1030');
      expect(body['expected_version'], 1);
      expect(body['evidence_digest'], digest);
      expect(body['confirm'], isTrue);
    },
  );

  testWidgets('failed account reads never appear as an unconfigured mapping', (
    tester,
  ) async {
    final repository = SourceAccountingFixtureRepository()..failMapping = true;
    await pump(tester, repository, SourceAccountingMode.receipts);
    await selectWallet(tester);
    expect(
      find.text('Selected account records are unavailable.'),
      findsOneWidget,
    );
    expect(find.text('No cash account mapping is configured.'), findsNothing);
    expect(find.byKey(const Key('source-edit-mapping')), findsNothing);
    expect(repository.writes, isEmpty);
  });

  testWidgets(
    'a session change clears private late receipt review and all write controls',
    (tester) async {
      final repository = SourceAccountingFixtureRepository()
        ..delayedReview = Completer<Map<String, dynamic>>();
      final identity = device();
      await pump(
        tester,
        repository,
        SourceAccountingMode.receipts,
        identity: identity,
      );
      await selectWallet(tester);
      final target = find.byKey(Key('source-review-${id(4)}'));
      await visible(tester, target);
      await tester.tap(target);
      await tester.pump();
      await tester.pumpWidget(
        MaterialApp(
          home: ManagementSourceAccountingPage(
            session: session(token: 'new', manage: false),
            deviceIdentityProvider: identity,
            mode: SourceAccountingMode.receipts,
            repository: repository,
          ),
        ),
      );
      await tester.pumpAndSettle();
      repository.delayedReview!.complete(source);
      await tester.pumpAndSettle();
      expect(find.textContaining('Private receipt'), findsNothing);
      expect(find.byKey(const Key('source-confirm')), findsNothing);
      expect(find.byKey(const Key('source-review-post')), findsNothing);
      expect(repository.writes, isEmpty);
    },
  );
}

Future<void> visible(WidgetTester tester, Finder target) async {
  await tester.scrollUntilVisible(
    target,
    220,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pumpAndSettle();
  expect(target.hitTestable(), findsOneWidget);
}

Future<void> tap(WidgetTester tester, Finder target) async {
  await visible(tester, target);
  await tester.tap(target);
  await tester.pumpAndSettle();
}

Future<void> enter(WidgetTester tester, String name, String value) async {
  final field = find.byKey(Key('source-$name'));
  await visible(tester, field);
  await tester.enterText(field, value);
  await tester.pumpAndSettle();
}

Future<void> selectWallet(WidgetTester tester) async {
  await tap(tester, find.byType(DropdownButtonFormField<String>));
  await tester.tap(find.text('Private wallet').last);
  await tester.pumpAndSettle();
}

DeviceIdentityProvider device() => DeviceIdentityProvider(
  store: MemoryDeviceIdentityStore()..value = 'installation',
  platformResolver: () => 'android',
  appVersionResolver: () async => '1.0.0',
);
Future<void> pump(
  WidgetTester tester,
  SourceAccountingFixtureRepository repository,
  SourceAccountingMode mode, {
  DeviceIdentityProvider? identity,
}) async {
  await tester.binding.setSurfaceSize(const Size(420, 800));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(
    MaterialApp(
      home: ManagementSourceAccountingPage(
        session: session(),
        deviceIdentityProvider: identity ?? device(),
        mode: mode,
        repository: repository,
        uuidGenerator: () => id(10),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

class SourceAccountingFixtureRepository implements SourceAccountingRepository {
  final writes = <(String, Map<String, dynamic>)>[];
  bool failWrites = false,
      failMapping = false,
      unconfigured = false,
      reportWithPolicy = false,
      openingReversal = false,
      definitionChanged = false;
  Map<String, dynamic> get reporting {
    final report = reportingTestSupplement(withPolicy: reportWithPolicy);
    final cash = report['cash_flows'] as Map<String, dynamic>;
    if (openingReversal) {
      final line = (cash['cash_lines'] as List).single as Map<String, dynamic>;
      line['source_type'] = 'reversal';
      line['is_opening_adjustment'] = true;
    }
    if (definitionChanged) {
      (cash['policy'] as Map<String, dynamic>)['cash_definition_valid'] = false;
      cash['status'] = 'cash_definition_changed';
      for (final key in [
        'opening_cash',
        'closing_cash',
        'net_cash_flow',
        'reconciliation_difference',
        'opening_balance_adjustments',
      ]) {
        cash[key] = null;
      }
      cash['categories'] = <String, dynamic>{};
      cash['cash_lines'] = <Map<String, dynamic>>[];
    }
    return report;
  }

  Completer<Map<String, dynamic>>? delayedReview;
  Map<String, dynamic>? preparation;
  @override
  Future<Map<String, dynamic>> read(
    UserSession session, {
    required String deviceId,
    required String path,
  }) async {
    if (path == sourceAccountingBase) {
      return {
        'fiscal_periods': [
          {'period_id': id(30), 'label': 'September'},
        ],
      };
    }
    if (path.contains('/reporting-policy?')) {
      return {'policy': (reporting['cash_flows'] as Map)['policy']};
    }
    if (path.contains('/statements?')) {
      return {
        'statements': {
          'period': {'period_id': id(30)},
          'reporting_supplement': reporting,
        },
      };
    }
    if (path.endsWith('/book')) {
      return {
        'book': unconfigured
            ? {
                'status': 'unconfigured',
                'book_id': null,
                'kind': null,
                'entity_label': null,
              }
            : book,
        'can_configure': true,
      };
    }
    if (path.endsWith('/workspace')) {
      return {
        'contract_version': 1,
        'actor': {'user_id': id(1), 'device_id': id(90)},
        'enabled': true,
        'owner_configured': true,
        'accounts': [
          {
            'id': id(3),
            'alias': 'Private wallet',
            'kind': 'gcash',
            'balance': {},
          },
        ],
      };
    }
    if (path.endsWith('/cash-mapping')) {
      if (failMapping) {
        throw const SpinaApiException('Mapping unavailable.', statusCode: 503);
      }
      return {
        'book_id': id(2),
        'treasury_account_id': id(3),
        'mapping': {
          'id': id(6),
          'book_id': id(2),
          'treasury_account_id': id(3),
          'version': 1,
          'cash_snapshot': {'code': '1030', 'name': 'Cash - Bank / GCash'},
        },
      };
    }
    if (path.contains('/receipts?')) {
      return {
        'items': [
          {
            'id': id(4),
            'account_id': id(3),
            'reference': 'Private receipt',
            'amount': source['amount'],
          },
        ],
        'total_count': 1,
        'limit': 50,
        'offset': 0,
        'has_more': false,
      };
    }
    if (path.contains('/review?')) {
      return delayedReview == null ? source : await delayedReview!.future;
    }
    if (path.contains('/liabilities')) return schedule;
    throw StateError('Unexpected read $path');
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
    if (path.endsWith('/book')) {
      unconfigured = false;
      return {
        'book': {...body, 'status': 'configured', 'book_id': id(2)},
        'can_configure': true,
      };
    }
    if (path.endsWith('/prepare')) {
      final snapshot = {...source}..remove('source_digest');
      preparation = {
        'id': id(20),
        'request_id': body['request_id'],
        'book_id': id(2),
        'treasury_account_id': id(3),
        'receipt_id': id(4),
        'event_id': id(5),
        'mapping_id': id(6),
        'source_digest': digest,
        'snapshot': snapshot,
        'actor_user_id': id(1),
        'confirmation_token': 'b' * 64,
      };
      return {'preparation': preparation, 'posting': null};
    }
    if (path.endsWith('/post')) {
      return {
        'preparation': preparation,
        'journal_entry_id': id(21),
        'posting': {
          'preparation_id': id(20),
          'journal_entry_id': id(21),
          'book_id': id(2),
          'treasury_account_id': id(3),
          'receipt_id': id(4),
          'event_id': id(5),
          'source_digest': digest,
          'exact_posted': true,
          'correction_pending': false,
        },
      };
    }
    if (path.endsWith('/cash-mapping')) {
      return {
        'mapping': {
          'id': id(6),
          'book_id': id(2),
          'treasury_account_id': id(3),
          'version': 2,
          'request_id': body['request_id'],
          'cash_snapshot': {'code': '1030'},
          'evidence_reference': body['evidence_reference'],
          'evidence_digest': body['evidence_digest'],
        },
      };
    }
    if (path.endsWith('/reporting-policy')) return {'policy_id': id(31)};
    if (path.endsWith('/cash-flow-classifications')) {
      return {'classification_id': id(34)};
    }
    return {'obligation_id': id(13)};
  }
}
