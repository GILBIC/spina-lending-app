import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_administration.dart';
import 'package:gilbic_mobile/src/core/management/management_administration_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_staff_detail_page.dart';

void main() {
  const cases = <(List<String>, bool, bool)>[
    (<String>['account.manage'], true, false),
    (<String>['device.manage'], false, true),
    (<String>['account.manage', 'device.manage'], true, true),
  ];
  for (final testCase in cases) {
    testWidgets('partitions detail controls for ${testCase.$1.join(' and ')}', (
      tester,
    ) async {
      final repository = _DetailRepository();
      await _pumpDetail(
        tester,
        repository: repository,
        session: _session(testCase.$1),
      );
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('management-staff-role-control')),
        testCase.$2 ? findsOneWidget : findsNothing,
      );
      expect(
        find.byKey(const Key('management-staff-status-control')),
        testCase.$2 ? findsOneWidget : findsNothing,
      );
      expect(
        find.byKey(const Key('management-staff-devices-section')),
        testCase.$3 ? findsOneWidget : findsNothing,
      );
      expect(
        find.byKey(
          const Key('management-staff-account-permission-explanation'),
        ),
        testCase.$2 || !testCase.$3 ? findsNothing : findsOneWidget,
      );
      expect(
        find.byKey(const Key('management-staff-device-permission-explanation')),
        testCase.$3 || !testCase.$2 ? findsNothing : findsOneWidget,
      );
      expect(repository.loadDeviceCalls, testCase.$3 ? 1 : 0);
    });
  }

  testWidgets('shows permission state with neither administration permission', (
    tester,
  ) async {
    await _pumpDetail(
      tester,
      repository: _DetailRepository(),
      session: _session(const <String>[]),
    );
    await tester.pumpAndSettle();

    expect(
      find.byKey(const Key('management-staff-detail-permission-denied')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('management-staff-role-control')),
      findsNothing,
    );
    expect(
      find.byKey(const Key('management-staff-devices-section')),
      findsNothing,
    );
  });

  testWidgets('never renders server identity fields or device hashes', (
    tester,
  ) async {
    await _pumpDetail(
      tester,
      repository: _DetailRepository(devices: <ManagementDevice>[_device]),
      session: _session(const <String>['account.manage', 'device.manage']),
    );
    await tester.pumpAndSettle();

    expect(find.text(_account.id), findsNothing);
    expect(find.text(_device.id), findsNothing);
    expect(find.text('auth_user_id'), findsNothing);
    expect(find.text('user_id'), findsNothing);
    expect(find.text('device-hash-secret'), findsNothing);
    expect(find.text('Ana West'), findsWidgets);
    expect(find.text('Android'), findsOneWidget);
  });

  testWidgets('renders authoritative account and phone metadata', (
    tester,
  ) async {
    await _pumpDetail(
      tester,
      repository: _DetailRepository(devices: <ManagementDevice>[_device]),
      session: _session(const <String>['account.manage', 'device.manage']),
    );
    await tester.pumpAndSettle();

    expect(find.text('Registered devices: 1'), findsOneWidget);
    expect(find.text('Created: 2026-08-28 08:00 UTC'), findsOneWidget);
    expect(find.text('Updated: 2026-08-28 09:00 UTC'), findsOneWidget);
    expect(find.text('App version: 0.4.0+4'), findsOneWidget);
    expect(find.text('Registered: 2026-08-28 08:00 UTC'), findsOneWidget);
    expect(find.text('Last seen: 2026-08-28 09:00 UTC'), findsOneWidget);
  });

  testWidgets('disables destructive changes to the acting account', (
    tester,
  ) async {
    final ownSession = UserSession(
      userId: _account.id,
      username: 'ana.west',
      displayName: 'Ana West',
      role: AppRole.management,
      rawRole: 'management',
      accessToken: 'access-token',
      permissions: const <String>['account.manage', 'device.manage'],
    );
    await _pumpDetail(
      tester,
      repository: _DetailRepository(devices: <ManagementDevice>[_device]),
      session: ownSession,
    );
    await tester.pumpAndSettle();

    await _selectDropdown(
      tester,
      const Key('management-staff-role-picker'),
      'Employee',
    );
    expect(
      tester
          .widget<FilledButton>(
            find.byKey(const Key('management-staff-role-save')),
          )
          .onPressed,
      isNull,
    );
    await _selectDropdown(
      tester,
      const Key('management-staff-status-picker'),
      'Inactive',
    );
    expect(
      tester
          .widget<FilledButton>(
            find.byKey(const Key('management-staff-status-save')),
          )
          .onPressed,
      isNull,
    );
    expect(
      tester
          .widget<OutlinedButton>(
            find.byKey(const Key('management-device-action')),
          )
          .onPressed,
      isNull,
    );
  });

  for (final status in <String>['pending', 'active', 'revoked']) {
    testWidgets('disables $status phone mutation for the acting account', (
      tester,
    ) async {
      final ownSession = UserSession(
        userId: _account.id,
        username: 'ana.west',
        displayName: 'Ana West',
        role: AppRole.management,
        rawRole: 'management',
        accessToken: 'access-token',
        permissions: const <String>['device.manage'],
      );
      await _pumpDetail(
        tester,
        repository: _DetailRepository(
          devices: <ManagementDevice>[_deviceWith(status: status)],
        ),
        session: ownSession,
      );
      await tester.pumpAndSettle();

      expect(
        tester
            .widget<ButtonStyleButton>(
              find.byKey(const Key('management-device-action')),
            )
            .onPressed,
        isNull,
      );
    });
  }

  testWidgets('shows success only after mutation and authoritative reloads', (
    tester,
  ) async {
    final mutation = Completer<ManagementStaffAccount>();
    final reload = Completer<ManagementStaffAccount>();
    final repository = _DetailRepository(onSetRole: (_, __) => mutation.future);
    await _pumpDetail(
      tester,
      repository: repository,
      session: _session(const <String>['account.manage', 'device.manage']),
      reloadAccount: () => reload.future,
    );
    await tester.pumpAndSettle();

    await _selectDropdown(
      tester,
      const Key('management-staff-role-picker'),
      'Employee',
    );
    await tester.tap(find.byKey(const Key('management-staff-role-save')));
    await tester.pumpAndSettle();
    expect(find.text('Ana West'), findsWidgets);
    expect(find.text('Current: Collector'), findsOneWidget);
    expect(find.text('Requested: Employee'), findsOneWidget);
    expect(find.textContaining('future access'), findsOneWidget);

    await tester.tap(find.byKey(const Key('management-action-confirm')));
    await tester.pump();
    expect(find.byKey(const Key('management-staff-success')), findsNothing);
    mutation.complete(_accountWith(role: 'employee'));
    await tester.pump();
    expect(find.byKey(const Key('management-staff-success')), findsNothing);
    reload.complete(_accountWith(role: 'employee'));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('management-staff-success')), findsOneWidget);
    expect(repository.loadDeviceCalls, 2);
  });

  testWidgets('network failure retains state and never retries automatically', (
    tester,
  ) async {
    final repository = _DetailRepository(
      onSetRole: (_, __) async => throw const SpinaApiException(
        'Connection lost.',
        code: 'network_unavailable',
      ),
    );
    await _pumpDetail(
      tester,
      repository: repository,
      session: _session(const <String>['account.manage']),
    );
    await tester.pumpAndSettle();

    await _requestEmployeeRole(tester);
    await tester.pumpAndSettle();

    expect(
      find.byKey(const Key('management-staff-mutation-error')),
      findsOneWidget,
    );
    expect(find.byKey(const Key('management-staff-refresh')), findsOneWidget);
    expect(find.text('Collector'), findsWidgets);
    expect(repository.setRoleCalls, 1);
  });

  testWidgets(
    'uncertain mutation remains locked until authoritative reload succeeds',
    (tester) async {
      final reload = Completer<ManagementStaffAccount>();
      var reloads = 0;
      final repository = _DetailRepository(
        onSetRole: (_, __) async => throw const SpinaApiException(
          'Connection lost.',
          code: 'network_unavailable',
        ),
      );
      await _pumpDetail(
        tester,
        repository: repository,
        session: _session(const <String>['account.manage']),
        reloadAccount: () {
          reloads += 1;
          return reload.future;
        },
      );
      await tester.pumpAndSettle();

      await _requestEmployeeRole(tester);
      await tester.pump();
      expect(reloads, 1);
      expect(
        tester
            .widget<FilledButton>(
              find.byKey(const Key('management-staff-role-save')),
            )
            .onPressed,
        isNull,
      );

      reload.complete(_account);
      await tester.pumpAndSettle();
      await _selectDropdown(
        tester,
        const Key('management-staff-role-picker'),
        'Employee',
      );
      expect(
        tester
            .widget<FilledButton>(
              find.byKey(const Key('management-staff-role-save')),
            )
            .onPressed,
        isNotNull,
      );
      expect(repository.setRoleCalls, 1);
    },
  );

  testWidgets('destructive account and phone actions use error styling', (
    tester,
  ) async {
    await _pumpDetail(
      tester,
      repository: _DetailRepository(devices: <ManagementDevice>[_device]),
      session: _session(const <String>['account.manage', 'device.manage']),
    );
    await tester.pumpAndSettle();
    await _selectDropdown(
      tester,
      const Key('management-staff-status-picker'),
      'Locked',
    );
    final colors = Theme.of(
      tester.element(find.byType(ManagementStaffDetailPage)),
    ).colorScheme;
    final statusButton = tester.widget<FilledButton>(
      find.byKey(const Key('management-staff-status-save')),
    );
    final deviceButton = tester.widget<ButtonStyleButton>(
      find.byKey(const Key('management-device-action')),
    );

    expect(
      statusButton.style?.backgroundColor?.resolve(<WidgetState>{}),
      colors.error,
    );
    expect(
      deviceButton.style?.foregroundColor?.resolve(<WidgetState>{}),
      colors.error,
    );
  });

  testWidgets('403 mutation denial offers refresh and back', (tester) async {
    final repository = _DetailRepository(
      onSetRole: (_, __) async =>
          throw const SpinaApiException('Denied.', statusCode: 403),
    );
    await _pumpDetail(
      tester,
      repository: repository,
      session: _session(const <String>['account.manage']),
    );
    await tester.pumpAndSettle();
    await _requestEmployeeRole(tester);
    await tester.pumpAndSettle();

    expect(
      find.byKey(const Key('management-staff-detail-permission-denied')),
      findsOneWidget,
    );
    expect(find.byKey(const Key('management-staff-refresh')), findsOneWidget);
    expect(find.byKey(const Key('management-staff-back')), findsOneWidget);
  });

  testWidgets('404 mutation refreshes the directory and reports removal', (
    tester,
  ) async {
    var directoryRefreshes = 0;
    final repository = _DetailRepository(
      onSetRole: (_, __) async =>
          throw const SpinaApiException('Missing.', statusCode: 404),
    );
    await _pumpDetail(
      tester,
      repository: repository,
      session: _session(const <String>['account.manage']),
      onDirectoryRefresh: () async => directoryRefreshes += 1,
    );
    await tester.pumpAndSettle();
    await _requestEmployeeRole(tester);
    await tester.pumpAndSettle();

    expect(directoryRefreshes, 1);
    expect(
      find.textContaining('record is no longer available'),
      findsOneWidget,
    );
  });

  testWidgets('409 conflict preserves explanation and reloads current state', (
    tester,
  ) async {
    var reloads = 0;
    final repository = _DetailRepository(
      onSetRole: (_, __) async => throw const SpinaApiException(
        'Another manager changed this account.',
        statusCode: 409,
      ),
    );
    await _pumpDetail(
      tester,
      repository: repository,
      session: _session(const <String>['account.manage']),
      reloadAccount: () async {
        reloads += 1;
        return _account;
      },
    );
    await tester.pumpAndSettle();
    await _requestEmployeeRole(tester);
    await tester.pumpAndSettle();

    expect(reloads, 1);
    expect(find.text('Another manager changed this account.'), findsOneWidget);
    expect(repository.setRoleCalls, 1);
  });

  testWidgets('Collector device approval confirmation explains revocation', (
    tester,
  ) async {
    final repository = _DetailRepository(
      devices: <ManagementDevice>[_pendingDevice],
    );
    await _pumpDetail(
      tester,
      repository: repository,
      session: _session(const <String>['device.manage']),
    );
    await tester.pumpAndSettle();
    final deviceAction = find.byKey(const Key('management-device-action'));
    await tester.ensureVisible(deviceAction);
    await tester.tap(deviceAction);
    await tester.pumpAndSettle();

    expect(find.text('Ana West'), findsWidgets);
    expect(find.text('Current: Pending'), findsOneWidget);
    expect(find.text('Requested: Active'), findsOneWidget);
    expect(
      find.text(
        'Approving this phone revokes any other active Collector phone.',
      ),
      findsOneWidget,
    );
  });
}

