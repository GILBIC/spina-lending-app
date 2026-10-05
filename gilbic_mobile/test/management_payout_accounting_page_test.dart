import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/management/payout_accounting_evidence.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_payout_accounting_page.dart';
import 'management_protected_accounting_page_test.dart'
    show id, session, book, digest, tap, enter, visible;

Map<String, dynamic> payoutSource() => {
  'book_id': id(1),
  'payout_id': id(5),
  'stage': 'debit',
  'event_id': id(6),
  'loan_id': id(11),
  'client_id': id(12),
  'disbursement_event_id': null,
  'treasury_account_id': id(3),
  'fiscal_period_id': id(7),
  'posting_date': '2026-09-30',
  'amount': '100.00',
  'fee': '2.00',
  'source_digest': digest,
  'lines': [
    {
      'line_number': 10,
      'account_code': '1050',
      'debit': '100.00',
      'credit': '0.00',
      'account_snapshot': {'name': 'Loan Disbursement Transit'},
    },
    {
      'line_number': 20,
      'account_code': '5240',
      'debit': '2.00',
      'credit': '0.00',
      'account_snapshot': {'name': 'Bank Charges'},
    },
    {
      'line_number': 30,
      'account_code': '1030',
      'debit': '0.00',
      'credit': '102.00',
      'account_snapshot': {'name': 'Cash in Bank'},
    },
  ],
  'origin': {'secret': 'PRIVATE SOURCE SNAPSHOT'},
};

Map<String, dynamic> payoutCompletion() => {
  ...payoutSource(),
  'stage': 'completion',
  'disbursement_event_id': id(13),
  'fee': '0.00',
  'lines': [
    {
      'line_number': 10,
      'account_code': '1100',
      'debit': '100.00',
      'credit': '0.00',
      'account_snapshot': {'name': 'Regular Loans Receivable'},
    },
    {
      'line_number': 30,
      'account_code': '1050',
      'debit': '0.00',
      'credit': '100.00',
      'account_snapshot': {'name': 'Loan Disbursement Transit'},
    },
  ],
};

