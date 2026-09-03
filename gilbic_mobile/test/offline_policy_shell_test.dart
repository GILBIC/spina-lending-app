import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan_repository.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/dashboard/enhanced_role_dashboard.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

void main() {
  const platforms = <TargetPlatform>[
    TargetPlatform.android,
    TargetPlatform.iOS,
  ];

  for (final platform in platforms) {
    final platformName = platform == TargetPlatform.android ? 'Android' : 'iOS';
    for (final role in AppRole.values) {
      testWidgets(
        '$platformName ${role.label} shell keeps its role identity and offline rule',
        (tester) async {
          await _runForPlatform(platform, () async {
            await tester.binding.setSurfaceSize(const Size(900, 1400));
            addTearDown(() async {
              await tester.binding.setSurfaceSize(null);
            });

            final session = _sessionFor(role);
            await tester.pumpWidget(
              MaterialApp(
                theme: SpinaTheme.light,
                home: EnhancedRoleDashboard(
                  session: session,
                  onSignOut: () async {},
                  collectorRouteLoader: _UnusedRouteLoader(),
                  paymentSubmissionRepository: _UnusedPaymentRepository(),
                  deviceIdentityProvider: DeviceIdentityProvider(
                    store: MemoryDeviceIdentityStore(),
                    platformResolver: () =>
                        platform == TargetPlatform.android ? 'android' : 'ios',
                    appVersionResolver: () async => '1.0.0',
                    randomByteGenerator: (length) =>
                        List<int>.filled(length, 7),
                  ),
                  collectionDeviceSequence: MemoryCollectionDeviceSequence(),
                  clientLoanRepository: _EmptyClientLoanRepository(),
                ),
              ),
            );
            await tester.pumpAndSettle();

            final theme = Theme.of(tester.element(find.byType(Scaffold).first));
            expect(theme.platform, platform);
            expect(theme.colorScheme.primary, SpinaTheme.brandPink);
            final roleHeading = switch (role) {
              AppRole.management => 'Management',
              AppRole.employee => 'Employee Dashboard',
              AppRole.collector => 'Daily Collection',
              AppRole.client => 'SPINA',
            };
            expect(find.text(roleHeading), findsOneWidget);

            if (role == AppRole.collector) {
              expect(
                find.byKey(const Key('collector-more-tab')),
                findsOneWidget,
              );
              await tester.tap(find.byKey(const Key('collector-more-tab')));
              await tester.pumpAndSettle();
              expect(
                find.byKey(const Key('collector-more-offline')),
                findsNothing,
              );
              return;
            }

            final policyLauncher = switch (role) {
              AppRole.management => find.byKey(
                const Key('management-offline-policy'),
              ),
              AppRole.employee => find.byKey(const Key('employee-offline')),
              AppRole.client => find.byKey(const Key('open-offline-policy')),
              AppRole.collector => throw StateError(
                'Collector returned above.',
              ),
            };
            expect(policyLauncher, findsOneWidget);
            await tester.tap(policyLauncher);
            await tester.pumpAndSettle();

            expect(
              find.byKey(const Key('offline-policy-page')),
              findsOneWidget,
            );
            expect(find.text('${role.label} offline policy'), findsOneWidget);
          });
        },
      );
    }
  }

  testWidgets('permission-denied shell still exposes offline safety policy', (
    tester,
  ) async {
    final session = UserSession(
      userId: 'restricted-collector',
      username: 'collector.restricted',
      displayName: 'Restricted Collector',
      role: AppRole.collector,
      rawRole: 'Collector',
      accessToken: 'token',
      permissions: const <String>['route.view'],
    );

    await tester.pumpWidget(
      MaterialApp(
        home: EnhancedRoleDashboard(
          session: session,
          onSignOut: () async {},
          collectorRouteLoader: _UnusedRouteLoader(),
          paymentSubmissionRepository: _UnusedPaymentRepository(),
          deviceIdentityProvider: DeviceIdentityProvider(
            store: MemoryDeviceIdentityStore(),
            platformResolver: () => 'android',
            appVersionResolver: () async => '1.0.0',
            randomByteGenerator: (length) => List<int>.filled(length, 7),
          ),
          collectionDeviceSequence: MemoryCollectionDeviceSequence(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(
      find.byKey(const Key('dashboard-permission-denied')),
      findsOneWidget,
    );
    expect(find.byKey(const Key('open-offline-policy')), findsOneWidget);
    await tester.tap(find.byKey(const Key('open-offline-policy')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('offline-policy-page')), findsOneWidget);
  });
}

Future<void> _runForPlatform(
  TargetPlatform platform,
  Future<void> Function() action,
) async {
  final previousPlatform = debugDefaultTargetPlatformOverride;
  debugDefaultTargetPlatformOverride = platform;
  try {
    await action();
  } finally {
    debugDefaultTargetPlatformOverride = previousPlatform;
  }
}

UserSession _sessionFor(AppRole role) {
  final permissions = switch (role) {
    AppRole.client => const <String>['loan.self.view'],
    AppRole.collector => const <String>['route.view', 'collection.create'],
    AppRole.employee => const <String>['employee.portal.view'],
    AppRole.management => const <String>['management.dashboard.view'],
  };
  return UserSession(
    userId: '${role.name}-shell',
    username: '${role.name}.one',
    displayName: '${role.label} One',
    role: role,
    rawRole: role.label,
    accessToken: 'token-${role.name}',
    permissions: permissions,
  );
}

class _UnusedRouteLoader implements CollectorRouteLoader {
  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async {
    return CollectorRouteLoadResult(
      route: const CollectorRoute(
        routeDate: null,
        collectorName: 'Unused',
        areas: <String>[],
        entries: <CollectorRouteEntry>[],
        expectedTotal: 0,
      ),
      syncedAt: DateTime.utc(2026, 8, 15),
      isFromCache: false,
    );
  }
}

class _UnusedPaymentRepository implements PaymentSubmissionRepository {
  @override
  Future<PaymentSubmissionResult> submit(
    UserSession session,
    PaymentSubmissionDraft draft,
  ) {
    throw StateError('Unexpected payment submission.');
  }
}

class _EmptyClientLoanRepository implements ClientLoanRepository {
  @override
  Future<ClientLoanPortfolio> loadPortfolio(
    UserSession session, {
    required String deviceId,
  }) async {
    return ClientLoanPortfolio(
      clientId: session.userId,
      clientCode: 'CLIENT-EMPTY',
      clientName: session.displayName,
      clientStatus: 'active',
      loans: const <ClientLoan>[],
    );
  }
}