Future<void> _requestEmployeeRole(WidgetTester tester) async {
  await _selectDropdown(
    tester,
    const Key('management-staff-role-picker'),
    'Employee',
  );
  await tester.tap(find.byKey(const Key('management-staff-role-save')));
  await tester.pumpAndSettle();
  await tester.tap(find.byKey(const Key('management-action-confirm')));
}

Future<void> _selectDropdown(WidgetTester tester, Key key, String label) async {
  final dropdown = find.byKey(key);
  await tester.ensureVisible(dropdown);
  await tester.tap(dropdown);
  await tester.pumpAndSettle();
  await tester.tap(find.text(label).last);
  await tester.pumpAndSettle();
}

Future<void> _pumpDetail(
  WidgetTester tester, {
  required _DetailRepository repository,
  required UserSession session,
  Future<ManagementStaffAccount> Function()? reloadAccount,
  Future<void> Function()? onDirectoryRefresh,
}) async {
  final store = MemoryDeviceIdentityStore()..value = 'management-phone';
  await tester.pumpWidget(
    MaterialApp(
      home: ManagementStaffDetailPage(
        session: session,
        account: _account,
        repository: repository,
        deviceIdentityProvider: DeviceIdentityProvider(
          store: store,
          platformResolver: () => 'android',
          appVersionResolver: () async => '0.4.0+4',
        ),
        reloadAccount: reloadAccount ?? () async => _account,
        onDirectoryRefresh: onDirectoryRefresh ?? () async {},
      ),
    ),
  );
  await tester.pump();
}

