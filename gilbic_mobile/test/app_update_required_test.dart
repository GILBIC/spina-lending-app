import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/app.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/auth_repository.dart';
import 'package:gilbic_mobile/src/core/auth/session_store.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

const UserSession _session = UserSession(
  userId: 'collector-1',
  username: 'collector.one',
  displayName: 'Collector One',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'access-current',
  refreshToken: 'refresh-current',
  permissions: <String>['route.view', 'collection.create'],
);

class _UpdateBlockingAuthRepository
    implements AuthRepository, SessionValidationRepository {
  @override
  Future<UserSession> validate(UserSession session) async {
    throw const SpinaApiException(
      'This Gilbic Android version is no longer supported. Update to version 0.5.0+5 or later before continuing.',
      statusCode: 426,
    );
  }

  @override
  Future<UserSession> signIn({
    required String username,
    required String password,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<void> signOut(UserSession session) async {}
}

void main() {
  testWidgets('unsupported restored build clears session and blocks app shell',
      (tester) async {
    final store = MemorySessionStore();
    await store.write(_session);

    await tester.pumpWidget(
      GilbicApp(
        sessionStore: store,
        authRepository: _UpdateBlockingAuthRepository(),
        collectorRouteCache: MemoryCollectorRouteCache(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('app-update-required')), findsOneWidget);
    expect(find.text('Update required'), findsOneWidget);
    expect(find.textContaining('Update to version 0.5.0+5'), findsOneWidget);
    expect(find.text('Collector Dashboard'), findsNothing);
    expect(find.byKey(const Key('sign-in-button')), findsNothing);
    expect(await store.read(), isNull);
  });
}
