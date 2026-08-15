import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/dashboard/role_dashboard.dart';

void main() {
  testWidgets('management tiles mirror exact backend permission boundaries',
      (tester) async {
    await _setLargeSurface(tester);
    const session = UserSession(
      userId: 'management-1',
      username: 'management.one',
      displayName: 'Management One',
      role: AppRole.management,
      rawRole: 'Management',
      accessToken: 'management-token',
      permissions: <String>[
        'management.dashboard.view',
        'accounting.view',
      ],
    );

    await tester.pumpWidget(MaterialApp(home: _dashboard(session)));
    await tester.pumpAndSettle();

    // These two backend reads are Management-role-gated, not permission-gated.
    expect(find.byKey(const Key('management-loans')), findsOneWidget);
    expect(find.byKey(const Key('management-loan-operations')), findsOneWidget);

    // Accounting entry points mirror the backend accounting.view read gate.
    expect(
      find.byKey(const Key('management-financial-accounting')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('management-opening-balance-journal')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('management-general-journal')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('management-financial-statements')),
      findsOneWidget,
    );

    // Missing exact permissions never surface privileged workflow launchers.
    expect(find.byKey(const Key('management-renewals')), findsNothing);
    expect(find.byKey(const Key('management-support')), findsNothing);
    expect(find.byKey(const Key('management-direct-payment')), findsNothing);
    expect(find.byKey(const Key('management-void-payment')), findsNothing);
    expect(find.byKey(const Key('remittance-notifications')), findsNothing);
    expect(
      find.byKey(const Key('client-registration-approvals')),
      findsNothing,
    );
  });

  testWidgets('collector tiles separate route collection and remittance scopes',
      (tester) async {
    await _setLargeSurface(tester);
    const session = UserSession(
      userId: 'collector-1',
      username: 'collector.one',
      displayName: 'Collector One',
      role: AppRole.collector,
      rawRole: 'Collector',
      accessToken: 'collector-token',
      permissions: <String>['route.view', 'collection.create'],
    );

    await tester.pumpWidget(MaterialApp(home: _dashboard(session)));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('daily-route')), findsOneWidget);
    expect(find.byKey(const Key('record-payment')), findsOneWidget);
    expect(find.byKey(const Key('other-area-payment')), findsOneWidget);
    expect(find.byKey(const Key('payment-updates')), findsOneWidget);

    expect(find.byKey(const Key('remittance')), findsNothing);
    expect(
      find.byKey(const Key('assigned-collector-remittance')),
      findsNothing,
    );
    expect(find.byKey(const Key('remittance-notifications')), findsNothing);
  });

  testWidgets('record payment requires both route view and collection create',
      (tester) async {
    await _setLargeSurface(tester);
    const session = UserSession(
      userId: 'collector-1',
      username: 'collector.one',
      displayName: 'Collector One',
      role: AppRole.collector,
      rawRole: 'Collector',
      accessToken: 'collector-token',
      permissions: <String>['route.view'],
    );

    await tester.pumpWidget(MaterialApp(home: _dashboard(session)));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('daily-route')), findsOneWidget);
    expect(find.byKey(const Key('record-payment')), findsNothing);
    expect(find.byKey(const Key('other-area-payment')), findsNothing);
    expect(find.byKey(const Key('payment-updates')), findsOneWidget);
  });

  testWidgets('tap-time permission recheck blocks a stale visible module',
      (tester) async {
    await _setLargeSurface(tester);
    final permissions = <String>[
      'management.dashboard.view',
      'accounting.view',
    ];
    final session = UserSession(
      userId: 'management-1',
      username: 'management.one',
      displayName: 'Management One',
      role: AppRole.management,
      rawRole: 'Management',
      accessToken: 'management-token',
      permissions: permissions,
    );

    await tester.pumpWidget(MaterialApp(home: _dashboard(session)));
    await tester.pumpAndSettle();

    final accountingTile =
        find.byKey(const Key('management-financial-accounting'));
    expect(accountingTile, findsOneWidget);

    // Simulate a stale already-rendered shell. The tap path must re-check the
    // same server permission instead of trusting visibility alone.
    permissions.remove('accounting.view');
    await tester.ensureVisible(accountingTile);
    await tester.tap(accountingTile);
    await tester.pumpAndSettle();

    expect(
      find.text(
        'Your current server permissions do not allow Financial Accounting.',
      ),
      findsOneWidget,
    );
  });
}

RoleDashboard _dashboard(UserSession session) {
  return RoleDashboard(
    session: session,
    onSignOut: () async {},
    collectorRouteLoader: _UnusedRouteLoader(),
    paymentSubmissionRepository: SpinaPaymentSubmissionRepository(),
    deviceIdentityProvider: DeviceIdentityProvider(
      store: MemoryDeviceIdentityStore(),
      platformResolver: () => 'android',
      appVersionResolver: () async => '1.0.0+1',
    ),
    collectionDeviceSequence: MemoryCollectionDeviceSequence(),
  );
}

Future<void> _setLargeSurface(WidgetTester tester) async {
  await tester.binding.setSurfaceSize(const Size(1100, 1800));
  addTearDown(() async => tester.binding.setSurfaceSize(null));
}

class _UnusedRouteLoader implements CollectorRouteLoader {
  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) {
    throw StateError('Route loading is not expected in navigation tests.');
  }
}
