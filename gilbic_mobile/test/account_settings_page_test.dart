import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/account/account_repository.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/features/account/account_settings_page.dart';

final _registeredAt = DateTime.utc(2026, 8, 15, 1);
final _lastSeenAt = DateTime.utc(2026, 8, 15, 2);

const _session = UserSession(
  userId: 'user-1',
  username: 'collector.one',
  displayName: 'Collector One',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'access-token',
  refreshToken: 'refresh-token',
  permissions: <String>['route.view', 'collection.create'],
);

const _clientSession = UserSession(
  userId: 'client-1',
  username: 'ana.client',
  displayName: 'Ana Client',
  role: AppRole.client,
  rawRole: 'Client',
  accessToken: 'client-token',
  permissions: <String>['loan.self.view'],
);

UserSession _staffSession(AppRole role) {
  final rawRole = switch (role) {
    AppRole.collector => 'Collector',
    AppRole.employee => 'Employee',
    AppRole.management => 'Management',
    AppRole.client => 'Client',
  };
  return UserSession(
    userId: 'staff-${role.name}',
    username: '${role.name}.one',
    displayName: '$rawRole One',
    role: role,
    rawRole: rawRole,
    accessToken: '${role.name}-token',
    permissions: const <String>[],
  );
}

class _FakeAccountRepository implements AccountRepository {
  var revoked = false;
  String? changedPassword;

  @override
  Future<AccountOverview> fetch(UserSession session) async {
    return AccountOverview(
      profile: const AccountProfile(
        id: 'user-1',
        username: 'collector.one',
        fullName: 'Collector One',
        role: 'Collector',
        status: 'active',
        email: 'collector@example.com',
      ),
      devices: <AccountDevice>[
        AccountDevice(
          id: 'device-current',
          platform: 'android',
          appVersion: '0.4.0+4',
          status: 'active',
          registeredAt: _registeredAt,
          lastSeenAt: _lastSeenAt,
          isCurrent: true,
        ),
        AccountDevice(
          id: 'device-old',
          platform: 'ios',
          appVersion: '0.3.0+3',
          status: 'active',
          registeredAt: _registeredAt,
          lastSeenAt: _lastSeenAt,
          isCurrent: false,
        ),
      ],
    );
  }

  @override
  Future<AccountDevice> revokeDevice(
    UserSession session,
    String deviceId,
  ) async {
    expect(deviceId, 'device-old');
    revoked = true;
    return AccountDevice(
      id: 'device-old',
      platform: 'ios',
      appVersion: '0.3.0+3',
      status: 'revoked',
      registeredAt: _registeredAt,
      lastSeenAt: _lastSeenAt,
      isCurrent: false,
    );
  }

  @override
  Future<void> changePassword(UserSession session, String password) async {
    changedPassword = password;
  }
}

DeviceIdentityProvider _identity() {
  return DeviceIdentityProvider(
    store: MemoryDeviceIdentityStore(),
    platformResolver: () => 'android',
    appVersionResolver: () async => '0.4.0+4',
    randomByteGenerator: (length) => List<int>.filled(length, 1),
  );
}

