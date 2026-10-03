import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_repository.dart';
import 'package:gilbic_mobile/src/features/treasury/loan_payout_page.dart';
import 'package:gilbic_mobile/src/features/treasury/treasury_command_page.dart';
import 'support/treasury_fixture.dart' as f;

class PayoutRepo implements LoanPayoutRepository {
  final data = f.workspace();
  final List<Map<String, dynamic>> previews = [];
  final List<Map<String, dynamic>> records = [];
  final List<Map<String, dynamic>> submitted = [];
  String? pending;
  TreasuryResult? recovered;
  PayoutRepo() {
    (data['accounts'] as List).first['actions'] = ['loan_payout_prepare'];
  }
  @override
  TreasuryWorkspace? get workspace =>
      TreasuryWorkspace.fromJson(data, expectedUserId: f.user);
  @override
  bool get busy => false;
  @override
  bool get denied => false;
  @override
  String? get pendingRequestId => pending;
  @override
  Future<TreasuryResult?> recover() async {
    pending = null;
    return recovered;
  }

  @override
  Future<TreasuryWorkspace> loadWorkspace() async => workspace!;
  @override
  Future<Map<String, dynamic>> loadLoanPayouts({
    String mode = 'own',
    String? accountId,
    int limit = 50,
    int offset = 0,
  }) async => {'enabled': true, 'items': records, 'has_more': false};
  @override
  Future<TreasuryResult> execute(
    TreasuryCommand command, {
    String? targetId,
  }) async {
    submitted.add(command.toJson());
    return TreasuryResult.fromJson({
      ...f.outcome(action: command.action.code),
      'request_id': command.requestId,
    });
  }

