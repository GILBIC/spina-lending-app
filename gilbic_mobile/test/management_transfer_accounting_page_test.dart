import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/management/transfer_accounting_evidence.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_transfer_accounting_page.dart';
import 'management_protected_accounting_page_test.dart'
    show id, session, book, digest, tap, enter, visible;

Map<String, dynamic> transferSource() => {
  'book_id': id(1),
  'transfer_id': id(5),
  'leg': 'source',
  'event_id': id(6),
  'source_account_id': id(3),
  'destination_account_id': id(4),
  'treasury_account_id': id(3),
  'fiscal_period_id': id(7),
  'posting_date': '2026-09-30',
  'amount': '100.00',
  'fee': '2.00',
  'source_digest': digest,
  'lines': [
    {
      'line_number': 10,
      'account_code': '1040',
      'debit': '100.00',
      'credit': '0.00',
      'account_snapshot': {'name': 'Transfer Funds in Transit'},
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

class TransferFixture implements SourceAccountingRepository {
  bool failWrites = false, denied = false;
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
      return delayed == null ? transferSource() : await delayed!.future;
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
      final snapshot = transferSource()..remove('source_digest');
      prep = {
        'id': id(20),
        'actor_user_id': id(2),
        'request_id': body['request_id'],
        'confirmation_token': 'b' * 64,
        'source_digest': digest,
        'source_mapping_id': id(8),
        'destination_mapping_id': id(9),
        'snapshot': snapshot,
        for (final key in [
          'book_id',
          'transfer_id',
          'leg',
          'event_id',
          'source_account_id',
          'destination_account_id',
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
Future<void> pumpTransfer(
  WidgetTester tester,
  TransferFixture repo, {
  UserSession? user,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: ManagementTransferAccountingPage(
        session: user ?? session(),
        deviceIdentityProvider: device,
        repository: repo,
        uuidGenerator: () => id(30),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> lookupTransfer(WidgetTester tester, {bool settle = true}) async {
  await tap(tester, 'transfer-source');
  await tester.tap(find.text('Source wallet').last);
  await tester.pumpAndSettle();
  await tap(tester, 'transfer-destination');
  await tester.tap(find.text('Destination bank').last);
  await tester.pumpAndSettle();
  await enter(tester, 'transfer-reference', id(5));
  await visible(tester, 'transfer-load');
  await tester.tap(find.byKey(const Key('transfer-load')));
  if (settle) {
    await tester.pumpAndSettle();
  } else {
    await tester.pump();
  }
}

void main() {
  testWidgets(
    'source principal and fee require separate preparation and posting confirmation',
    (tester) async {
      final repo = TransferFixture();
      await pumpTransfer(tester, repo);
      await lookupTransfer(tester);
      expect(find.textContaining('PRIVATE SOURCE SNAPSHOT'), findsNothing);
      await tap(tester, 'transfer-prepare');
      expect(repo.writes, isEmpty);
      await tap(tester, 'transfer-confirm');
      expect(repo.writes, hasLength(1));
      expect(repo.writes.first.$2.keys.toSet(), {
        'leg',
        'source_mapping_id',
        'destination_mapping_id',
        'source_digest',
        'request_id',
      });
      await tap(tester, 'transfer-post');
      expect(repo.writes, hasLength(1));
      await tap(tester, 'transfer-confirm');
      expect(repo.writes, hasLength(2));
      expect(repo.writes.last.$2['confirm'], isTrue);
      await tester.scrollUntilVisible(
        find.text('Transfer leg accounting posted'),
        220,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      expect(
        find.text('Transfer leg accounting posted').hitTestable(),
        findsOneWidget,
      );
    },
  );
  testWidgets(
    'uncertain outcome retries exact request and never invents new money',
    (tester) async {
      final repo = TransferFixture()..failWrites = true;
      await pumpTransfer(tester, repo);
      await lookupTransfer(tester);
      await tap(tester, 'transfer-prepare');
      await tap(tester, 'transfer-confirm');
      repo.failWrites = false;
      await tap(tester, 'transfer-retry');
      expect(repo.writes.first.$2, repo.writes.last.$2);
      await visible(tester, 'transfer-post');
      expect(find.byKey(const Key('transfer-post')), findsOneWidget);
    },
  );
  testWidgets('denial clears both wallet identities and private evidence', (
    tester,
  ) async {
    final repo = TransferFixture()..denied = true;
    await pumpTransfer(tester, repo);
    await lookupTransfer(tester);
    expect(
      find.textContaining('Private destination access removed'),
      findsOneWidget,
    );
    expect(find.byKey(const Key('transfer-prepare')), findsNothing);
    expect(find.byKey(const Key('transfer-source')), findsNothing);
  });
  testWidgets('session replacement rejects delayed prior private response', (
    tester,
  ) async {
    final repo = TransferFixture()..delayed = Completer<Map<String, dynamic>>();
    await pumpTransfer(tester, repo);
    await lookupTransfer(tester, settle: false);
    await tester.pumpWidget(
      MaterialApp(
        home: ManagementTransferAccountingPage(
          session: session(token: 'replacement', manage: false),
          deviceIdentityProvider: device,
          repository: repo,
        ),
      ),
    );
    await tester.pump();
    repo.delayed!.complete(transferSource());
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('transfer-prepare')), findsNothing);
    expect(find.textContaining('Principal: PHP 100.00'), findsNothing);
    expect(repo.writes, isEmpty);
  });
  test(
    'transfer projection rejects wrong wallet, unexplained fees and noncash accounts',
    () {
      Map<String, dynamic> validate(Map<String, dynamic> value) =>
          validateTransferAccounting(
            value,
            bookId: id(1),
            sourceAccountId: id(3),
            destinationAccountId: id(4),
            transferId: id(5),
            leg: 'source',
          );
      expect(
        jsonEncode(validate(transferSource())),
        isNot(contains('PRIVATE SOURCE SNAPSHOT')),
      );
      expect(
        () => validate(transferSource()..['destination_account_id'] = id(99)),
        throwsFormatException,
      );
      expect(
        () => validate(transferSource()..['fee'] = '3.00'),
        throwsFormatException,
      );
      final wrong = transferSource();
      (wrong['lines'] as List).last['account_code'] = '2200';
      expect(() => validate(wrong), throwsFormatException);
    },
  );
}
