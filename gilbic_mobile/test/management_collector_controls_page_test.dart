import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/management/collector_control_schedule.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_collector_controls_page.dart';
import 'management_collector_accounting_page_test.dart' show device;
import 'management_protected_accounting_page_test.dart'
    show id, session, book, tap, enter, visible;

Map<String, dynamic> controlSchedule() => {
  'book': book,
  'as_of': '2026-09-30',
  'business_timezone': 'Asia/Manila',
  'balance_basis': 'debit_minus_credit',
  'controls': [
    for (final row in [
      ('1060', 'debit', '4.00', '4.00'),
      ('2210', 'credit', '0.00', '0.00'),
      ('2220', 'credit', '-10.00', '10.00'),
    ])
      {
        'account_code': row.$1,
        'normal_balance': row.$2,
        'source_balance': row.$3,
        'ledger_balance': row.$3,
        'difference': '0.00',
        'source_amount': row.$4,
        'ledger_amount': row.$4,
        'unregistered_line_count': 0,
      },
  ],
  'movements': [
    {
      'account_code': '2220',
      'effective_date': '2026-09-30',
      'signed_amount': '-10.00',
      'source_type': 'collector_credit',
      'source_id': id(5),
      'exact_posted': true,
    },
  ],
  'movement_count': 1,
  'unproven_movement_count': 0,
  'correction_count': 0,
  'limit': 100,
  'offset': 0,
  'current_capacity': <String, dynamic>{
    'observed_at': '2026-10-05T01:02:03+00:00',
    'unidentified_amount': '0.00',
    'outstanding_amount': '10.00',
    'reserved_amount': '4.00',
    'available_amount': '6.00',
  },
  'controls_reconciled': true,
  'comprehensive_source_coverage': false,
};

class ControlFixture implements SourceAccountingRepository {
  bool denied = false, changedBook = false;
  int writes = 0;
  final paths = <String>[];
  Completer<Map<String, dynamic>>? delayed;
  Map<String, dynamic> value = controlSchedule();
  @override
  Future<Map<String, dynamic>> read(
    UserSession user, {
    required String deviceId,
    required String path,
  }) async {
    paths.add(path);
    if (path.endsWith('/book')) {
      return {
        'book': {...book, if (changedBook) 'book_id': id(99)},
      };
    }
    if (denied) {
      throw const SpinaApiException(
        'Private control history access removed',
        statusCode: 403,
      );
    }
    return delayed == null ? value : await delayed!.future;
  }

  @override
  Future<Map<String, dynamic>> write(
    UserSession user, {
    required String deviceId,
    required String path,
    required Map<String, dynamic> body,
  }) async {
    writes++;
    throw StateError('Read-only schedule wrote money');
  }
}

Future<void> pumpControls(
  WidgetTester tester,
  ControlFixture repo, {
  UserSession? user,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: ManagementCollectorControlsPage(
        session: user ?? session(manage: false),
        deviceIdentityProvider: device,
        repository: repo,
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'view-only controls separate credit liabilities and historical cutoff from current reservations',
    (tester) async {
      final repo = ControlFixture();
      await pumpControls(tester, repo);
      await tester.scrollUntilVisible(
        find.text('Collector credit owed'),
        220,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('Ledger amount: PHP 10.00'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.text('Reserved within outstanding: PHP 4.00'),
        220,
        scrollable: find.byType(Scrollable).first,
      );
      expect(
        find.text('Reserved within outstanding: PHP 4.00'),
        findsOneWidget,
      );
      expect(find.textContaining('2026-10-05T01:02:03+00:00'), findsOneWidget);
      expect(repo.writes, 0);
    },
  );
  test(
    'projection rejects missing values and mismatched balance direction and strips private extras',
    () {
      Map<String, dynamic> validate(Map<String, dynamic> value) =>
          validateCollectorControlSchedule(value, bookId: id(1));
      final invalid = controlSchedule();
      (invalid['controls'] as List).last['ledger_amount'] = '-10.00';
      expect(() => validate(invalid), throwsFormatException);
      final missing = controlSchedule();
      (missing['current_capacity'] as Map)['reserved_amount'] = null;
      expect(() => validate(missing), throwsFormatException);
      final falseComplete = controlSchedule();
      (falseComplete['controls'] as List).last['unregistered_line_count'] = 2;
      expect(() => validate(falseComplete), throwsFormatException);
      final unknown = controlSchedule();
      (unknown['controls'] as List).last['account_code'] = '9999';
      (unknown['controls'] as List).last.remove('normal_balance');
      expect(() => validate(unknown), throwsFormatException);
      final secret = controlSchedule()..['private_origin'] = 'PRIVATE';
      (secret['movements'] as List).first['account_id'] = id(99);
      expect(jsonEncode(validate(secret)), isNot(contains('PRIVATE')));
      expect(jsonEncode(validate(secret)), isNot(contains('account_id')));
    },
  );
  testWidgets(
    'cutoff edit clears old balances and denied reload retains no private totals',
    (tester) async {
      final repo = ControlFixture();
      await pumpControls(tester, repo);
      await enter(tester, 'collector-controls-date', '2026-08-31');
      expect(find.text('Ledger amount: PHP 10.00'), findsNothing);
      repo.denied = true;
      await tap(tester, 'collector-controls-load');
      expect(
        find.text('Private control history access removed'),
        findsOneWidget,
      );
      expect(find.textContaining('Actual owner'), findsNothing);
      expect(find.byKey(const Key('collector-controls-date')), findsNothing);
    },
  );
  testWidgets(
    'pagination stays explicit and changed book discards the next page',
    (tester) async {
      final repo = ControlFixture();
      repo.value['movement_count'] = 101;
      repo.value['movements'] = List.generate(
        100,
        (i) => {
          ...(controlSchedule()['movements'] as List).first
              as Map<String, dynamic>,
          'source_id': id(i + 100),
        },
      );
      await pumpControls(tester, repo);
      await visible(tester, 'collector-controls-next');
      repo.changedBook = true;
      await tap(tester, 'collector-controls-next');
      expect(find.textContaining('Accounting book changed'), findsOneWidget);
      expect(find.text('Ledger amount: PHP 10.00'), findsNothing);
      expect(repo.writes, 0);
    },
  );
  testWidgets(
    'late prior session response cannot repopulate private controls',
    (tester) async {
      final repo = ControlFixture()
        ..delayed = Completer<Map<String, dynamic>>();
      await tester.pumpWidget(
        MaterialApp(
          home: ManagementCollectorControlsPage(
            session: session(manage: false),
            deviceIdentityProvider: device,
            repository: repo,
          ),
        ),
      );
      await tester.pump();
      repo.denied = true;
      await tester.pumpWidget(
        MaterialApp(
          home: ManagementCollectorControlsPage(
            session: session(token: 'replaced', manage: false),
            deviceIdentityProvider: device,
            repository: repo,
          ),
        ),
      );
      await tester.pump();
      repo.delayed!.complete(controlSchedule());
      await tester.pumpAndSettle();
      expect(find.text('Ledger amount: PHP 10.00'), findsNothing);
    },
  );
}
