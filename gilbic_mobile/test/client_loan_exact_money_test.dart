import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan_repository.dart';
import 'package:gilbic_mobile/src/core/payments/client_gcash.dart';
import 'package:gilbic_mobile/src/core/payments/client_gcash_repository.dart';
import 'package:gilbic_mobile/src/features/client/client_dashboard.dart';
import 'package:gilbic_mobile/src/features/client/client_gcash_payment_page.dart';
import 'package:gilbic_mobile/src/features/client/client_loans_page.dart';

void main() {
  test('Client loan model preserves authoritative money as exact text', () {
    final loan = ClientLoan.fromPayload(_exactLoanPayload());

    expect(loan.principal, '90071992547409.93');
    expect(loan.dailyAmount, '90071992547409.01');
    expect(loan.interestRate, '20.0000');
    expect(loan.remainingBalance, '90071992547409.93');
    expect(loan.paidAmount, '0.01');
  });

  testWidgets('My Loans displays exact server loan money without IEEE rounding',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(1000, 1800));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        home: ClientLoansPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: _ExactLoanRepository(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('Remaining: ₱90,071,992,547,409.93'), findsOneWidget);
    expect(find.text('₱90,071,992,547,409.93'), findsWidgets);
    expect(find.text('₱90,071,992,547,409.01'), findsOneWidget);
    expect(find.text('20%'), findsOneWidget);
  });

  testWidgets('Client home displays exact server balance and daily amount',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(1000, 1800));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        home: ClientDashboard(
          session: _session,
          onSignOut: () async {},
          deviceIdentityProvider: _deviceIdentityProvider(),
          loanRepository: _ExactLoanRepository(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('₱90,071,992,547,409.93'), findsOneWidget);
    expect(find.text('₱90,071,992,547,409.01'), findsOneWidget);
  });

  testWidgets('GCash loan labels keep exact authoritative loan money',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(1000, 1800));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        home: ClientGcashPaymentPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          gcashRepository: _CapabilityRepository(),
          loanRepository: _ExactLoanRepository(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(
      find.textContaining('balance ₱90,071,992,547,409.93'),
      findsOneWidget,
    );
    expect(find.text('Daily ₱90,071,992,547,409.01'), findsOneWidget);
  });
}

const UserSession _session = UserSession(
  userId: 'client-exact-1',
  username: 'client.exact',
  displayName: 'Exact Client',
  role: AppRole.client,
  rawRole: 'Client',
  accessToken: 'client-token',
  permissions: <String>['loan.self.view'],
);

Map<String, dynamic> _exactLoanPayload() => <String, dynamic>{
      'loan_id': 'exact-loan',
      'loan_number': 'EXACT-001',
      'loan_type_code': 'regular',
      'loan_type_name': 'Regular',
      'principal': '90071992547409.93',
      'daily_amount': '90071992547409.01',
      'interest_rate': '20.0000',
      'date_released': '2026-09-01',
      'due_date': '2026-12-30',
      'status': 'active',
      'remaining_balance': '90071992547409.93',
      'paid_amount': '0.01',
      'pass_count': 0,
      'last_payment_date': '2026-09-12',
      'advance_until': null,
      'state_version': 1,
      'payment_count': 1,
    };

ClientLoanPortfolio _portfolio() => ClientLoanPortfolio(
      clientId: 'client-record-exact',
      clientCode: 'CLIENT-EXACT',
      clientName: 'Exact Client',
      area: 'Exact Area',
      clientStatus: 'active',
      loans: <ClientLoan>[ClientLoan.fromPayload(_exactLoanPayload())],
    );

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'exact-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

class _ExactLoanRepository implements ClientLoanRepository {
  @override
  Future<ClientLoanPortfolio> loadPortfolio(
    UserSession session, {
    required String deviceId,
  }) async {
    return _portfolio();
  }
}

class _CapabilityRepository implements ClientGcashRepository {
  @override
  Future<ClientGcashCapability> loadCapability(
    UserSession session, {
    required String deviceId,
  }) async {
    return const ClientGcashCapability(
      provider: 'test-provider',
      mode: 'sandbox',
      checkoutAvailable: true,
      settlementVerificationReady: false,
      paymentAvailable: true,
      message: 'Sandbox checkout is available.',
      officialPaymentRule:
          'Provider checkout does not itself create an official SPINA payment.',
    );
  }

  @override
  Future<ClientGcashIntent> createIntent(
    UserSession session, {
    required String deviceId,
    required String idempotencyKey,
    required List<ClientGcashAllocation> allocations,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<ClientGcashIntent> loadIntent(
    UserSession session, {
    required String deviceId,
    required String intentId,
  }) {
    throw UnimplementedError();
  }
}
