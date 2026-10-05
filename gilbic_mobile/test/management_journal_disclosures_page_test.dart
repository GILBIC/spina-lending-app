import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/journal_disclosure_evidence.dart';
import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_journal_disclosures_page.dart';
import 'journal_disclosure_evidence_test.dart' show disclosureContract;
import 'management_protected_accounting_page_test.dart'
    show session, device, id, tap, enter;

class DisclosureFixture implements SourceAccountingRepository {
  bool loseResponse = false;
  int? rejectWrite;
  final reads = <String>[];
  final writes = <Map<String, dynamic>>[];
  final report = disclosureContract();
  @override
  Future<Map<String, dynamic>> read(
    UserSession user, {
    required String deviceId,
    required String path,
  }) async {
    reads.add(path);
    if (path.contains('/disclosures?')) return {'disclosures': report};
    return {
      'fiscal_periods': [
        {
          'period_id': report['period']['id'],
          'label': report['period']['label'],
        },
      ],
    };
  }

  @override
  Future<Map<String, dynamic>> write(
    UserSession user, {
    required String deviceId,
    required String path,
    required Map<String, dynamic> body,
  }) async {
    writes.add(Map<String, dynamic>.from(jsonDecode(jsonEncode(body)) as Map));
    if (rejectWrite != null) {
      throw SpinaApiException(
        'Current review rejected',
        statusCode: rejectWrite,
      );
    }
    if (loseResponse && writes.length == 1) {
      throw Exception('Synthetic lost response');
    }
    return {'review_id': body['request_id'], 'policy_id': body['request_id']};
  }
}

