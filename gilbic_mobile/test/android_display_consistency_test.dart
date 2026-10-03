import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/offline/mobile_offline_policy.dart';
import 'package:gilbic_mobile/src/features/client/client_loans_page.dart';
import 'support/android_role_fixture.dart';
import 'support/client_fixture.dart';

void main() {
  test('directly reachable offline copy uses SPINA branding in every role', () {
    for (final role in AppRole.values) {
      final policy = MobileOfflinePolicy.forRole(role);
      expect(
        [
          policy.summary,
          ...policy.availableOffline,
          ...policy.blockedOffline,
        ].join(' '),
        isNot(contains('Gilbic')),
      );
    }
  });
  testWidgets(
    'Client loan details preserve calendar fields with common date display',
    (tester) async {
      await pumpAndroidRoleFixture(
        tester,
        size: const Size(412, 915),
        textScaler: TextScaler.linear(1),
        home: ClientLoansPage(
          session: clientSession(),
          deviceIdentityProvider: clientIdentity(),
          repository: FakeClientLoanRepository(clientPortfolio()),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('2026-08-01'), findsOneWidget);
      for (final loanId in ['regular-loan', 'seven-by-seven-loan']) {
        final card = find.byKey(Key('client-loan-$loanId'));
        for (final label in ['Last payment', 'Paid in advance until']) {
          final row = find.ancestor(
            of: find.descendant(of: card, matching: find.text(label)),
            matching: find.byType(Row),
          );
          expect(row, findsOneWidget);
          final value = loanId == 'regular-loan' && label == 'Last payment'
              ? '2026-08-02'
              : 'Not recorded';
          expect(
            find.descendant(of: row, matching: find.text(value)),
            findsOneWidget,
            reason:
                '$loanId $label must independently disclose its recorded or missing date',
          );
        }
      }
      expect(find.text('₱4,950.00'), findsWidgets);
      expect(tester.takeException(), isNull);
    },
  );
}
