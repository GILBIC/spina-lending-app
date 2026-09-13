import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/payments/client_payment.dart';
import 'package:gilbic_mobile/src/core/payments/client_payment_repository.dart';
import 'package:gilbic_mobile/src/features/client/client_payments_page.dart';

void main() {
  test('Client payment model preserves authoritative money as exact text', () {
    final payment = ClientPayment.fromPayload(
      _paymentPayload(
        transactionId: 'payment-exact',
        receiptNumber: 'R-EXACT',
        amount: '90071992547409.93',
        previousBalance: '90071992547409.91',
        officialBalance: '90071992547409.89',
      ),
    );

    expect(payment.amount, '90071992547409.93');
    expect(payment.previousBalance, '90071992547409.91');
    expect(payment.officialBalance, '90071992547409.89');
  });

  test('Client payment valid total sums exact cents without IEEE rounding', () {
    final timeline = ClientPaymentTimeline.fromPayload(<String, dynamic>{
      'client': <String, dynamic>{
        'client_id': 'client-record-exact',
        'client_code': 'CLIENT-EXACT',
        'client_name': 'Exact Client',
      },
      'payments': <Map<String, dynamic>>[
        _paymentPayload(
          transactionId: 'payment-1',
          receiptNumber: 'R-1',
          amount: '90071992547409.91',
          previousBalance: '90071992547409.95',
          officialBalance: '0.04',
        ),
        _paymentPayload(
          transactionId: 'payment-2',
          receiptNumber: 'R-2',
          amount: '0.02',
          previousBalance: '0.04',
          officialBalance: '0.02',
        ),
        _paymentPayload(
          transactionId: 'payment-voided',
          receiptNumber: 'R-V',
          amount: '999.99',
          previousBalance: '0.02',
          officialBalance: '0.02',
          isVoided: true,
          status: 'voided',
        ),
      ],
      'payment_proof': <String, dynamic>{
        'upload_available': false,
        'message': 'Official SPINA receipts only.',
      },
    });

    expect(timeline.validTotal, '90071992547409.93');
  });

  testWidgets('Payments displays exact server receipt money without IEEE rounding',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(1100, 2400));
    addTearDown(() async => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        home: ClientPaymentsPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: _ExactPaymentRepository(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('₱90,071,992,547,409.93'), findsWidgets);
    expect(find.textContaining('₱90,071,992,547,409.91'), findsOneWidget);
    expect(find.textContaining('₱90,071,992,547,409.89'), findsOneWidget);
    expect(find.textContaining('90,071,992,547,409.94'), findsNothing);
  });
}

const UserSession _session = UserSession(
  userId: 'client-exact-payment',
  username: 'client.exact.payment',
  displayName: 'Exact Payment Client',
  role: AppRole.client,
  rawRole: 'Client',
  accessToken: 'client-token',
  permissions: <String>['loan.self.view'],
);

Map<String, dynamic> _paymentPayload({
  required String transactionId,
  required String receiptNumber,
  required String amount,
  required String previousBalance,
  required String officialBalance,
  bool isVoided = false,
  String status = 'posted',
}) {
  return <String, dynamic>{
    'transaction_id': transactionId,
    'receipt_number': receiptNumber,
    'loan_id': 'loan-exact',
    'loan_number': 'EXACT-001',
    'loan_type_name': 'Regular',
    'collector_name': 'Exact Collector',
    'collection_date': '2026-09-13',
    'recorded_at': '2026-09-13T08:00:00Z',
    'entry_type': 'payment',
    'amount': amount,
    'covered_dates': <String>['2026-09-13'],
    'previous_balance': previousBalance,
    'official_balance': officialBalance,
    'note': null,
    'collection_origin': 'collector',
    'status': status,
    'is_voided': isVoided,
    'voided_at': isVoided ? '2026-09-13T09:00:00Z' : null,
    'void_reason': isVoided ? 'Test void' : null,
    'edit_version': 0,
    'remittance_number': null,
    'remittance_status': null,
    'remittance_submitted_at': null,
    'remittance_received_at': null,
  };
}

ClientPaymentTimeline _exactTimeline() =>
    ClientPaymentTimeline.fromPayload(<String, dynamic>{
      'client': <String, dynamic>{
        'client_id': 'client-record-exact',
        'client_code': 'CLIENT-EXACT',
        'client_name': 'Exact Payment Client',
      },
      'payments': <Map<String, dynamic>>[
        _paymentPayload(
          transactionId: 'payment-exact',
          receiptNumber: 'R-EXACT',
          amount: '90071992547409.93',
          previousBalance: '90071992547409.91',
          officialBalance: '90071992547409.89',
        ),
      ],
      'payment_proof': <String, dynamic>{
        'upload_available': false,
        'message': 'Collector-recorded payments use official SPINA receipts.',
      },
    });

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'exact-payment-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

class _ExactPaymentRepository implements ClientPaymentRepository {
  @override
  Future<ClientPaymentTimeline> loadTimeline(
    UserSession session, {
    required String deviceId,
  }) async {
    return _exactTimeline();
  }
}
