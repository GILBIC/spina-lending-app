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
      expect(find.text('₱4,950.00'), findsWidgets);
      expect(tester.takeException(), isNull);
    },
  );
}
