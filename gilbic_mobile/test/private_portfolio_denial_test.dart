// External review probe. Synthetic fixtures only; production page unchanged.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_loan.dart';
import 'package:gilbic_mobile/src/core/management/management_loan_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_loan_portfolio_page.dart';

void main() {
  for (final status in [401, 403, 426, 503]) {
    testWidgets('portfolio denial boundary $status', (tester) async {
      await tester.binding.setSurfaceSize(const Size(1000, 2000));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final repository = _Repository(status);
      final store = MemoryDeviceIdentityStore()..value = 'synthetic-device';
      await tester.pumpWidget(
        MaterialApp(
          home: ManagementLoanPortfolioPage(
            session: const UserSession(
              userId: 'synthetic-management',
              username: 'synthetic',
              displayName: 'Synthetic Manager',
              role: AppRole.management,
              rawRole: 'Management',
              accessToken: 'synthetic-token',
            ),
            deviceIdentityProvider: DeviceIdentityProvider(
              store: store,
              platformResolver: () => 'android',
              appVersionResolver: () async => '1.0.0',
            ),
            repository: repository,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('SYNTHETIC PRIVATE BORROWER'), findsOneWidget);
      final refresh = find.widgetWithIcon(IconButton, Icons.refresh);
      await tester.tap(refresh);
      await tester.pumpAndSettle();
      expect(repository.calls, 2);
      expect(find.text('Synthetic HTTP $status'), findsOneWidget);
      final retainedBorrower = find
          .text('SYNTHETIC PRIVATE BORROWER')
          .evaluate()
          .isNotEmpty;
      final refreshEnabled =
          refresh.evaluate().isNotEmpty &&
          tester.widget<IconButton>(refresh).onPressed != null;
      final searches = find.byKey(const Key('management-loan-search'));
      final searchEnabled =
          searches.evaluate().isNotEmpty &&
          tester.widget<TextField>(searches).enabled != false &&
          tester.widget<TextField>(searches).onSubmitted != null;
      // Capture both exposure and action state before the expected red assertion.
      // ignore: avoid_print
      print(
        'SYNTHETIC_PROBE status=$status borrowerRetained=$retainedBorrower refreshEnabled=$refreshEnabled searchEnabled=$searchEnabled calls=${repository.calls}',
      );
      if (status == 503) {
        expect(
          retainedBorrower,
          isTrue,
          reason:
              'Temporary read failure may preserve an authorized previous portfolio.',
        );
        expect(refreshEnabled, isTrue);
      } else {
        expect(
          retainedBorrower,
          isFalse,
          reason:
              'An explicit authority denial must revoke loaded private loan records.',
        );
        expect(refreshEnabled, isFalse);
        expect(searchEnabled, isFalse);
      }
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpAndSettle();
    });
  }
}

class _Repository implements ManagementLoanRepository {
  _Repository(this.statusCode);
  final int statusCode;
  int calls = 0;
  @override
  Future<ManagementLoanPortfolio> loadPortfolio(
    UserSession session, {
    required String deviceId,
    required String query,
    required String status,
  }) async {
    calls++;
    if (calls > 1) {
      throw SpinaApiException(
        'Synthetic HTTP $statusCode',
        statusCode: statusCode,
      );
    }
    return ManagementLoanPortfolio(
      summary: const ManagementLoanSummary(
        activeLoanCount: 1,
        activeClientCount: 1,
        activePrincipalTotal: 5000,
        activeRemainingTotal: 4900,
        overdueActiveCount: 0,
        activeSevenBySevenCount: 0,
        approvedRenewalCount: 0,
      ),
      notice: 'Synthetic authorized portfolio',
      loans: [
        ManagementLoanItem.fromPayload({
          'loan_id': 'synthetic-loan',
          'loan_number': 'SYNTHETIC-001',
          'client_id': 'synthetic-client',
          'client_code': 'SYNTHETIC-CLIENT',
          'client_name': 'SYNTHETIC PRIVATE BORROWER',
          'client_status': 'active',
          'loan_type_name': 'Regular',
          'calculation_mode': 'fixed_daily',
          'principal': '5000.00',
          'daily_amount': '50.00',
          'remaining_balance': '4900.00',
          'paid_amount': '100.00',
          'paid_percent': '2.0',
          'loan_status': 'active',
          'pass_count': 0,
          'payment_count': 2,
          'state_version': 3,
        }),
      ],
    );
  }
}