UserSession _session(List<String> permissions) => UserSession(
  userId: '99999999-9999-4999-8999-999999999999',
  username: 'manager.one',
  displayName: 'Manager One',
  role: AppRole.management,
  rawRole: 'management',
  accessToken: 'access-token',
  permissions: permissions,
);

ManagementStaffAccount _accountWith({required String role}) =>
    ManagementStaffAccount(
      id: _account.id,
      username: _account.username,
      email: _account.email,
      fullName: _account.fullName,
      status: _account.status,
      roles: <String>[role],
      deviceCount: _account.deviceCount,
      createdAt: _account.createdAt,
      updatedAt: _account.updatedAt,
    );

final _account = ManagementStaffAccount(
  id: '11111111-1111-4111-8111-111111111111',
  username: 'ana.west',
  email: 'ana@example.com',
  fullName: 'Ana West',
  status: 'active',
  roles: const <String>['collector'],
  deviceCount: 1,
  createdAt: DateTime.utc(2026, 8, 28, 8),
  updatedAt: DateTime.utc(2026, 8, 28, 9),
);

final _device = ManagementDevice(
  id: '22222222-2222-4222-8222-222222222222',
  platform: 'android',
  appVersion: '0.4.0+4',
  status: 'active',
  registeredAt: DateTime.utc(2026, 8, 28, 8),
  lastSeenAt: DateTime.utc(2026, 8, 28, 9),
);

