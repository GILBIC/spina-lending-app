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

class _FakeAccountRepository implements AccountRepository {
  var revoked = false;

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
