import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/payments/client_payment.dart';
import 'package:gilbic_mobile/src/core/payments/client_payment_repository.dart';
import 'package:gilbic_mobile/src/features/client/client_payments_page.dart';

void main() {
  testWidgets('linked client can view valid and voided payment receipts',
      (tester) async {
    final repository = _FakeClientPaymentRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ClientPaymentsPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Payments'), findsOneWidget);
    expect(find.text('TEST CLIENT REGULAR'), findsOneWidget);
    expect(find.text('TEST-REG-001'), findsOneWidget);
    expect(find.text('Valid payments'), findsOneWidget);
    expect(find.text('₱50.00'), findsWidgets);
    await tester.scrollUntilVisible(
      find.byKey(const Key('client-gcash-placeholder')),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('Direct GCash payment'), findsOneWidget);
    expect(find.text('Coming soon through Xendit'), findsOneWidget);
    expect(
      find.text(
        'This is a placeholder only. It cannot accept or post a payment yet.',
      ),
      findsOneWidget,
    );
    expect(find.byKey(const Key('open-client-gcash-payment')), findsNothing);
    await tester.scrollUntilVisible(
      find.text(
        'Sending or uploading an image does not post a payment. Only a SPINA-posted transaction with an official receipt changes your balance.',
      ),
      250,
      scrollable: find.byType(Scrollable).first,
    );
    expect(
      find.text(
        'Sending or uploading an image does not post a payment. Only a SPINA-posted transaction with an official receipt changes your balance.',
      ),
      findsOneWidget,
    );
    expect(find.byKey(const Key('client-payment-proof-upload')), findsNothing);

    // The direct-GCash placeholder sits above the receipt timeline, so scroll
    // the first lazy-built receipt into view before asserting timeline details.
    await tester.scrollUntilVisible(
      find.text('Payment timeline'),
      250,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('Payment timeline'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('Receipt: GBC-20260806-00000010'),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('Receipt: GBC-20260806-00000010'), findsOneWidget);
    expect(find.text('Payment posted'), findsOneWidget);

    await tester.scrollUntilVisible(
      find.text('Receipt: GBC-20260805-00000008'),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('Receipt: GBC-20260805-00000008'), findsOneWidget);
    expect(find.text('Voided'), findsOneWidget);
    expect(
      find.text('This receipt was voided and does not reduce your balance.'),
      findsOneWidget,
    );
    expect(repository.deviceId, 'client-device');
    expect(repository.userId, 'client-1');
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

class _FakeClientPaymentRepository implements ClientPaymentRepository {
  String? deviceId;
  String? userId;

  @override
  Future<ClientPaymentTimeline> loadTimeline(
    UserSession session, {
    required String deviceId,
  }) async {
    this.deviceId = deviceId;
    userId = session.userId;
    return ClientPaymentTimeline(
      clientId: 'client-record-1',
      clientCode: 'TEST-REG-001',
      clientName: 'TEST CLIENT REGULAR',
      proofUploadAvailable: false,
      proofMessage:
          'Collector-recorded payments use official SPINA receipts.',
      payments: <ClientPayment>[
        ClientPayment(
          transactionId: 'payment-1',
          receiptNumber: 'GBC-20260806-00000010',
          loanId: 'regular-loan',
          loanNumber: 'TEST-REG-20260802',
          loanTypeName: 'Regular',
          collectorName: 'Test Collector',
          collectionDate: DateTime(2026, 8, 6),
          recordedAt: DateTime.utc(2026, 8, 5, 23, 3),
          entryType: 'payment',
          amount: 50,
          coveredDates: <DateTime>[DateTime(2026, 8, 6)],
          previousBalance: 4950,
          officialBalance: 4900,
          status: 'posted',
          isVoided: false,
          editVersion: 0,
        ),
        ClientPayment(
          transactionId: 'payment-voided',
          receiptNumber: 'GBC-20260805-00000008',
          loanId: 'regular-loan',
          loanNumber: 'TEST-REG-20260802',
          loanTypeName: 'Regular',
          collectorName: 'Test Collector',
          collectionDate: DateTime(2026, 8, 5),
          recordedAt: DateTime.utc(2026, 8, 5, 8, 30),
          entryType: 'covered_payment',
          amount: 50,
          coveredDates: <DateTime>[DateTime(2026, 8, 6)],
          previousBalance: 4950,
          officialBalance: 4900,
          status: 'voided',
          isVoided: true,
          voidedAt: DateTime.utc(2026, 8, 5, 9, 1),
          voidReason: 'Payment posted to the wrong borrower',
          editVersion: 0,
        ),
      ],
    );
  }
}