final _pendingDevice = ManagementDevice(
  id: '33333333-3333-4333-8333-333333333333',
  platform: 'android',
  appVersion: '0.4.0+4',
  status: 'pending',
  registeredAt: DateTime.utc(2026, 8, 28, 8),
  lastSeenAt: null,
);

ManagementDevice _deviceWith({required String status}) => ManagementDevice(
  id: _device.id,
  platform: _device.platform,
  appVersion: _device.appVersion,
  status: status,
  registeredAt: _device.registeredAt,
  lastSeenAt: _device.lastSeenAt,
);

final class _DetailRepository implements ManagementAdministrationRepository {
  _DetailRepository({
    this.devices = const <ManagementDevice>[],
    this.onSetRole,
  });

  List<ManagementDevice> devices;
  final Future<ManagementStaffAccount> Function(String role, int call)?
  onSetRole;
  int loadDeviceCalls = 0;
  int setRoleCalls = 0;

  @override
  Future<List<ManagementDevice>> loadDevices(
    UserSession session, {
    required String deviceId,
    required String userId,
  }) async {
    loadDeviceCalls += 1;
    return devices;
  }

  @override
  Future<ManagementStaffAccount> setRole(
    UserSession session, {
    required String deviceId,
    required String userId,
    required String role,
  }) {
    setRoleCalls += 1;
    final callback = onSetRole;
    return callback == null
        ? Future<ManagementStaffAccount>.value(_accountWith(role: role))
        : callback(role, setRoleCalls);
  }

  @override
  Future<ManagementStaffAccount> setAccountStatus(
    UserSession session, {
    required String deviceId,
    required String userId,
    required String status,
  }) async => _account;

  @override
  Future<ManagementDevice> setDeviceStatus(
    UserSession session, {
    required String deviceId,
    required String userId,
    required String managedDeviceId,
    required String status,
  }) async => ManagementDevice(
    id: _device.id,
    platform: _device.platform,
    appVersion: _device.appVersion,
    status: status,
    registeredAt: _device.registeredAt,
    lastSeenAt: _device.lastSeenAt,
  );

  @override
  Future<ManagementStaffPage> loadStaff(
    UserSession session, {
    required String deviceId,
    String? query,
    String? role,
    String? status,
    int limit = 50,
    int offset = 0,
  }) => throw UnimplementedError();

  @override
  Future<ManagementStaffAccount> inviteStaff(
    UserSession session, {
    required String deviceId,
    required String username,
    required String email,
    required String fullName,
    required String role,
  }) => throw UnimplementedError();
}