  @override
  Future<Map<String, dynamic>> loanPayoutSources(String accountId) async => {
    'items': [
      {
        'source_kind': 'first_loan',
        'source_id': f.event,
        'label': 'Approved loan',
        'amount': '1000.00',
        'authorization_id': f.event,
        'packet_hash': 'a' * 64,
        'contract_evidence_reference': 'office-evidence:${f.event}',
      },
    ],
  };
  @override
  Future<Map<String, dynamic>> loanPayoutPreview(
    Map<String, dynamic> input,
  ) async {
    previews.add(input);
    return {
      ...input,
      'amount': '1000.00',
      'payee_name': 'Assigned Collector',
      'source_digest': 'b' * 64,
    };
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  testWidgets('same Collector and amount still identify each loan source', (
    tester,
  ) async {
    final repo = PayoutRepo();
    repo.data['source_choices'] = [
      for (var i = 1; i <= 2; i++)
        {
          'id': '70000000-0000-4000-8000-00000000000$i',
          'account_id': f.account,
          'kind': 'loan_release',
          'label': 'LN-00$i',
          'payee_name': 'Assigned Collector',
          'amount': '1000.00',
          'supported': true,
          'status': 'prepared',
        },
    ];
    await tester.pumpWidget(
      MaterialApp(
        home: TreasuryCommandPage(
          repository: repo,
          account: repo.workspace!.account(f.account),
          action: TreasuryAction.disbursementRecord,
        ),
      ),
    );
    await tester.pumpAndSettle();
    // Opening the picker exposes all source captions, including the loan identity.
    await tester.ensureVisible(find.text('Approved payable source'));
    await tester.tap(find.text('Approved payable source'));
    await tester.pumpAndSettle();
    expect(find.textContaining('LN-001'), findsWidgets);
    expect(find.textContaining('LN-002'), findsWidgets);
  });
  Map<String, dynamic> row({bool stale = false}) => {
    'id': f.event,
    'account_id': f.account,
    'ledger_context_id': f.ledger,
    'version': stale ? 1 : 3,
    'source_kind': 'renewal',
    'destination': 'borrower',
    'amount': '1000.00',
    'status': stale ? 'prepared' : 'recipient_confirmed',
    'stages': ['borrower'],
    'funding_method': 'gcash',
    'acknowledgments': <String, dynamic>{},
    'blocker': stale ? 'The approved source changed.' : null,
  };
  final note = find.byWidgetPredicate(
    (w) =>
        w is TextField &&
        w.decoration?.labelText == 'Receipt statement or reason',
  );
  testWidgets(
    'restarted upload recovery never attaches another payout receipt',
    (tester) async {
      final payoutA = row()..['status'] = 'debited';
      final payoutB = {
        ...payoutA,
        'id': '77777777-7777-4777-8777-777777777777',
      };
      final repo = PayoutRepo()
        ..records.addAll([payoutA, payoutB])
        ..pending = f.requestId
        ..recovered = TreasuryResult.fromJson({
          ...f.outcome(action: 'evidence_upload'),
          'result': {
            'evidence': {'id': f.requestId, 'account_id': f.account},
          },
        });
      await tester.pumpWidget(
        MaterialApp(
          home: LoanPayoutPage(repository: repo, accountId: f.account),
        ),
      );
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Check saved request'));
      await tester.tap(find.text('Check saved request'));
      await tester.pumpAndSettle();
      expect(find.text('Reviewed evidence uploaded'), findsNothing);
      expect(
        find.textContaining('Choose and review the receipt again'),
        findsOneWidget,
      );
      expect(repo.submitted, isEmpty);
    },
  );
  testWidgets('own recipient can review and submit without account authority', (
    tester,
  ) async {
    final repo = PayoutRepo()..records.add(row());
    repo.data['accounts'] = <dynamic>[];
    await tester.pumpWidget(
      MaterialApp(home: LoanPayoutPage(repository: repo)),
    );
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byType(CheckboxListTile));
    await tester.tap(find.byType(CheckboxListTile));
    await tester.ensureVisible(note);
    await tester.enterText(note, 'I received the full proceeds.');
    await tester.ensureVisible(find.text('Record my acknowledgment'));
    await tester.tap(find.text('Record my acknowledgment'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 250));
    expect(find.text('Confirm reviewed record'), findsOneWidget);
    await tester.tap(find.text('Confirm reviewed record'));
    await tester.pumpAndSettle();
    final body = repo.submitted.single;
    expect(body['action'], 'loan_payout_acknowledge');
    expect(body['stage'], 'borrower');
    expect(body['received'], isTrue);
    expect(body.containsKey('account_id'), isFalse);
    expect(body.containsKey('expected_version'), isFalse);
  });
  testWidgets('stale unfunded preparation accepts a cancellation reason', (
    tester,
  ) async {
    final repo = PayoutRepo()..records.add(row(stale: true));
    await tester.pumpWidget(
      MaterialApp(
        home: LoanPayoutPage(repository: repo, accountId: f.account),
      ),
    );
    await tester.pumpAndSettle();
    await tester.ensureVisible(note);
    expect(tester.widget<TextField>(note).enabled, isTrue);
    await tester.enterText(note, 'Cancel stale unfunded preparation.');
    await tester.ensureVisible(find.text('Cancel unfunded preparation'));
    await tester.tap(find.text('Cancel unfunded preparation'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 250));
    await tester.tap(find.text('Confirm reviewed record'));
    await tester.pumpAndSettle();
    expect(repo.submitted.single['action'], 'loan_payout_cancel');
    expect(
      repo.submitted.single['reason'],
      'Cancel stale unfunded preparation.',
    );
    expect(repo.submitted.single['account_id'], f.account);
  });
  testWidgets(
    'small screen preserves recipient draft on refresh and defaults to Collector',
    (tester) async {
      tester.view.physicalSize = const Size(360, 640);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final repo = PayoutRepo();
      await tester.pumpWidget(
        MaterialApp(
          home: LoanPayoutPage(repository: repo, accountId: f.account),
        ),
      );
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('payout-recipient')),
        'Actual recipient wallet',
      );
      await tester.tap(find.byTooltip('Refresh payouts'));
      await tester.pumpAndSettle();
      expect(find.text('Actual recipient wallet'), findsOneWidget);
      await tester.ensureVisible(find.text('Review payout'));
      await tester.tap(find.text('Review payout'));
      await tester.pumpAndSettle();
      expect(repo.previews.single['destination'], 'collector');
      expect(repo.previews.single['source_id'], f.event);
      expect(find.text('PHP 1000.00 to Assigned Collector'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets('recipient mode needs no wallet selector or source access', (
    tester,
  ) async {
    final repo = PayoutRepo();
    await tester.pumpWidget(
      MaterialApp(home: LoanPayoutPage(repository: repo)),
    );
    await tester.pumpAndSettle();
    expect(find.text('Review payout'), findsNothing);
    expect(find.text('No payouts on this page.'), findsOneWidget);
  });
}
