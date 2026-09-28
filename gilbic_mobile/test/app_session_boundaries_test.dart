import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/app.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/auth_repository.dart';
import 'package:gilbic_mobile/src/core/auth/session_store.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/auth/login_page.dart';
import 'package:gilbic_mobile/src/features/dashboard/enhanced_role_dashboard.dart';
import 'support/app_platform_dependencies.dart';

UserSession account(String name, {bool refresh = false}) => UserSession(
  userId: name,
  username: name,
  displayName: name,
  role: AppRole.employee,
  rawRole: 'Employee',
  accessToken: '$name-token',
  refreshToken: refresh ? '$name-refresh' : null,
  expiresAt: DateTime.now().toUtc().add(const Duration(minutes: 3)),
);

class DelayedAuth
    implements
        AuthRepository,
        SessionValidationRepository,
        SessionRefreshRepository {
  final pending = Completer<UserSession>();
  Completer<void>? logout;
  int validations = 0;
  @override
  Future<UserSession> validate(UserSession session) async =>
      ++validations == 1 || session.userId == 'bob' ? session : pending.future;
  @override
  Future<UserSession> refresh(UserSession session) => pending.future;
  @override
  Future<UserSession> signIn({
    required String username,
    required String password,
  }) async => account(username);
  @override
  Future<void> signOut(UserSession session) async => logout?.future;
}

void main() {
  for (final refresh in [false, true]) {
    for (final status in [200, 401, 403, 426]) {
      for (final nextAccount in [false, true]) {
        testWidgets(
          'late ${refresh ? 'refresh' : 'validation'} $status preserves ${nextAccount ? 'new account' : 'logout'}',
          (tester) async {
            final store = MemorySessionStore();
            final alice = account('alice', refresh: refresh);
            await store.write(alice);
            final auth = DelayedAuth();
            final images = testAppImageRecovery();
            await tester.pumpWidget(
              GilbicApp(
                sessionStore: store,
                authRepository: auth,
                imageRecoveryController: images,
                deviceIdentityProvider: testAppDeviceIdentity(),
                collectorRouteCache: MemoryCollectorRouteCache(),
              ),
            );
            await tester.pumpAndSettle();
            if (refresh) {
              await tester.pump(const Duration(minutes: 1, seconds: 1));
            } else {
              tester.binding.handleAppLifecycleStateChanged(
                AppLifecycleState.inactive,
              );
              tester.binding.handleAppLifecycleStateChanged(
                AppLifecycleState.resumed,
              );
              await tester.pump();
            }
            await tester
                .widget<EnhancedRoleDashboard>(
                  find.byType(EnhancedRoleDashboard),
                )
                .onSignOut();
            await tester.pumpAndSettle();
            if (nextAccount) {
              await tester
                  .widget<LoginPage>(find.byType(LoginPage))
                  .onSignIn('bob', 'synthetic');
              await tester.pumpAndSettle();
            }
            if (status == 200) {
              auth.pending.complete(account('alice'));
            } else {
              auth.pending.completeError(
                SpinaApiException('Denied', statusCode: status),
              );
            }
            await tester.pumpAndSettle();
            expect((await store.read())?.userId, nextAccount ? 'bob' : null);
            expect(
              find.byType(EnhancedRoleDashboard),
              nextAccount ? findsOneWidget : findsNothing,
            );
            expect(find.byKey(const Key('app-update-required')), findsNothing);
            await tester.pumpWidget(const SizedBox());
            alice.clearRefreshOverride();
          },
        );
      }
    }
  }
  testWidgets('local sign-out completes while remote revocation is stalled', (
    tester,
  ) async {
    final store = MemorySessionStore();
    await store.write(account('alice'));
    final auth = DelayedAuth()..logout = Completer<void>();
    final images = testAppImageRecovery();
    await tester.pumpWidget(
      GilbicApp(
        sessionStore: store,
        authRepository: auth,
        imageRecoveryController: images,
        deviceIdentityProvider: testAppDeviceIdentity(),
        collectorRouteCache: MemoryCollectorRouteCache(),
      ),
    );
    await tester.pumpAndSettle();
    var completed = false;
    unawaited(
      tester
          .widget<EnhancedRoleDashboard>(find.byType(EnhancedRoleDashboard))
          .onSignOut()
          .then((_) => completed = true),
    );
    await tester.pumpAndSettle();
    final persisted = await store.read();
    final signedOut = find.byType(LoginPage).evaluate().isNotEmpty;
    auth.logout!.complete();
    await tester.pumpAndSettle();
    await tester.pumpWidget(const SizedBox());
    expect(persisted, isNull);
    expect(signedOut, isTrue);
    expect(completed, isTrue);
  });
}
