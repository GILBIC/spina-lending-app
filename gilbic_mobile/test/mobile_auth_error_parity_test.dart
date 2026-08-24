import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/app.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/auth_repository.dart';
import 'package:gilbic_mobile/src/core/auth/session_store.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

void main() {
  const platforms = <TargetPlatform>[
    TargetPlatform.android,
    TargetPlatform.iOS,
  ];

  for (final platform in platforms) {
    final platformName = platform == TargetPlatform.android ? 'Android' : 'iOS';

    testWidgets('$platformName authenticates into the server-authorized role',
        (tester) async {
      await _runForPlatform(platform, () async {
        final store = MemorySessionStore();
        final session = _employeeSession('$platformName-auth');
        final repository = _ParityAuthRepository(
          onSignIn: (_, __) async => session,
        );

        await _pumpApp(tester, store: store, repository: repository);
        await tester.enterText(
          find.byKey(const Key('username-field')),
          'employee.one',
        );
        await tester.enterText(
          find.byKey(const Key('password-field')),
          'secret',
        );
        await tester.tap(find.byKey(const Key('sign-in-button')));
        await tester.pumpAndSettle();

        expect(find.text('Employee Dashboard'), findsOneWidget);
        expect((await store.read())?.role, AppRole.employee);
      });
    });

    testWidgets('$platformName revoked device clears session with notice',
        (tester) async {
      await _runForPlatform(platform, () async {
        final store = MemorySessionStore();
        final session = _employeeSession('$platformName-revoked');
        await store.write(session);
        final repository = _ParityAuthRepository(
          onValidate: (_) async => throw const SpinaApiException(
            'This device has been revoked.',
            statusCode: 403,
            code: 'device_revoked',
          ),
        );

        await _pumpApp(tester, store: store, repository: repository);

        expect(find.byKey(const Key('sign-in-button')), findsOneWidget);
        expect(find.byKey(const Key('session-notice')), findsOneWidget);
        expect(
          find.text(
            'This account or device is no longer authorized for this session. '
            'Sign in again or contact Management.',
          ),
          findsOneWidget,
        );
        expect(await store.read(), isNull);
      });
    });

    testWidgets('$platformName stale session fails closed with expiry notice',
        (tester) async {
      await _runForPlatform(platform, () async {
        final store = MemorySessionStore();
        final expired = _employeeSession(
          '$platformName-expired',
          refreshToken: 'refresh-token',
          expiresAt: DateTime.now().toUtc().subtract(const Duration(minutes: 5)),
        );
        await store.write(expired);
        final repository = _ParityAuthRepository(
          onRefresh: (_) async => throw const SpinaApiException(
            'Refresh token is no longer valid.',
            statusCode: 401,
            code: 'session_expired',
          ),
        );

        await _pumpApp(tester, store: store, repository: repository);

        expect(find.byKey(const Key('sign-in-button')), findsOneWidget);
        expect(find.byKey(const Key('session-notice')), findsOneWidget);
        expect(
          find.text(
            'Your login session expired or is no longer valid. Sign in again.',
          ),
          findsOneWidget,
        );
        expect(await store.read(), isNull);
      });
    });

    testWidgets('$platformName permission removal fails closed before navigation',
        (tester) async {
      await _runForPlatform(platform, () async {
        final store = MemorySessionStore();
        final restricted = UserSession(
          userId: '$platformName-collector-restricted',
          username: 'collector.one',
          displayName: 'Restricted Collector',
          role: AppRole.collector,
          rawRole: 'Collector',
          accessToken: 'restricted-token',
          permissions: const <String>['route.view'],
        );
        await store.write(restricted);
        final repository = _ParityAuthRepository(
          onValidate: (_) async => restricted,
        );

        await _pumpApp(tester, store: store, repository: repository);

        expect(
          find.byKey(const Key('dashboard-permission-denied')),
          findsOneWidget,
        );
        expect(find.text('Collector Dashboard'), findsNothing);
        expect(find.byKey(const Key('daily-route')), findsNothing);
      });
    });

    testWidgets('$platformName keeps a valid session during network validation failure',
        (tester) async {
      await _runForPlatform(platform, () async {
        final store = MemorySessionStore();
        final session = _employeeSession('$platformName-network-session');
        await store.write(session);
        final repository = _ParityAuthRepository(
          onValidate: (_) async => throw const SpinaApiException(
            'Gilbic could not verify the login session. Check the connection and try again.',
            code: 'network_unavailable',
          ),
        );

        await _pumpApp(tester, store: store, repository: repository);

        expect(find.text('Employee Dashboard'), findsOneWidget);
        expect(await store.read(), isNotNull);
        expect(find.byKey(const Key('session-notice')), findsNothing);
      });
    });

    testWidgets('$platformName login network failure stays on sign-in with error',
        (tester) async {
      await _runForPlatform(platform, () async {
        final store = MemorySessionStore();
        final repository = _ParityAuthRepository(
          onSignIn: (_, __) async => throw const SpinaApiException(
            'Gilbic could not reach the Gilbic server. Check the connection and try again.',
            code: 'network_unavailable',
          ),
        );

        await _pumpApp(tester, store: store, repository: repository);
        await tester.enterText(
          find.byKey(const Key('username-field')),
          'employee.one',
        );
        await tester.enterText(
          find.byKey(const Key('password-field')),
          'secret',
        );
        await tester.tap(find.byKey(const Key('sign-in-button')));
        await tester.pumpAndSettle();

        expect(find.byKey(const Key('login-error')), findsOneWidget);
        expect(
          find.text(
            'Gilbic could not reach the Gilbic server. Check the connection and try again.',
          ),
          findsOneWidget,
        );
        expect(await store.read(), isNull);
      });
    });

    testWidgets('$platformName enforces server-required app update', (tester) async {
      await _runForPlatform(platform, () async {
        final store = MemorySessionStore();
        final repository = _ParityAuthRepository(
          onSignIn: (_, __) async => throw const SpinaApiException(
            'Gilbic 1.2.0 or later is required.',
            statusCode: 426,
            code: 'app_update_required',
          ),
        );

        await _pumpApp(tester, store: store, repository: repository);
        await tester.enterText(
          find.byKey(const Key('username-field')),
          'employee.one',
        );
        await tester.enterText(
          find.byKey(const Key('password-field')),
          'secret',
        );
        await tester.tap(find.byKey(const Key('sign-in-button')));
        await tester.pumpAndSettle();

        expect(find.byKey(const Key('app-update-required')), findsOneWidget);
        expect(find.text('Gilbic 1.2.0 or later is required.'), findsOneWidget);
        expect(await store.read(), isNull);
      });
    });

    test('$platformName device identity reports the canonical platform code', () async {
      await _runForPlatform(platform, () async {
        final provider = DeviceIdentityProvider(
          store: MemoryDeviceIdentityStore(),
          appVersionResolver: () async => '1.2.0+10',
          randomByteGenerator: (length) => List<int>.filled(length, 7),
        );

        final identity = await provider.load();

        expect(
          identity.platform,
          platform == TargetPlatform.android ? 'android' : 'ios',
        );
        expect(identity.appVersion, '1.2.0+10');
        expect(identity.installationId, startsWith('gilbic-'));
      });
    });
  }
}