Future<void> pumpPage(
  WidgetTester tester,
  DisclosureFixture repo, {
  UserSession? user,
  double width = 420,
  double scale = 1,
}) async {
  await tester.binding.setSurfaceSize(Size(width, 800));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(
    MaterialApp(
      home: MediaQuery(
        data: MediaQueryData(textScaler: TextScaler.linear(scale)),
        child: ManagementJournalDisclosuresPage(
          session: user ?? session(),
          deviceIdentityProvider: device(),
          repository: repo,
          uuidGenerator: () => id(30),
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> review(WidgetTester tester) async {
  await tap(tester, 'disclosure-journal-0');
  await enter(
    tester,
    'disclosure-reason',
    'Reconfirmed exact financing contract',
  );
  await enter(tester, 'disclosure-reference', 'Retained contract');
  await enter(tester, 'disclosure-digest', 'a' * 64);
  await tap(tester, 'disclosure-review');
}

void main() {
  testWidgets(
    'existing components require explicit review and exact confirmation',
    (tester) async {
      final repo = DisclosureFixture();
      await pumpPage(tester, repo);
      await review(tester);
      expect(repo.writes, isEmpty);
      expect(find.text('Reconfirmed exact financing contract'), findsOneWidget);
      await tap(tester, 'disclosure-save');
      expect(repo.writes.length, 1);
      expect(
        repo.writes.single['source_digest'],
        repo.report['journals'][0]['source_digest'],
      );
      expect(repo.writes.single['expected_version'], 1);
      expect(repo.writes.single['reviewed'], true);
      expect(
        repo.writes.single['components'],
        repo.report['journals'][0]['components'],
      );
    },
  );
  testWidgets('lost response keeps an unchanged recoverable request', (
    tester,
  ) async {
    final repo = DisclosureFixture()..loseResponse = true;
    await pumpPage(tester, repo);
    await review(tester);
    await tap(tester, 'disclosure-save');
    await tap(tester, 'disclosure-retry');
    expect(repo.writes.length, 2);
    expect(repo.writes[0], repo.writes[1]);
  });
  testWidgets('read-only user sees reports without save actions', (
    tester,
  ) async {
    final repo = DisclosureFixture();
    await pumpPage(tester, repo, user: session(manage: false));
    expect(find.text('Cash and noncash disclosure review'), findsOneWidget);
    expect(find.byKey(const Key('disclosure-journal-0')), findsNothing);
    expect(repo.writes, isEmpty);
  });
  testWidgets('review fits narrow screen at large text size', (tester) async {
    final repo = DisclosureFixture();
    await pumpPage(tester, repo, width: 320, scale: 2);
    await review(tester);
    expect(tester.takeException(), isNull);
  });
  testWidgets(
    'new portions require complete coverage and explicit confirmation',
    (tester) async {
      final repo = DisclosureFixture();
      await pumpPage(tester, repo);
      await tap(tester, 'disclosure-journal-0');
      await tap(tester, 'disclosure-remove-0');
      await tap(tester, 'disclosure-remove-0');
      await enter(tester, 'disclosure-reason', 'Reviewed financing contract');
      await enter(tester, 'disclosure-reference', 'Contract');
      await enter(tester, 'disclosure-digest', 'a' * 64);
      await tap(tester, 'disclosure-review');
      expect(find.byKey(const Key('disclosure-save')), findsNothing);
      final journal = repo.report['journals'][0] as Map;
      for (final part in journal['components'] as List) {
        tester
            .state<ScrollableState>(find.byType(Scrollable).first)
            .position
            .jumpTo(0);
        await tester.pumpAndSettle();
        for (final side in ['debit', 'credit']) {
          final line = (journal['lines'] as List).firstWhere(
            (line) => line['id'] == part['${side}_line_id'],
          );
          await tap(tester, 'disclosure-$side');
          await tester.tap(
            find.text('${line['account_code']} · ${line['account_name']}').last,
          );
          await tester.pumpAndSettle();
        }
        await tap(tester, 'disclosure-classification');
        await tester.ensureVisible(
          find.text(journalDisclosureLabels[part['classification']]!).last,
        );
        await tester.tap(
          find.text(journalDisclosureLabels[part['classification']]!).last,
        );
        await tester.pumpAndSettle();
        await enter(tester, 'disclosure-part-amount', part['amount'] as String);
        await enter(
          tester,
          'disclosure-part-reference',
          part['evidence_reference'] as String,
        );
        await enter(
          tester,
          'disclosure-part-digest',
          part['evidence_digest'] as String,
        );
        await tap(tester, 'disclosure-add');
      }
      await tap(tester, 'disclosure-review');
      expect(repo.writes, isEmpty);
      expect(find.byKey(const Key('disclosure-remove-0')), findsNothing);
      await tap(tester, 'disclosure-save');
      expect(repo.writes.single['components'], journal['components']);
    },
  );
  testWidgets(
    'financing policy can explicitly record no financing liabilities',
    (tester) async {
      final repo = DisclosureFixture();
      await pumpPage(tester, repo);
      await tap(tester, 'disclosure-policy');
      final selected = find.byWidgetPredicate(
        (widget) => widget is CheckboxListTile && widget.value == true,
      );
      await tester.ensureVisible(selected);
      await tester.tap(selected);
      await tester.pumpAndSettle();
      await enter(tester, 'disclosure-reference', 'No financing liabilities');
      await enter(tester, 'disclosure-digest', 'a' * 64);
      await tap(tester, 'disclosure-review');
      expect(repo.writes, isEmpty);
      await tap(tester, 'disclosure-save');
      expect(repo.writes.single['financing_account_codes'], isEmpty);
      expect(
        repo.writes.single['expected_version'],
        repo.report['policy']['version'],
      );
    },
  );
  for (final status in [403, 409]) {
    testWidgets('server rejection $status never appears as a saved review', (
      tester,
    ) async {
      final repo = DisclosureFixture()..rejectWrite = status;
      await pumpPage(tester, repo);
      await review(tester);
      await tap(tester, 'disclosure-save');
      expect(repo.writes.length, 1);
      if (status == 403) {
        expect(
          find.text('Current Management accounting access is required.'),
          findsOneWidget,
        );
        expect(find.byKey(const Key('disclosure-retry')), findsNothing);
      } else {
        expect(find.text('Current review rejected'), findsOneWidget);
        expect(find.byKey(const Key('disclosure-restart')), findsOneWidget);
      }
    });
  }
  testWidgets('closed period permits reading but no editing', (tester) async {
    final repo = DisclosureFixture();
    repo.report['period']['status'] = 'closed';
    await pumpPage(tester, repo);
    expect(find.byKey(const Key('disclosure-policy')), findsNothing);
    expect(find.byKey(const Key('disclosure-journal-0')), findsNothing);
    expect(repo.reads.length, 2);
  });
  testWidgets(
    'session change clears the pending write and its private review',
    (tester) async {
      final repo = DisclosureFixture()..loseResponse = true;
      await pumpPage(tester, repo);
      await review(tester);
      await tap(tester, 'disclosure-save');
      expect(find.byKey(const Key('disclosure-retry')), findsOneWidget);
      await pumpPage(
        tester,
        repo,
        user: session(token: 'new-session', manage: false),
      );
      expect(find.byKey(const Key('disclosure-retry')), findsNothing);
      expect(find.text('Reconfirmed exact financing contract'), findsNothing);
      expect(repo.writes.length, 1);
    },
  );
}
