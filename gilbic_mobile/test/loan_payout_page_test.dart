import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_repository.dart';
import 'package:gilbic_mobile/src/features/treasury/loan_payout_page.dart';
import 'support/treasury_fixture.dart' as f;

class PayoutRepo implements LoanPayoutRepository {
  final data = f.workspace();
  final List<Map<String, dynamic>> previews = [];
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
  String? get pendingRequestId => null;
  @override
  Future<TreasuryWorkspace> loadWorkspace() async => workspace!;
  @override
  Future<Map<String, dynamic>> loadLoanPayouts({
    String mode = 'own',
    String? accountId,
    int limit = 50,
    int offset = 0,
  }) async => {'enabled': true, 'items': [], 'has_more': false};
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
