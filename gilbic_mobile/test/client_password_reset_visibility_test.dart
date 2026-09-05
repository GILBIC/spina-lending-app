import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/account/account_repository.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/features/account/account_settings_page.dart';

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

      expect(find.byKey(const Key('account-reset-client-password')), findsOneWidget);
      expect(find.text('Reset Client password'), findsOneWidget);
    });
  }

  for (final role in <AppRole>[AppRole.client, AppRole.collector]) {
    testWidgets('${role.name} cannot see Client password reset', (tester) async {
      await _pump(tester, _session(role, permissions: const <String>[]));

      expect(find.byKey(const Key('account-reset-client-password')), findsNothing);
    });
  }
}
