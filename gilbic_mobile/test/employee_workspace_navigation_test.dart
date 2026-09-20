import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/dashboard/enhanced_role_dashboard.dart';
import 'package:gilbic_mobile/src/features/employee/employee_dashboard.dart';

void main() {
  testWidgets(
    'combined worker switches actual assigned workspaces with one unchanged session',
    (tester) async {
      const session = UserSession(
        userId: 'worker',
        username: 'worker',
        displayName: 'Worker',
        role: AppRole.collector,
        rawRole: 'Collector',
        roles: ['Collector', 'Employee', 'employee_manager'],
        accessToken: 'token',
        permissions: [
          'route.view',
          'collection.create',
          'employee.portal.view',
          'client_onboarding.requirement.review',
        ],
      );
      final loader = _RouteLoader();
      await tester.pumpWidget(
        MaterialApp(
          home: EnhancedRoleDashboard(
            session: session,
            onSignOut: () async {},
            collectorRouteLoader: loader,
            paymentSubmissionRepository: SpinaPaymentSubmissionRepository(),
            deviceIdentityProvider: DeviceIdentityProvider(
              store: MemoryDeviceIdentityStore(),
              platformResolver: () => 'android',
              appVersionResolver: () async => 'test',
            ),
            collectionDeviceSequence: MemoryCollectionDeviceSequence(),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('employee-collector-workspace-switch')),
        findsOneWidget,
      );
      expect(find.text('Daily Collection'), findsOneWidget);
      await tester.tap(find.text('Office & staff'));
      await tester.pumpAndSettle();
      final dashboard = tester.widget<EmployeeDashboard>(
        find.byType(EmployeeDashboard),
      );
      expect(identical(dashboard.session, session), isTrue);
      expect(dashboard.session.role, AppRole.collector);
      expect(find.text('Employee Dashboard'), findsOneWidget);
      expect(find.text('Management'), findsNothing);
      await tester.tap(find.text('Collector'));
      await tester.pumpAndSettle();
      expect(find.text('Daily Collection'), findsOneWidget);
      expect(loader.users.every((user) => identical(user, session)), isTrue);
      expect(tester.takeException(), isNull);
    },
  );
}

class _RouteLoader implements CollectorRouteLoader {
  final users = <UserSession>[];
  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async {
    users.add(session);
    return CollectorRouteLoadResult(
      route: const CollectorRoute(
        routeDate: null,
        collectorName: 'Worker',
        areas: [],
        entries: [],
        expectedTotal: 0,
      ),
      syncedAt: DateTime.utc(2026, 9, 20),
      isFromCache: false,
    );
  }
}
