import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan_repository.dart';
import 'package:gilbic_mobile/src/core/payments/client_gcash.dart';
import 'package:gilbic_mobile/src/core/payments/client_gcash_repository.dart';
import 'package:gilbic_mobile/src/features/client/client_gcash_payment_page.dart';

void main() {
  testWidgets('GCash amount stays blank until the client enters it',
      (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: ClientGcashPaymentPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          gcashRepository: _FakeGcashRepository(),
          loanRepository: _FakeLoanRepository(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    final amountField =
        find.byKey(const Key('client-gcash-amount-regular-loan'));
    expect(amountField, findsOneWidget);
    final textField = tester.widget<TextField>(amountField);
    expect(textField.controller?.text, '');
    expect(find.text('₱0.00'), findsOneWidget);
  });
}

const UserSession _session = UserSession(
  userId: 'client-1',
  username: 'testregular1',
  displayName: 'TEST CLIENT REGULAR',
  role: AppRole.client,
  rawRole: 'Client',
  accessToken: 'client-token',
  permissions: <String>[],
);

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'client-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

class _FakeGcashRepository implements ClientGcashRepository {
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

class _FakeLoanRepository implements ClientLoanRepository {
  @override
  Future<ClientLoanPortfolio> loadPortfolio(
    UserSession session, {
    required String deviceId,
  }) async {
    return const ClientLoanPortfolio(
      clientId: 'client-record-1',
      clientCode: 'TEST-REG-001',
      clientName: 'TEST CLIENT REGULAR',
      clientStatus: 'active',
      loans: <ClientLoan>[
        ClientLoan(
          loanId: 'regular-loan',
          loanNumber: 'TEST-REG-20260802',
          loanTypeCode: 'regular',
          loanTypeName: 'Regular',
          principal: 5000,
          dailyAmount: 200,
          status: 'active',
          remainingBalance: 4900,
          paidAmount: 100,
          passCount: 0,
          stateVersion: 1,
          paymentCount: 1,
        ),
      ],
    );
  }
}
