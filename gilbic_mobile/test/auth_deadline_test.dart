import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/app.dart';
import 'package:gilbic_mobile/src/core/auth/session_store.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_repository.dart';
import 'package:gilbic_mobile/src/features/dashboard/enhanced_role_dashboard.dart';
import 'package:gilbic_mobile/src/features/auth/login_page.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/auth_repository.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/app_platform_dependencies.dart';

void main() {
  for (final expires in [false, true]) {
    testWidgets(
      'temporary resume validation ${expires ? 'rejects expired session' : 'restores consumed refresh timer'}',
      (tester) async {
        final session = _ExpiringSession();
        final store = MemorySessionStore();
        await store.write(session);
        final auth = _ResumeAuth();
        await tester.pumpWidget(
          GilbicApp(
            sessionStore: store,
            authRepository: auth,
            imageRecoveryController: testAppImageRecovery(),
            deviceIdentityProvider: testAppDeviceIdentity(),
            collectorRouteCache: MemoryCollectorRouteCache(),
            collectorRouteRepository: _OfflineRoute(),
          ),
        );
        await tester.pumpAndSettle();
        tester.binding.handleAppLifecycleStateChanged(
          AppLifecycleState.inactive,
        );
        tester.binding.handleAppLifecycleStateChanged(
          AppLifecycleState.resumed,
        );
        await tester.pump();
        // The normal refresh timer fires while validation owns the in-flight guard.
        await tester.pump(const Duration(seconds: 6));
        session.expired = expires;
        auth.pending.completeError(
          const SpinaApiException('Temporary timeout'),
        );
        await tester.pumpAndSettle();
        if (expires) {
          expect(find.byType(LoginPage), findsOneWidget);
          expect(await store.read(), isNull);
        } else {
          await tester.pump(const Duration(seconds: 6));
          await tester.pumpAndSettle();
          expect((await store.read())?.accessToken, 'resumed-renewed');
        }
        await tester.pumpWidget(const SizedBox());
        session.clearRefreshOverride();
      },
    );
  }
  testWidgets(
    'session expiring during stalled startup cannot enter offline fallback',
    (tester) async {
      final session = _ExpiringSession();
      final store = MemorySessionStore();
      await store.write(session);
      final auth = SpinaAuthRepository(
        deviceIdentityProvider: testAppDeviceIdentity(),
        client: MockClient((_) => Completer<http.Response>().future),
      );
      await tester.pumpWidget(
        GilbicApp(
          sessionStore: store,
          authRepository: auth,
          imageRecoveryController: testAppImageRecovery(),
          deviceIdentityProvider: testAppDeviceIdentity(),
          collectorRouteCache: MemoryCollectorRouteCache(),
          collectorRouteRepository: _OfflineRoute(),
        ),
      );
      await tester.pump();
      session.expired = true;
      await tester.pump(const Duration(seconds: 16));
      await tester.pumpAndSettle();
      expect(find.byType(LoginPage), findsOneWidget);
      expect(await store.read(), isNull);
      await tester.pumpWidget(const SizedBox());
    },
  );
  testWidgets('expired stored session cannot fall back when refresh stalls', (
    tester,
  ) async {
    final store = MemorySessionStore();
    await store.write(
      UserSession(
        userId: 'expired',
        username: 'expired',
        displayName: 'Expired',
        role: AppRole.collector,
        rawRole: 'Collector',
        permissions: const ['route.view'],
        accessToken: 'expired-token',
        refreshToken: 'refresh',
        expiresAt: DateTime.now().toUtc().subtract(const Duration(minutes: 1)),
      ),
    );
    final auth = SpinaAuthRepository(
      deviceIdentityProvider: testAppDeviceIdentity(),
      client: MockClient((_) => Completer<http.Response>().future),
    );
    await tester.pumpWidget(
      GilbicApp(
        sessionStore: store,
        authRepository: auth,
        imageRecoveryController: testAppImageRecovery(),
        deviceIdentityProvider: testAppDeviceIdentity(),
        collectorRouteCache: MemoryCollectorRouteCache(),
        collectorRouteRepository: _OfflineRoute(),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(seconds: 16));
    await tester.pumpAndSettle();
    expect(find.byType(LoginPage), findsOneWidget);
    expect(await store.read(), isNull);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets(
    'stalled startup reaches cached read-only route and stalled refresh retries with new memberships',
    (tester) async {
      final store = MemorySessionStore();
      final session = UserSession(
        userId: 'deadline',
        username: 'deadline',
        displayName: 'Deadline',
        role: AppRole.collector,
        rawRole: 'Collector',
        roles: const ['Collector', 'Employee'],
        permissions: const [
          'route.view',
          'collection.create',
          'employee.portal.view',
        ],
        accessToken: 'token',
        refreshToken: 'refresh',
        expiresAt: DateTime.now().toUtc().add(const Duration(minutes: 1)),
      );
      await store.write(session);
      final cache = MemoryCollectorRouteCache();
      await cache.writeForUser(
        session.userId,
        const CollectorRoute(
          routeDate: null,
          collectorName: 'Deadline',
          areas: [],
          entries: [],
          expectedTotal: 0,
        ),
        DateTime.now().toUtc(),
      );
      final lateValidation = Completer<http.Response>();
      final lateRefresh = Completer<http.Response>();
      var refreshes = 0;
      final auth = SpinaAuthRepository(
        deviceIdentityProvider: testAppDeviceIdentity(),
        client: MockClient((request) {
          if (request.method == 'GET') return lateValidation.future;
          if (++refreshes == 1) return lateRefresh.future;
          return Future.value(
            http.Response(
              jsonEncode({
                'data': {
                  'access_token': 'renewed',
                  'refresh_token': 'renewed-refresh',
                  'expires_at': DateTime.now()
                      .toUtc()
                      .add(const Duration(hours: 1))
                      .toIso8601String(),
                  'user': {
                    'id': 'deadline',
                    'username': 'deadline',
                    'display_name': 'Deadline',
                    'role': 'Collector',
                    'roles': ['Collector'],
                    'permissions': ['route.view'],
                  },
                },
              }),
              200,
            ),
          );
        }),
      );
      await tester.pumpWidget(
        GilbicApp(
          sessionStore: store,
          authRepository: auth,
          imageRecoveryController: testAppImageRecovery(),
          deviceIdentityProvider: testAppDeviceIdentity(),
          collectorRouteCache: cache,
          collectorRouteRepository: _OfflineRoute(),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(seconds: 16));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('collector-offline-read-only')),
        findsOneWidget,
      );
      expect(find.text('Office & staff'), findsOneWidget);
      await tester.pump(const Duration(seconds: 16));
      await tester.pump(const Duration(seconds: 31));
      await tester.pumpAndSettle();
      expect((await store.read())?.accessToken, 'renewed');
      expect(find.text('Office & staff'), findsNothing);
      expect(
        find.byKey(const Key('collector-offline-read-only')),
        findsOneWidget,
      );
      await tester
          .widget<EnhancedRoleDashboard>(find.byType(EnhancedRoleDashboard))
          .onSignOut();
      await tester.pumpAndSettle();
      lateValidation.complete(http.Response('{}', 426));
      lateRefresh.complete(http.Response('{}', 200));
      await tester.pumpAndSettle();
      expect(find.byType(LoginPage), findsOneWidget);
      expect(await store.read(), isNull);
      expect(find.byKey(const Key('app-update-required')), findsNothing);
      await tester.pumpWidget(const SizedBox());
      session.clearRefreshOverride();
    },
  );
  for (final operation in ['login', 'validation', 'refresh']) {
    testWidgets('stalled $operation reaches recoverable error by deadline', (
      tester,
    ) async {
      final pending = Completer<http.Response>();
      final repository = SpinaAuthRepository(
        client: MockClient((_) => pending.future),
        deviceIdentityProvider: testAppDeviceIdentity(),
      );
      const session = UserSession(
        userId: 'deadline',
        username: 'deadline',
        displayName: 'Deadline',
        role: AppRole.collector,
        rawRole: 'Collector',
        accessToken: 'token',
        refreshToken: 'refresh',
      );
      Object? failure;
      final request = switch (operation) {
        'login' => repository.signIn(
          username: 'deadline',
          password: 'synthetic',
        ),
        'validation' => repository.validate(session),
        _ => repository.refresh(session),
      };
      unawaited(
        request.then<void>(
          (_) {},
          onError: (Object error) {
            failure = error;
          },
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(seconds: 16));
      expect(failure, isA<SpinaApiException>());
      expect((failure as SpinaApiException).statusCode, isNull);
      // Completing the abandoned transport must not produce a second outcome.
      pending.complete(http.Response('{}', 401));
      await tester.pump();
      expect((failure as SpinaApiException).statusCode, isNull);
    });
  }
}

class _OfflineRoute implements CollectorRouteRepository {
  @override
  Future<CollectorRoute> fetchToday(UserSession session) async =>
      throw const SpinaApiException('Offline');
}

class _ExpiringSession extends UserSession {
  _ExpiringSession()
    : super(
        userId: 'expiring',
        username: 'expiring',
        displayName: 'Expiring',
        role: AppRole.collector,
        rawRole: 'Collector',
        accessToken: 'token',
        refreshToken: 'refresh',
        expiresAt: DateTime.now().toUtc().add(
          const Duration(minutes: 2, seconds: 5),
        ),
        permissions: const ['route.view'],
      );
  bool expired = false;
  @override
  bool get isExpired => expired;
}

class _ResumeAuth
    implements
        AuthRepository,
        SessionValidationRepository,
        SessionRefreshRepository {
  final pending = Completer<UserSession>();
  int validations = 0;
  @override
  Future<UserSession> validate(UserSession session) async =>
      ++validations == 1 ? session : pending.future;
  @override
  Future<UserSession> refresh(UserSession session) async => UserSession(
    userId: session.userId,
    username: session.username,
    displayName: session.displayName,
    role: session.role,
    rawRole: session.rawRole,
    permissions: session.permissions,
    accessToken: 'resumed-renewed',
    refreshToken: 'renewed-refresh',
    expiresAt: DateTime.now().toUtc().add(const Duration(hours: 1)),
  );
  @override
  Future<UserSession> signIn({
    required String username,
    required String password,
  }) => throw UnimplementedError();
  @override
  Future<void> signOut(UserSession session) async {}
}
