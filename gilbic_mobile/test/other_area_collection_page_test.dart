import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/other_area_client.dart';
import 'package:gilbic_mobile/src/core/collector/other_area_client_repository.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/collector/other_area_collection_page.dart';

void main() {
  testWidgets(
    'collector can search another area, sees assigned recorder warning, and opens payment',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(800, 1400));
      addTearDown(() async => tester.binding.setSurfaceSize(null));

      final paymentRepository = _PaymentRepository();
      final searchRepository = _OtherAreaRepository();
      await tester.pumpWidget(
        MaterialApp(
          home: OtherAreaCollectionPage(
            session: _collectorSession,
            paymentRepository: paymentRepository,
            deviceIdentityProvider: _deviceIdentityProvider(),
            deviceSequence: MemoryCollectionDeviceSequence(),
            repository: searchRepository,
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('other-area-search')),
        'Bea',
      );
      await tester.pump(const Duration(milliseconds: 400));
      await tester.pumpAndSettle();

      expect(searchRepository.queries, ['Bea']);
      expect(find.text('Bea Borrower'), findsOneWidget);
      expect(find.text('Assigned collector: Collector Two'), findsOneWidget);
      expect(find.text('Taytay'), findsWidgets);
      expect(find.text('Regular'), findsWidgets);
      expect(find.byKey(const Key('record-other-area-loan-other')), findsOneWidget);

      await tester.tap(find.byKey(const Key('record-other-area-loan-other')));
      await tester.pumpAndSettle();
      expect(find.text("Record another collector’s client?"), findsOneWidget);
      expect(
        find.textContaining('Your name will remain the recorder'),
        findsOneWidget,
      );
      expect(find.textContaining('assigned collector'), findsOneWidget);

      await tester.tap(find.byKey(const Key('confirm-other-area-payment')));
      await tester.pumpAndSettle();
      expect(find.text('Record Collection'), findsOneWidget);
      expect(find.text('Bea Borrower'), findsOneWidget);
      expect(find.byKey(const Key('collection-amount')), findsOneWidget);
    },
  );

  testWidgets('7x7 other-area search remains fail-closed on the cross-area path',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(800, 1400));
    addTearDown(() async => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        home: OtherAreaCollectionPage(
          session: _collectorSession,
          paymentRepository: _PaymentRepository(),
          deviceIdentityProvider: _deviceIdentityProvider(),
          deviceSequence: MemoryCollectionDeviceSequence(),
          repository: _OtherAreaRepository(sevenBySeven: true),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byKey(const Key('other-area-search')), 'Bea');
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pumpAndSettle();

    final button = tester.widget<FilledButton>(
      find.byKey(const Key('record-other-area-loan-other')),
    );
    expect(button.onPressed, isNull);
    expect(
      find.textContaining('7x7 mobile collection remains disabled'),
      findsOneWidget,
    );
  });
}

const UserSession _collectorSession = UserSession(
  userId: 'collector-one',
  username: 'collector.one',
  displayName: 'Collector One',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'collector-token',
  permissions: <String>['collection.create'],
);

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'android-release-candidate';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0-rc',
  );
}

class _OtherAreaRepository implements OtherAreaClientRepository {
  _OtherAreaRepository({this.sevenBySeven = false});

  final bool sevenBySeven;
  final List<String> queries = <String>[];

  @override
  Future<List<OtherAreaClient>> search(UserSession session, String query) async {
    queries.add(query);
    return <OtherAreaClient>[
      OtherAreaClient(
        clientCode: 'C-OTHER',
        phoneNumber: '09170000000',
        assignedCollectorUserId: 'collector-two',
        assignedCollectorName: 'Collector Two',
        entry: CollectorRouteEntry(
          id: 'loan-other',
          clientId: 'client-other',
          loanId: 'loan-other',
          clientName: 'Bea Borrower',
          area: 'Taytay',
          loanType: sevenBySeven ? '7x7' : 'Regular',
          dailyAmount: sevenBySeven ? 35 : 200,
          balance: 4800,
          status: 'Pending',
          passCount: 0,
          routeRevision: 'loan:loan-other:v3',
          canCollectMobile: true,
          canEnterPayment: true,
          collectionMessage: 'Ready for mobile collection.',
        ),
      ),
    ];
  }
}

class _PaymentRepository implements PaymentSubmissionRepository {
  @override
  Future<PaymentSubmissionResult> submit(
    UserSession session,
    PaymentSubmissionDraft draft,
  ) async {
    return PaymentSubmissionResult(
      disposition: PaymentSubmissionDisposition.accepted,
      idempotencyKey: draft.idempotencyKey,
      message: 'Payment saved.',
      receiptNumber: 'GBC-RC-1',
      officialBalance: 4600,
    );
  }
}