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
    'collector automatically loads approved other-area work and opens payment',
    (tester) async {
      await _setLargeSurface(tester);
      final repository = _OtherAreaRepository();
      await tester.pumpWidget(
        MaterialApp(
          home: OtherAreaCollectionPage(
            session: _collectorSession,
            paymentRepository: _PaymentRepository(),
            deviceIdentityProvider: _deviceIdentityProvider(),
            deviceSequence: MemoryCollectionDeviceSequence(),
            repository: repository,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(repository.workLoads, 1);
      expect(repository.queries, isEmpty);
      expect(find.text('Other-Area Work'), findsOneWidget);
      expect(find.text('Bea Borrower'), findsOneWidget);
      expect(find.text('Assigned collector: Collector Two'), findsOneWidget);
      expect(find.textContaining('Taytay'), findsWidgets);
      expect(find.textContaining('Regular'), findsWidgets);
      expect(find.byKey(const Key('record-other-area-loan-other')), findsOneWidget);

      await tester.tap(find.byKey(const Key('record-other-area-loan-other')));
      await tester.pumpAndSettle();
      expect(find.text('Record delegated-area payment?'), findsOneWidget);
      expect(
        find.textContaining('temporary grant will be rechecked by the server'),
        findsOneWidget,
      );

      await tester.tap(find.byKey(const Key('confirm-other-area-payment')));
      await tester.pumpAndSettle();
      expect(find.text('Record Collection'), findsOneWidget);
      expect(find.text('Bea Borrower'), findsOneWidget);
      expect(find.byKey(const Key('collection-amount')), findsOneWidget);
    },
  );

  testWidgets('already processed delegated work shows recorder and cannot post again',
      (tester) async {
    await _setLargeSurface(tester);
    await tester.pumpWidget(
      MaterialApp(
        home: OtherAreaCollectionPage(
          session: _collectorSession,
          paymentRepository: _PaymentRepository(),
          deviceIdentityProvider: _deviceIdentityProvider(),
          deviceSequence: MemoryCollectionDeviceSequence(),
          repository: _OtherAreaRepository(processedToday: true),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Collected ₱200.00'), findsOneWidget);
    expect(find.text('Recorded by: Collector Three'), findsOneWidget);
    expect(find.text('Entry: Locked'), findsOneWidget);
    final button = tester.widget<FilledButton>(
      find.byKey(const Key('record-other-area-loan-other')),
    );
    expect(button.onPressed, isNull);
    expect(find.text('Already recorded today'), findsOneWidget);
  });

  testWidgets('7x7 delegated work remains fail-closed on the mobile path',
      (tester) async {
    await _setLargeSurface(tester);
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

    final button = tester.widget<FilledButton>(
      find.byKey(const Key('record-other-area-loan-other')),
    );
    expect(button.onPressed, isNull);
    expect(
      find.textContaining('7x7 mobile collection remains disabled'),
      findsOneWidget,
    );
  });

  testWidgets('Management direct payment keeps the distinct search workflow',
      (tester) async {
    await _setLargeSurface(tester);
    final repository = _OtherAreaRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: OtherAreaCollectionPage(
          session: _managementSession,
          paymentRepository: _PaymentRepository(),
          deviceIdentityProvider: _deviceIdentityProvider(),
          deviceSequence: MemoryCollectionDeviceSequence(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(repository.workLoads, 0);
    await tester.enterText(find.byKey(const Key('other-area-search')), 'Bea');
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pumpAndSettle();

    expect(repository.queries, ['Bea']);
    expect(find.text('Direct Payment Entry'), findsOneWidget);
    expect(find.text('Bea Borrower'), findsOneWidget);
  });
}

const UserSession _collectorSession = UserSession(
  userId: 'collector-one',
  username: 'collector.one',
  displayName: 'Collector One',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'collector-token',
  permissions: <String>['collection.create', 'delegated_area.view'],
);

const UserSession _managementSession = UserSession(
  userId: 'management-one',
  username: 'management.one',
  displayName: 'Management One',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>['collection.create'],
);

Future<void> _setLargeSurface(WidgetTester tester) async {
  await tester.binding.setSurfaceSize(const Size(900, 1600));
  addTearDown(() async => tester.binding.setSurfaceSize(null));
}

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'android-release-candidate';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0-rc',
  );
}

class _OtherAreaRepository implements OtherAreaClientRepository {
  _OtherAreaRepository({
    this.sevenBySeven = false,
    this.processedToday = false,
  });

  final bool sevenBySeven;
  final bool processedToday;
  final List<String> queries = <String>[];
  int workLoads = 0;

  @override
  Future<List<OtherAreaClient>> listWork(
    UserSession session,
    DateTime workDate, {
    String? assignedCollectorUserId,
  }) async {
    workLoads += 1;
    return _clients();
  }

  @override
  Future<List<OtherAreaClient>> search(UserSession session, String query) async {
    queries.add(query);
    return _clients();
  }

  List<OtherAreaClient> _clients() {
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
          area: 'Taytay › San Juan',
          loanType: sevenBySeven ? '7x7' : 'Regular',
          dailyAmount: sevenBySeven ? 35 : 200,
          balance: 4800,
          status: processedToday ? 'Recorded today' : 'Pending',
          passCount: 0,
          routeRevision: 'loan:loan-other:v3',
          canCollectMobile: true,
          canEnterPayment: !processedToday,
          collectionMessage: processedToday
              ? 'Already recorded today by Collector Three.'
              : 'Delegated other-area work.',
          processedToday: processedToday,
          todayEntryType: processedToday ? 'payment' : '',
          todayCollectorName: processedToday ? 'Collector Three' : '',
          todayAmount: processedToday ? 200 : 0,
          todayIsLocked: processedToday,
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