void main() {
  testWidgets('Client account explains personal access without permission jargon',
      (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: AccountSettingsPage(
          session: _clientSession,
          repository: _FakeAccountRepository(),
          deviceIdentityProvider: _identity(),
          onSignOut: () async {},
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Your access'), findsOneWidget);
    expect(
      find.text('Only your own linked loan and account records'),
      findsOneWidget,
    );
    expect(find.textContaining('server permissions'), findsNothing);
  });

  testWidgets('Client does not receive a self-service password control',
      (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: AccountSettingsPage(
          session: _clientSession,
          repository: _FakeAccountRepository(),
          deviceIdentityProvider: _identity(),
          onSignOut: () async {},
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('account-change-password')), findsNothing);
  });

  for (final role in <AppRole>[
    AppRole.collector,
    AppRole.employee,
    AppRole.management,
  ]) {
    testWidgets('${role.name} receives own-password control', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: AccountSettingsPage(
            session: _staffSession(role),
            repository: _FakeAccountRepository(),
            deviceIdentityProvider: _identity(),
            onSignOut: () async {},
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('account-change-password')), findsOneWidget);
      expect(find.text('Change my password'), findsOneWidget);
    });
  }

  testWidgets('matching password confirmation changes only the signed-in staff password',
      (tester) async {
    final repository = _FakeAccountRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: AccountSettingsPage(
          session: _session,
          repository: repository,
          deviceIdentityProvider: _identity(),
          onSignOut: () async {},
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('account-change-password')));
    await tester.pumpAndSettle();

    expect(find.text('Change my password'), findsWidgets);
    expect(find.byKey(const Key('account-password-new')), findsOneWidget);
    expect(find.byKey(const Key('account-password-confirm')), findsOneWidget);

    await tester.enterText(
      find.byKey(const Key('account-password-new')),
      'new-password-123',
    );
    await tester.enterText(
      find.byKey(const Key('account-password-confirm')),
      'different-password',
    );
    await tester.tap(find.byKey(const Key('account-password-submit')));
    await tester.pumpAndSettle();

    expect(repository.changedPassword, isNull);
    expect(find.text('Passwords do not match.'), findsOneWidget);

    await tester.enterText(
      find.byKey(const Key('account-password-confirm')),
      'new-password-123',
    );
    await tester.tap(find.byKey(const Key('account-password-submit')));
    await tester.pumpAndSettle();

    expect(repository.changedPassword, 'new-password-123');
    expect(find.text('Password changed.'), findsOneWidget);
  });

  testWidgets('shows profile, current session, and privacy-safe device state',
      (tester) async {
    final repository = _FakeAccountRepository();
    var signedOut = false;

    await tester.pumpWidget(
      MaterialApp(
        home: AccountSettingsPage(
          session: _session,
          repository: repository,
          deviceIdentityProvider: _identity(),
          onSignOut: () async {
            signedOut = true;
          },
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('account-settings-page')), findsOneWidget);
    expect(find.text('Collector One'), findsOneWidget);
    expect(find.text('collector@example.com'), findsOneWidget);
    expect(find.text('Current session'), findsOneWidget);
    expect(find.text('2 server permissions'), findsOneWidget);

    await tester.tap(find.byKey(const Key('account-sign-out')));
    await tester.pump();
    expect(signedOut, isTrue);

    await tester.drag(find.byType(ListView), const Offset(0, -500));
    await tester.pumpAndSettle();

    expect(find.text('This device'), findsOneWidget);
    expect(find.byKey(const Key('revoke-device-device-current')), findsNothing);
    expect(find.byKey(const Key('revoke-device-device-old')), findsOneWidget);

    await tester.drag(find.byType(ListView), const Offset(0, -350));
    await tester.pumpAndSettle();
    expect(
      find.textContaining('Device identifiers are never shown'),
      findsOneWidget,
    );
  });

  testWidgets('confirms and revokes only a non-current active device',
      (tester) async {
    final repository = _FakeAccountRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: AccountSettingsPage(
          session: _session,
          repository: repository,
          deviceIdentityProvider: _identity(),
          onSignOut: () async {},
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.drag(find.byType(ListView), const Offset(0, -650));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('revoke-device-device-old')));
    await tester.pumpAndSettle();
    expect(find.text('Revoke device?'), findsOneWidget);

    await tester.tap(find.widgetWithText(FilledButton, 'Revoke'));
    await tester.pumpAndSettle();

    expect(repository.revoked, isTrue);
    expect(find.text('Status: revoked'), findsOneWidget);
    expect(find.byKey(const Key('revoke-device-device-old')), findsNothing);
    expect(find.text('Device access revoked.'), findsOneWidget);
  });
}
