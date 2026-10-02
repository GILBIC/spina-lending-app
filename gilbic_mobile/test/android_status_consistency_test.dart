import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_grouping.dart';
import 'package:gilbic_mobile/src/features/collector/collector_client_ledger.dart';
import 'support/android_role_fixture.dart';

void main() {
  for (final note in ['Not paid through GCash', 'Do not use GCash', 'GCash tomorrow']) {
    testWidgets('note_mentions_never_verify_gcash: $note', (tester) async {
      final entry = CollectorRouteEntry(id: 'entry', clientId: 'client', loanId: 'loan', clientName: 'Client', area: 'Area', loanType: 'Regular', dailyAmount: 100, balance: 1000, status: 'future_state', note: note, passCount: 0);
      var submitted = 0;
      await pumpAndroidRoleFixture(tester, size: const Size(412, 915), textScaler: TextScaler.linear(1), home: Scaffold(body: CollectorClientLedgerSection(
        group: CollectorRouteAreaGroup(area: 'Area', clients: [CollectorRouteClientGroup(clientId: 'client', clientName: 'Client', area: 'Area', loans: [entry])]),
        expandedClients: const {'client'}, directPayBlockedReasonFor: (_) => null, payingLoanIds: const {}, pendingDirectLoanIds: const {}, onToggleClient: (_) {}, onRecord: (_) => submitted++, onRecordCombined: (_) => submitted++, detailsBuilder: (value) => Text(value.note),
      )));
      expect(find.text('GCASH'), findsNothing);
      expect(find.text('NOTE'), findsOneWidget);
      expect(find.text(note), findsOneWidget);
      expect(find.text('NOT COLLECTED'), findsOneWidget);
      expect(submitted, 0);
      expect(tester.takeException(), isNull);
    });
  }
}