class PayoutFixture implements SourceAccountingRepository {
  bool failWrites = false, denied = false, completion = false;
  Map<String, dynamic> source() =>
      completion ? payoutCompletion() : payoutSource();
  Completer<Map<String, dynamic>>? delayed;
  final writes = <(String, Map<String, dynamic>)>[];
  Map<String, dynamic>? prep;
  @override
  Future<Map<String, dynamic>> read(
    UserSession user, {
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
          for (final n in [3, 4])
            {
              'id': id(n),
              'alias': n == 3 ? 'Source wallet' : 'Destination bank',
              'kind': 'bank',
              'balance': <String, dynamic>{},
              'active': true,
            },
        ],
      };
    }
    if (path.endsWith('/cash-mapping')) {
      final account = path.contains(id(3)) ? id(3) : id(4);
      return {
        'book_id': id(1),
        'treasury_account_id': account,
        'mapping': {
          'id': account == id(3) ? id(8) : id(9),
          'book_id': id(1),
          'treasury_account_id': account,
        },
      };
    }
    if (path.contains('/review?')) {
      if (denied) {
        throw const SpinaApiException(
          'Private destination access removed',
          statusCode: 403,
        );
      }
      return delayed == null ? source() : await delayed!.future;
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
      final snapshot = source()..remove('source_digest');
      prep = {
        'id': id(20),
        'actor_user_id': id(2),
        'request_id': body['request_id'],
        'confirmation_token': 'b' * 64,
        'source_digest': digest,
        'snapshot': snapshot,
        for (final key in [
          'book_id',
          'payout_id',
          'stage',
          'event_id',
          'treasury_account_id',
          'loan_id',
          'client_id',
          'disbursement_event_id',
        ])
          key: snapshot[key],
      };
      return {'preparation': prep, 'posting': null};
    }
    return {
      'preparation': prep,
      'journal_entry_id': id(21),
      'posting': {
        ...prep!,
        'preparation_id': id(20),
        'journal_entry_id': id(21),
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
Future<void> pumpPayout(
  WidgetTester tester,
  PayoutFixture repo, {
  UserSession? user,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: ManagementPayoutAccountingPage(
        session: user ?? session(),
        deviceIdentityProvider: device,
        repository: repo,
        uuidGenerator: () => id(30),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> lookupPayout(
  WidgetTester tester, {
  bool settle = true,
  bool completion = false,
}) async {
  await tap(tester, 'payout-account');
  await tester.tap(find.text('Source wallet').last);
  await tester.pumpAndSettle();
  if (completion) {
    await tap(tester, 'payout-stage');
    await tester.tap(find.text('Borrower completion').last);
    await tester.pumpAndSettle();
  }
  await enter(tester, 'payout-reference', id(5));
  await visible(tester, 'payout-load');
  await tester.tap(find.byKey(const Key('payout-load')));
  if (settle) {
    await tester.pumpAndSettle();
  } else {
    await tester.pump();
  }
}

void main() {
  testWidgets(
    'borrower completion reviews receivable from transit with no second cash entry',
    (tester) async {
      final repo = PayoutFixture()..completion = true;
      await pumpPayout(tester, repo);
      await lookupPayout(tester, completion: true);
      await tap(tester, 'payout-prepare');
      expect(repo.writes, isEmpty);
      await tap(tester, 'payout-confirm');
      expect(repo.writes.first.$2['stage'], 'completion');
      await tap(tester, 'payout-post');
      await tap(tester, 'payout-confirm');
      expect(repo.writes.last.$2['confirm'], isTrue);
    },
  );
  test(
    'completion rejects fee, missing authoritative release and a second cash debit',
    () {
      Map<String, dynamic> validate(Map<String, dynamic> source) =>
          validatePayoutAccounting(
            source,
            bookId: id(1),
            accountId: id(3),
            payoutId: id(5),
            stage: 'completion',
          );
      expect(validate(payoutCompletion())['stage'], 'completion');
      expect(
        () => validate(payoutCompletion()..['fee'] = '1.00'),
        throwsFormatException,
      );
      expect(
        () => validate(payoutCompletion()..['disbursement_event_id'] = null),
        throwsFormatException,
      );
      final secondCash = payoutCompletion();
      (secondCash['lines'] as List).first['account_code'] = '1030';
      expect(() => validate(secondCash), throwsFormatException);
    },
  );

  testWidgets(
    'source principal and fee require separate preparation and posting confirmation',
    (tester) async {
      final repo = PayoutFixture();
      await pumpPayout(tester, repo);
      await lookupPayout(tester);
      expect(find.textContaining('PRIVATE SOURCE SNAPSHOT'), findsNothing);
      await tap(tester, 'payout-prepare');
      expect(repo.writes, isEmpty);
      await tap(tester, 'payout-confirm');
      expect(repo.writes, hasLength(1));
      expect(repo.writes.first.$2.keys.toSet(), {
        'stage',
        'source_digest',
        'request_id',
      });
      await tap(tester, 'payout-post');
      expect(repo.writes, hasLength(1));
      await tap(tester, 'payout-confirm');
      expect(repo.writes, hasLength(2));
      expect(repo.writes.last.$2['confirm'], isTrue);
      await tester.scrollUntilVisible(
        find.text('Payout stage accounting posted'),
        220,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      expect(
        find.text('Payout stage accounting posted').hitTestable(),
        findsOneWidget,
      );
    },
  );
  testWidgets(
    'uncertain outcome retries exact request and never invents new money',
    (tester) async {
      final repo = PayoutFixture()..failWrites = true;
      await pumpPayout(tester, repo);
      await lookupPayout(tester);
      await tap(tester, 'payout-prepare');
      await tap(tester, 'payout-confirm');
      repo.failWrites = false;
      await tap(tester, 'payout-retry');
      expect(repo.writes.first.$2, repo.writes.last.$2);
      await visible(tester, 'payout-post');
      expect(find.byKey(const Key('payout-post')), findsOneWidget);
    },
  );
  testWidgets('denial clears the wallet identity and private evidence', (
    tester,
  ) async {
    final repo = PayoutFixture()..denied = true;
    await pumpPayout(tester, repo);
    await lookupPayout(tester);
    expect(
      find.textContaining('Private destination access removed'),
      findsOneWidget,
    );
    expect(find.byKey(const Key('payout-prepare')), findsNothing);
    expect(find.byKey(const Key('payout-account')), findsNothing);
  });
  testWidgets('session replacement rejects delayed prior private response', (
    tester,
  ) async {
    final repo = PayoutFixture()..delayed = Completer<Map<String, dynamic>>();
    await pumpPayout(tester, repo);
    await lookupPayout(tester, settle: false);
    await tester.pumpWidget(
      MaterialApp(
        home: ManagementPayoutAccountingPage(
          session: session(token: 'replacement', manage: false),
          deviceIdentityProvider: device,
          repository: repo,
        ),
      ),
    );
    await tester.pump();
    repo.delayed!.complete(payoutSource());
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('payout-prepare')), findsNothing);
    expect(find.textContaining('Principal: PHP 100.00'), findsNothing);
    expect(repo.writes, isEmpty);
  });
  test(
    'payout projection rejects wrong wallet, unexplained fees and noncash accounts',
    () {
      Map<String, dynamic> validate(Map<String, dynamic> value) =>
          validatePayoutAccounting(
            value,
            bookId: id(1),
            accountId: id(3),
            payoutId: id(5),
            stage: 'debit',
          );
      expect(
        jsonEncode(validate(payoutSource())),
        isNot(contains('PRIVATE SOURCE SNAPSHOT')),
      );
      expect(
        () => validate(payoutSource()..['treasury_account_id'] = id(99)),
        throwsFormatException,
      );
      expect(
        () => validate(payoutSource()..['fee'] = '3.00'),
        throwsFormatException,
      );
      final wrong = payoutSource();
      (wrong['lines'] as List).last['account_code'] = '2200';
      expect(() => validate(wrong), throwsFormatException);
    },
  );
}
