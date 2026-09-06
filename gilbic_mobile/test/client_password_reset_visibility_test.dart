import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/account/account_repository.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/features/account/account_settings_page.dart';
import 'package:gilbic_mobile/src/features/account/client_password_reset_page.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

final _now = DateTime.utc(2026, 9, 6, 1);

UserSession _session(AppRole role, {required List<String> permissions}) => UserSession(
      userId: 'user-${role.name}',
      username: '${role.name}.one',
      displayName: '${role.label} One',
      role: role,
      rawRole: role.label,
      accessToken: '${role.name}-token',
      permissions: permissions,
    );

class _FakeAccountRepository implements AccountRepository {
  @override
  Future<AccountOverview> fetch(UserSession session) async => AccountOverview(
        profile: AccountProfile(
          id: session.userId,
          username: session.username,
          fullName: session.displayName,
          role: session.rawRole,
          status: 'active',
        ),
        devices: <AccountDevice>[
          AccountDevice(
            id: 'device-current',
            platform: 'android',
            status: 'active',
            registeredAt: _now,
            isCurrent: true,
          ),
        ],
      );

  @override
  Future<void> changePassword(UserSession session, String password) async {}

  @override
  Future<AccountDevice> revokeDevice(UserSession session, String deviceId) async {
    throw UnimplementedError();
  }
}

DeviceIdentityProvider _identity() => DeviceIdentityProvider(
      store: MemoryDeviceIdentityStore(),
      platformResolver: () => 'android',
      appVersionResolver: () async => '0.4.0+4',
      randomByteGenerator: (length) => List<int>.filled(length, 4),
    );

Future<void> _pump(
  WidgetTester tester,
  UserSession session,
) async {
  await tester.pumpWidget(
    MaterialApp(
      home: AccountSettingsPage(
        session: session,
        repository: _FakeAccountRepository(),
        deviceIdentityProvider: _identity(),
        onSignOut: () async {},
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  for (final role in <AppRole>[AppRole.employee, AppRole.management]) {
    testWidgets('${role.name} with client.credential.manage can open Client password reset',
        (tester) async {
      await _pump(
        tester,
        _session(role, permissions: const <String>['client.credential.manage']),
      );

      await tester.drag(find.byType(ListView), const Offset(0, -320));
      await tester.pumpAndSettle();

      final resetControl = find.byKey(const Key('account-reset-client-password'));
      expect(resetControl, findsOneWidget);
      expect(find.text('Reset Client password'), findsOneWidget);

      await tester.tap(resetControl);
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('client-password-reset-page')), findsOneWidget);
      expect(find.text('Search Client accounts by name, username, or email.'), findsOneWidget);
    });
  }

  testWidgets('Client password reset starts with one simple search control', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: ClientPasswordResetPage(
          session: _session(
            AppRole.employee,
            permissions: const <String>['client.credential.manage'],
          ),
          deviceIdentityProvider: _identity(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('client-password-search')), findsOneWidget);
    expect(find.byKey(const Key('client-password-search-submit')), findsOneWidget);
    expect(find.text('Search'), findsOneWidget);
  });

  testWidgets('Client password search uses the protected scoped endpoint and shows results',
      (tester) async {
    var requests = 0;
    await http.runWithClient(
      () async {
        await tester.pumpWidget(
          MaterialApp(
            home: ClientPasswordResetPage(
              session: _session(
                AppRole.employee,
                permissions: const <String>['client.credential.manage'],
              ),
              deviceIdentityProvider: _identity(),
            ),
          ),
        );
        await tester.pumpAndSettle();

        await tester.enterText(
          find.byKey(const Key('client-password-search')),
          '  Maria Santos  ',
        );
        await tester.tap(find.byKey(const Key('client-password-search-submit')));
        await tester.pumpAndSettle();

        expect(requests, 1);
        expect(find.text('Maria Santos'), findsOneWidget);
        expect(find.textContaining('spina.c.001'), findsOneWidget);
        expect(find.textContaining('client@example.com'), findsOneWidget);
      },
      () => MockClient((request) async {
        requests += 1;
        expect(request.method, 'GET');
        expect(request.url.path, '/api/v1/management/client-accounts');
        expect(request.url.queryParameters['q'], 'Maria Santos');
        expect(request.headers['Authorization'], 'Bearer employee-token');
        expect(request.headers['X-Device-Id'], startsWith('gilbic-'));
        return http.Response(
          jsonEncode(<String, Object?>{
            'success': true,
            'data': <String, Object?>{
              'accounts': <Object?>[
                <String, Object?>{
                  'id': '33333333-3333-4333-8333-333333333333',
                  'username': 'spina.c.001',
                  'email': 'client@example.com',
                  'full_name': 'Maria Santos',
                  'status': 'active',
                  'roles': <String>['client'],
                  'device_count': 0,
                  'created_at': '2026-09-05T13:00:00Z',
                  'updated_at': '2026-09-05T13:00:00Z',
                },
              ],
            },
          }),
          200,
          headers: const <String, String>{'content-type': 'application/json'},
        );
      }),
    );
  });

  for (final role in <AppRole>[AppRole.client, AppRole.collector]) {
    testWidgets('${role.name} cannot see Client password reset', (tester) async {
      await _pump(tester, _session(role, permissions: const <String>[]));

      await tester.drag(find.byType(ListView), const Offset(0, -500));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('account-reset-client-password')), findsNothing);
    });
  }
}
