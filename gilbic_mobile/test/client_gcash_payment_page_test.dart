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

  testWidgets(
      'GCash keeps exact cents through input request response and display',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(1100, 2400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final gcashRepository = _CapturingGcashRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ClientGcashPaymentPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          gcashRepository: gcashRepository,
          loanRepository: _FakeTwoLoanRepository(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byType(Checkbox), findsNWidgets(2));
    await tester.tap(find.byType(Checkbox).at(0));
    await tester.pump();
    await tester.tap(find.byType(Checkbox).at(1));
    await tester.pump();

    await tester.enterText(
      find.byKey(const Key('client-gcash-amount-regular-loan')),
      '90071992547409.91',
    );
    await tester.enterText(
      find.byKey(const Key('client-gcash-amount-seven-loan')),
      '0.02',
    );
    await tester.pump();

    expect(find.text('₱90071992547409.93'), findsOneWidget);

    await tester.tap(find.byKey(const Key('client-gcash-start-payment')));
    await tester.pumpAndSettle();

    final allocations = gcashRepository.lastAllocations;
    expect(allocations, isNotNull);
    expect(allocations, hasLength(2));
    expect(allocations![0].toPayload()['amount'], '90071992547409.91');
    expect(allocations[1].toPayload()['amount'], '0.02');
    expect(find.text('Amount: ₱90071992547409.93'), findsOneWidget);
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

class _CapturingGcashRepository extends _FakeGcashRepository {
  List<ClientGcashAllocation>? lastAllocations;

  @override
  Future<ClientGcashIntent> createIntent(
    UserSession session, {
    required String deviceId,
    required String idempotencyKey,
    required List<ClientGcashAllocation> allocations,
  }) async {
    lastAllocations = List<ClientGcashAllocation>.of(allocations);
    return ClientGcashIntent.fromPayload(
      <String, dynamic>{
        'intent_id': 'intent-exact-money',
        'provider': 'test-provider',
        'mode': 'sandbox',
        'provider_reference': 'provider-exact-money',
        'status': 'provider_pending',
        'currency': 'PHP',
        'amount': '90071992547409.93',
        'checkout_url': null,
        'qr_value': null,
        'expires_at': null,
        'verified_paid_at': null,
        'official_payment_posted': false,
        'official_collection_transaction_id': null,
        'allocations': allocations
            .map((allocation) => allocation.toPayload())
            .toList(growable: false),
      },
    );
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

class _FakeTwoLoanRepository implements ClientLoanRepository {
  @override
  Future<ClientLoanPortfolio> loadPortfolio(
    UserSession session, {
    required String deviceId,
  }) async {
    return const ClientLoanPortfolio(
      clientId: 'client-record-1',
      clientCode: 'TEST-EXACT-001',
      clientName: 'TEST CLIENT EXACT MONEY',
      clientStatus: 'active',
      loans: <ClientLoan>[
        ClientLoan(
          loanId: 'regular-loan',
          loanNumber: 'TEST-REG-EXACT',
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
        ClientLoan(
          loanId: 'seven-loan',
          loanNumber: 'TEST-7X7-EXACT',
          loanTypeCode: '7x7',
          loanTypeName: '7x7',
          principal: 3000,
          dailyAmount: 50,
          status: 'active',
          remainingBalance: 2950,
          paidAmount: 50,
          passCount: 0,
          stateVersion: 1,
          paymentCount: 1,
        ),
      ],
    );
  }
}
