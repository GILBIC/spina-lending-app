import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/management/collector_accounting_evidence.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_collector_accounting_page.dart';
import 'management_protected_accounting_page_test.dart'
    show id, session, book, digest, tap, enter, visible;

Map<String, dynamic> collectorLine(
  int number,
  String code,
  String debit,
  String credit,
) => {
  'line_number': number,
  'account_code': code,
  'debit': debit,
  'credit': credit,
  'account_snapshot': {
    'name': switch (code) {
      '1010' => 'Office cash',
      '1020' => 'Collector custody cash',
      '1060' => 'Return awaiting confirmation',
      '2210' => 'Unidentified excess payable',
      '2220' => 'Collector credit payable',
      '5240' => 'Actual payment fee',
      _ => code,
    },
  },
};

Map<String, dynamic> collectorSource([String kind = 'settlement']) => {
  'book_id': id(1),
  'source_kind': kind,
  'source_id': id(5),
  'treasury_account_id': id(3),
  'fiscal_period_id': id(7),
  'posting_date': '2026-09-30',
  'source_digest': digest,
  'amount': switch (kind) {
    'settlement' => '110.00',
    'recognition' => '10.00',
    'return_debit' || 'return_confirmation' => '4.00',
    _ => '1.00',
  },
  'fee': kind == 'return_debit' ? '1.00' : '0.00',
  'lines': switch (kind) {
    'settlement' => [
      collectorLine(10, '1010', '110.00', '0.00'),
      collectorLine(20, '1020', '0.00', '100.00'),
      collectorLine(30, '2210', '0.00', '10.00'),
    ],
    'recognition' => [
      collectorLine(10, '2210', '10.00', '0.00'),
      collectorLine(20, '2220', '0.00', '10.00'),
    ],
    'return_debit' => [
      collectorLine(10, '1060', '4.00', '0.00'),
      collectorLine(20, '5240', '1.00', '0.00'),
      collectorLine(30, '1010', '0.00', '5.00'),
    ],
    'return_confirmation' => [
      collectorLine(10, '2220', '4.00', '0.00'),
      collectorLine(20, '1060', '0.00', '4.00'),
    ],
    _ => [
      collectorLine(10, '1010', '1.00', '0.00'),
      collectorLine(20, '2220', '0.00', '1.00'),
    ],
  },
  'origin': {'secret': 'PRIVATE COLLECTOR SNAPSHOT'},
};

class CollectorFixture implements SourceAccountingRepository {
  String kind = 'settlement';
  bool failWrites = false,
      denied = false,
      unsupported = false,
      changedBook = false;
  Completer<Map<String, dynamic>>? delayed;
  final writes = <(String, Map<String, dynamic>)>[];
  Map<String, dynamic>? prep;
  Map<String, dynamic> preparation() {
    final snapshot = collectorSource(kind)..remove('source_digest');
    return {
      'id': id(20),
      'actor_user_id': id(2),
      'request_id': id(30),
      'confirmation_token': 'b' * 64,
      'source_digest': digest,
      'snapshot': snapshot,
      for (final key in ['book_id', 'source_kind', 'source_id'])
        key: snapshot[key],
    };
  }

  @override
  Future<Map<String, dynamic>> read(
    UserSession user, {
    required String deviceId,
    required String path,
  }) async {
    if (path.endsWith('/book')) {
      return {
        'book': {...book, if (changedBook) 'book_id': id(99)},
      };
    }
    if (path.endsWith('/workspace')) {
      return {
        'contract_version': 1,
        'actor': {'user_id': id(2), 'device_id': id(90)},
        'enabled': true,
        'owner_configured': true,
        'accounts': [
          for (final n in [3, 4])
            {
              'id': id(n),
              'alias': n == 3 ? 'Office cash' : 'Other bank',
              'kind': n == 3 ? 'physical_cash' : 'bank',
              'balance': <String, dynamic>{},
              'active': true,
            },
        ],
      };
    }
    if (path.contains('/preparations/')) {
      return {'preparation': prep ?? preparation(), 'posting': null};
    }
    if (path.endsWith('/review')) {
      if (denied) {
        throw const SpinaApiException(
          'Private Collector access removed',
          statusCode: 403,
        );
      }
      if (unsupported) {
        throw const SpinaApiException(
          'Historical correction requires separate reviewed evidence',
          statusCode: 409,
        );
      }
      return delayed == null ? collectorSource(kind) : await delayed!.future;
    }
    throw StateError(path);
  }

  @override
  Future<Map<String, dynamic>> write(
    UserSession user, {
    required String deviceId,
    required String path,
    required Map<String, dynamic> body,
  }) async {
    writes.add((path, jsonDecode(jsonEncode(body)) as Map<String, dynamic>));
    if (failWrites) {
      throw const SpinaApiException(
        'Lost response',
        code: 'network_unavailable',
      );
    }
    if (path.endsWith('/prepare')) {
      prep = preparation()..['request_id'] = body['request_id'];
      return {'preparation': prep, 'posting': null};
    }
    return {
      'preparation': prep,
      'journal_entry_id': id(21),
      'posting': {
        'preparation_id': id(20),
        'journal_entry_id': id(21),
        'book_id': id(1),
        'source_kind': kind,
        'source_id': id(5),
        'posting_date': '2026-09-30',
        'amount': collectorSource(kind)['amount'],
        'exact_posted': true,
        'correction_pending': false,
      },
    };
  }
}

