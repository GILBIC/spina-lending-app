import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/features/collector/collector_cash_status_card.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/android_role_fixture.dart';
import 'support/client_fixture.dart';

void main() {
  for (final status in [401, 403]) {
    testWidgets(
      'cash read $status explains recovery without same-token retry',
      (tester) async {
        var calls = 0;
        await http.runWithClient(
          () async {
            await pumpAndroidRoleFixture(
              tester,
              size: const Size(360, 640),
              textScaler: TextScaler.linear(1),
              home: Scaffold(
                body: CollectorCashStatusCard(
                  session: const UserSession(
                    userId: 'collector',
                    username: 'synthetic',
                    displayName: 'Synthetic',
                    role: AppRole.collector,
                    rawRole: 'Collector',
                    accessToken: 'synthetic',
                    permissions: ['remittance.view'],
                  ),
                  deviceIdentityProvider: clientIdentity(),
                  onOpenRemittance: () {},
                  onOpenRenewals: () {},
                  onOpenCashToReceive: () {},
                  onOpenCashToClient: () {},
                ),
              ),
            );
            await tester.pumpAndSettle();
            expect(
              find.textContaining(
                status == 401 ? 'Sign in again' : 'Access unavailable',
              ),
              findsOneWidget,
            );
            final refresh = tester.widget<IconButton>(
              find.byKey(const Key('collector-cash-status-refresh')),
            );
            expect(refresh.onPressed, isNull);
            expect(calls, 1);
          },
          () => MockClient((_) async {
            calls++;
            return http.Response('{"detail":"private_secret"}', status);
          }),
        );
      },
    );
  }
  testWidgets('collector_cash_long_full_amount_remains_legible', (
    tester,
  ) async {
    await http.runWithClient(
      () async {
        await pumpAndroidRoleFixture(
          tester,
          size: const Size(320, 640),
          textScaler: TextScaler.linear(2),
          home: Scaffold(
            body: ListView(
              children: [
                CollectorCashStatusCard(
                  session: const UserSession(
                    userId: 'collector',
                    username: 'synthetic',
                    displayName: 'Synthetic',
                    role: AppRole.collector,
                    rawRole: 'Collector',
                    accessToken: 'synthetic',
                    permissions: ['remittance.view'],
                  ),
                  deviceIdentityProvider: clientIdentity(),
                  onOpenRemittance: () {},
                  onOpenRenewals: () {},
                  onOpenCashToReceive: () {},
                  onOpenCashToClient: () {},
                ),
              ],
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.text('₱123,456,789.01'), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
      () => MockClient((request) async {
        expect(request.method, 'GET');
        return http.Response(
          jsonEncode({
            'success': true,
            'data': {
              'total_cash_held': '123456789.01',
              'assigned_area_cash_held': '123456000.00',
              'other_area_cash_held': '789.01',
              'other_area_by_collector': [],
              'ready_to_remit_amount': '123456789.01',
              'ready_to_remit_count': 1,
              'awaiting_acceptance_amount': '0.00',
              'awaiting_acceptance_count': 0,
            },
          }),
          200,
        );
      }),
    );
  });
}