Future<void> _runForPlatform(
  TargetPlatform platform,
  Future<void> Function() action,
) async {
  final previous = debugDefaultTargetPlatformOverride;
  debugDefaultTargetPlatformOverride = platform;
  try {
    await action();
  } finally {
    debugDefaultTargetPlatformOverride = previous;
  }
}

Future<void> _pumpApp(
  WidgetTester tester, {
  required MemorySessionStore store,
  required AuthRepository repository,
}) async {
  await tester.pumpWidget(
    GilbicApp(
      sessionStore: store,
      authRepository: repository,
      collectorRouteCache: MemoryCollectorRouteCache(),
    ),
  );
  await tester.pumpAndSettle();
}

UserSession _employeeSession(
  String suffix, {
  String? refreshToken,
  DateTime? expiresAt,
}) {
  return UserSession(
    userId: 'employee-$suffix',
    username: 'employee.one',
    displayName: 'Employee One',
    role: AppRole.employee,
    rawRole: 'Employee',
    accessToken: 'access-$suffix',
    refreshToken: refreshToken,
    permissions: const <String>['employee.portal.view'],
    expiresAt: expiresAt,
  );
}

class _ParityAuthRepository
    implements AuthRepository, SessionValidationRepository, SessionRefreshRepository {
  _ParityAuthRepository({
    this.onSignIn,
    this.onValidate,
    this.onRefresh,
  });

  final Future<UserSession> Function(String username, String password)? onSignIn;
  final Future<UserSession> Function(UserSession session)? onValidate;
  final Future<UserSession> Function(UserSession session)? onRefresh;

  @override
  Future<UserSession> signIn({
    required String username,
    required String password,
  }) {
    final callback = onSignIn;
    if (callback == null) {
      throw StateError('Unexpected sign-in call.');
    }
    return callback(username, password);
  }

  @override
  Future<UserSession> validate(UserSession session) {
    final callback = onValidate;
    return callback == null ? Future<UserSession>.value(session) : callback(session);
  }

  @override
  Future<UserSession> refresh(UserSession session) {
    final callback = onRefresh;
    if (callback == null) {
      throw StateError('Unexpected refresh call.');
    }
    return callback(session);
  }

  @override
  Future<void> signOut(UserSession session) async {}
}
