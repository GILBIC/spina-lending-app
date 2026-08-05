import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/payments/collection_correction.dart';
import 'package:gilbic_mobile/src/core/payments/collection_correction_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collection_correction_page.dart';

void main() {
  testWidgets('loads exact saved values for the original collector',
      (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: CollectionCorrectionPage(
          session: _session,
          entry: _entry,
          collectionDate: DateTime(2026, 8, 2),
          repository: _FakeCorrectionRepository(),
          deviceIdentityProvider: _deviceIdentityProvider(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Edit Collection'), findsOneWidget);
    expect(find.text('Recorded by: Test Collector'), findsOneWidget);
    expect(find.text('2026-08-02'), findsWidgets);
    expect(find.text('2026-08-04'), findsOneWidget);
    expect(find.text('2026-08-03'), findsNothing);

    await tester.scrollUntilVisible(
      find.byKey(const Key('correction-reason')),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('correction-reason')), findsOneWidget);
    expect(find.byKey(const Key('submit-collection-correction')), findsOneWidget);
  });
}

const UserSession _session = UserSession(
  userId: 'collector-1',
  username: 'collector.one',
  displayName: 'Test Collector',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'token',
  permissions: <String>['collection.correct.own_unremitted'],
);

final CollectorRouteEntry _entry = CollectorRouteEntry(
  id: 'loan-1',
  clientId: 'client-1',
  loanId: 'loan-1',
  clientName: 'Ana Client',
  area: 'Cardona',
  loanType: 'Regular',
  dailyAmount: 50,
  balance: 4900,
  status: 'Recorded today',
  passCount: 0,
  processedToday: true,
  todayEntryType: 'advance',
  todayCollectorName: 'Test Collector',
  todayTransactionId: 'transaction-1',
  canEditToday: true,
  todayAmount: 100,
  todayNote: 'Two selected dates',
  todayCoveredDates: <DateTime>[
    DateTime(2026, 8, 2),
    DateTime(2026, 8, 4),
  ],
);

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'device-one';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

class _FakeCorrectionRepository implements CollectionCorrectionRepository {
  @override
  Future<CollectionCorrectionResult> correct(
    UserSession session, {
    required String deviceId,
    required CollectionCorrectionDraft draft,
  }) {
    throw UnimplementedError();
  }
}
