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
import 'package:gilbic_mobile/src/features/management/management_dashboard.dart';
import 'package:gilbic_mobile/src/features/collector/collector_field_home_page.dart';

void main() {
  for (final roles in [
    ['Management', 'Collector'],
    ['Management', 'Employee', 'Collector'],
    ['Collector'],
    ['Collector', 'Employee'],
  ]) {
    testWidgets(
      'active shell offers authorized workspaces $roles with read-only route',
      (tester) async {
        final session = UserSession(
          userId: 'worker',
          username: 'worker',
          displayName: 'Worker',
          role: AppRole.fromValue(roles.first)!,
          rawRole: roles.first,
          roles: roles,
          accessToken: 'token',
          permissions: const [
            'management.dashboard.view',
            'employee.portal.view',
            'route.view',
          ],
        );
        Future<void> show(UserSession current) async {
          await tester.pumpWidget(
            MaterialApp(
              home: EnhancedRoleDashboard(
                session: current,
                onSignOut: () async {},
                collectorRouteLoader: _RouteLoader(),
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
        }

        await show(session);
        if (roles.contains('Management')) {
          expect(find.byType(ManagementDashboard), findsOneWidget);
          expect(
            identical(
              tester
                  .widget<ManagementDashboard>(find.byType(ManagementDashboard))
                  .session,
              session,
            ),
            isTrue,
          );
        }
        if (roles.length > 1) {
          await tester.tap(find.text('Collector').first);
          await tester.pumpAndSettle();
        }
        expect(find.byType(CollectorFieldHomePage), findsOneWidget);
        expect(find.text('Daily Collection'), findsOneWidget);
        await tester.tap(find.byKey(const Key('route-client-client-readonly')));
        await tester.pumpAndSettle();
        expect(
          find.text(
            'This account does not have permission to record collections.',
          ),
          findsOneWidget,
        );
        await tester.tap(find.text('Payment details / other amount'));
        await tester.pumpAndSettle();
        expect(find.text('Record Collection'), findsNothing);
        Navigator.of(tester.element(find.text('Client Tools'))).pop();
        await tester.pumpAndSettle();
        expect(
          identical(
            tester
                .widget<CollectorFieldHomePage>(
                  find.byType(CollectorFieldHomePage),
                )
                .session,
            session,
          ),
          isTrue,
        );
        if (roles.contains('Employee')) {
          await tester.tap(find.text('Office & staff'));
          await tester.pumpAndSettle();
          expect(find.byType(EmployeeDashboard), findsOneWidget);
        }
        if (roles.contains('Management') && roles.contains('Employee')) {
          await show(
            UserSession(
              userId: 'worker',
              username: 'worker',
              displayName: 'Worker',
              role: session.role,
              rawRole: session.rawRole,
              roles: roles,
              accessToken: 'new-token',
              permissions: const ['management.dashboard.view', 'route.view'],
            ),
          );
          expect(find.byType(ManagementDashboard), findsOneWidget);
          expect(find.text('Office & staff'), findsNothing);
        }
        // A permission refresh removes the selected office/management workspace.
        await show(
          UserSession(
            userId: 'worker',
            username: 'worker',
            displayName: 'Worker',
            role: session.role,
            rawRole: session.rawRole,
            roles: roles,
            accessToken: 'new-token',
            permissions: const ['route.view'],
          ),
        );
        expect(find.byType(CollectorFieldHomePage), findsOneWidget);
        expect(find.byType(EmployeeDashboard), findsNothing);
        expect(find.byType(ManagementDashboard), findsNothing);
        expect(
          find.byKey(const Key('dashboard-permission-denied')),
          findsNothing,
        );
        expect(tester.takeException(), isNull);
      },
    );
  }
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
        entries: [
          CollectorRouteEntry(
            id: 'entry-readonly',
            clientId: 'client-readonly',
            loanId: 'loan-readonly',
            clientName: 'Read-only Client',
            area: 'Area One',
            loanType: 'Regular',
            dailyAmount: 100,
            balance: 1000,
            status: 'Current',
            passCount: 0,
            routeRevision: '1',
          ),
        ],
        expectedTotal: 0,
      ),
      syncedAt: DateTime.utc(2026, 9, 20),
      isFromCache: false,
    );
  }
}