final device = DeviceIdentityProvider(
  store: MemoryDeviceIdentityStore()..value = 'installation',
  platformResolver: () => 'android',
  appVersionResolver: () async => '1.0.0',
);
Future<void> pumpCollector(
  WidgetTester tester,
  CollectorFixture repo, {
  UserSession? user,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: ManagementCollectorAccountingPage(
        session: user ?? session(),
        deviceIdentityProvider: device,
        repository: repo,
        uuidGenerator: () => id(30),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> lookupCollector(
  WidgetTester tester, {
  bool settle = true,
  String? stage,
  bool recover = false,
}) async {
  await tap(tester, 'collector-account');
  await tester.tap(find.text('Office cash').last);
  await tester.pumpAndSettle();
  if (stage != null) {
    await tap(tester, 'collector-stage');
    await tester.tap(find.text(stage).last);
    await tester.pumpAndSettle();
  }
  await enter(tester, 'collector-reference', recover ? id(20) : id(5));
  await visible(tester, recover ? 'collector-recover' : 'collector-load');
  await tester.tap(
    find.byKey(Key(recover ? 'collector-recover' : 'collector-load')),
  );
  if (settle) {
    await tester.pumpAndSettle();
  } else {
    await tester.pump();
  }
}

void main() {
  for (final stage in {
    'recognition': 'Recognized Collector credit',
    'return_debit': 'Actual return debit',
    'return_confirmation': 'Received return confirmation',
    'return_reversal': 'Actual incoming return reversal',
  }.entries) {
    testWidgets(
      '${stage.key} reviews and posts only its immutable source movement',
      (tester) async {
        final repo = CollectorFixture()..kind = stage.key;
        await pumpCollector(tester, repo);
        await lookupCollector(tester, stage: stage.value);
        await tap(tester, 'collector-prepare');
        expect(repo.writes, isEmpty);
        await tap(tester, 'collector-confirm');
        expect(
          repo.writes.single.$1,
          endsWith('/collector/${stage.key}/${id(5)}/prepare'),
        );
        await tap(tester, 'collector-post');
        await tap(tester, 'collector-confirm');
        expect(repo.writes.last.$2['confirm'], isTrue);
        expect(repo.writes.last.$2.keys, isNot(contains('amount')));
      },
    );
  }
  test(
    'five source shapes preserve exact cash, fee and liability amounts without private data',
    () {
      Map<String, dynamic> validate(Map<String, dynamic> value, String kind) =>
          validateCollectorAccounting(
            value,
            bookId: id(1),
            accountId: id(3),
            sourceId: id(5),
            sourceKind: kind,
          );
      for (final kind in [
        'settlement',
        'recognition',
        'return_debit',
        'return_confirmation',
        'return_reversal',
      ]) {
        final projected = validate(collectorSource(kind), kind);
        expect(
          jsonEncode(projected),
          isNot(contains('PRIVATE COLLECTOR SNAPSHOT')),
        );
        expect(projected['source_kind'], kind);
        expect(
          () => validate(
            collectorSource(kind)..['treasury_account_id'] = id(99),
            kind,
          ),
          throwsFormatException,
        );
        expect(
          () => validate(collectorSource(kind)..['fee'] = '2.00', kind),
          throwsFormatException,
        );
        final tampered = collectorSource(kind);
        (tampered['lines'] as List).first['debit'] = '999.00';
        expect(() => validate(tampered, kind), throwsFormatException);
      }
      final confirmation = validate(
        collectorSource('return_confirmation'),
        'return_confirmation',
      );
      expect(
        (confirmation['lines'] as List).map((row) => row['account_code']),
        ['2220', '1060'],
      );
      final recognition = validate(
        collectorSource('recognition'),
        'recognition',
      );
      expect((recognition['lines'] as List).map((row) => row['credit']), [
        '0.00',
        '10.00',
      ]);
      final debit = validate(collectorSource('return_debit'), 'return_debit');
      expect((debit['lines'] as List).last['credit'], '5.00');
      expect(
        () => validate(collectorSource()..['fee'] = '0', 'settlement'),
        throwsFormatException,
      );
      expect(
        () => validate(
          collectorSource()..['posting_date'] = '2026-02-30',
          'settlement',
        ),
        throwsFormatException,
      );
      final duplicate = collectorSource();
      (duplicate['lines'] as List).last['line_number'] = 10;
      expect(() => validate(duplicate, 'settlement'), throwsFormatException);
    },
  );
  testWidgets('uncertain preparation retries unchanged request', (
    tester,
  ) async {
    final repo = CollectorFixture()..failWrites = true;
    await pumpCollector(tester, repo);
    await lookupCollector(tester);
    await tap(tester, 'collector-prepare');
    await tap(tester, 'collector-confirm');
    repo.failWrites = false;
    await tap(tester, 'collector-retry');
    expect(repo.writes.first.$1, repo.writes.last.$1);
    expect(repo.writes.first.$2, repo.writes.last.$2);
    await visible(tester, 'collector-post');
    expect(
      find.byKey(const Key('collector-post')).hitTestable(),
      findsOneWidget,
    );
  });
  testWidgets('revoked private access clears account and evidence', (
    tester,
  ) async {
    final repo = CollectorFixture()..denied = true;
    await pumpCollector(tester, repo);
    await lookupCollector(tester);
    expect(find.text('Private Collector access removed'), findsOneWidget);
    expect(find.byKey(const Key('collector-account')), findsNothing);
    expect(find.byKey(const Key('collector-prepare')), findsNothing);
  });
  testWidgets(
    'unsupported source reports actual reason without posting or invented amounts',
    (tester) async {
      final repo = CollectorFixture()..unsupported = true;
      await pumpCollector(tester, repo);
      await lookupCollector(tester);
      expect(
        find.text('Historical correction requires separate reviewed evidence'),
        findsOneWidget,
      );
      expect(find.byKey(const Key('collector-prepare')), findsNothing);
      expect(find.textContaining('Source amount: PHP 0.00'), findsNothing);
      expect(repo.writes, isEmpty);
    },
  );
  testWidgets(
    'changed book before submission clears private state without a write',
    (tester) async {
      final repo = CollectorFixture();
      await pumpCollector(tester, repo);
      await lookupCollector(tester);
      await tap(tester, 'collector-prepare');
      repo.changedBook = true;
      await tap(tester, 'collector-confirm');
      expect(repo.writes, isEmpty);
      expect(find.byKey(const Key('collector-retry')), findsNothing);
      expect(find.byKey(const Key('collector-account')), findsNothing);
    },
  );
  testWidgets('session replacement discards late prior source response', (
    tester,
  ) async {
    final repo = CollectorFixture()
      ..delayed = Completer<Map<String, dynamic>>();
    await pumpCollector(tester, repo);
    await lookupCollector(tester, settle: false);
    await tester.pumpWidget(
      MaterialApp(
        home: ManagementCollectorAccountingPage(
          session: session(token: 'new', manage: false),
          deviceIdentityProvider: device,
          repository: repo,
        ),
      ),
    );
    await tester.pump();
    repo.delayed!.complete(collectorSource());
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('collector-prepare')), findsNothing);
    expect(find.textContaining('Source amount: PHP 110.00'), findsNothing);
    expect(repo.writes, isEmpty);
  });
  testWidgets('saved preparation requires the selected step and account', (
    tester,
  ) async {
    final repo = CollectorFixture();
    await pumpCollector(tester, repo);
    await lookupCollector(tester, recover: true);
    await visible(tester, 'collector-post');
    expect(repo.writes, isEmpty);
    await tester.scrollUntilVisible(
      find.byKey(const Key('collector-stage')),
      -250,
      scrollable: find.byType(Scrollable).first,
    );
    await tap(tester, 'collector-stage');
    await tester.tap(find.text('Recognized Collector credit').last);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('collector-post')), findsNothing);
    await tap(tester, 'collector-recover');
    expect(find.byKey(const Key('collector-post')), findsNothing);
    await tester.scrollUntilVisible(
      find.byKey(const Key('collector-error')),
      -250,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.byKey(const Key('collector-error')), findsOneWidget);
  });
  testWidgets(
    'accepted count preserves custody cash and excess payable with two explicit confirmations',
    (tester) async {
      final repo = CollectorFixture();
      await pumpCollector(tester, repo);
      await lookupCollector(tester);
      expect(find.textContaining('PRIVATE COLLECTOR SNAPSHOT'), findsNothing);
      await tap(tester, 'collector-prepare');
      expect(repo.writes, isEmpty);
      await tap(tester, 'collector-confirm');
      expect(repo.writes, hasLength(1));
      expect(
        repo.writes.single.$1,
        endsWith('/collector/settlement/${id(5)}/prepare'),
      );
      expect(repo.writes.single.$2, {
        'source_digest': digest,
        'request_id': id(30),
      });
      await tap(tester, 'collector-post');
      expect(repo.writes, hasLength(1));
      await tap(tester, 'collector-confirm');
      expect(repo.writes, hasLength(2));
      expect(repo.writes.last.$2, {
        'source_digest': digest,
        'confirmation_token': 'b' * 64,
        'confirm': true,
      });
      await tester.scrollUntilVisible(
        find.text('Collector accounting posted'),
        220,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      expect(
        find.text('Collector accounting posted').hitTestable(),
        findsOneWidget,
      );
    },
  );
}
