import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_administration.dart';
import 'package:gilbic_mobile/src/core/management/management_administration_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_staff_devices_page.dart';
import 'package:gilbic_mobile/src/features/management/management_staff_detail_page.dart';
import 'package:gilbic_mobile/src/features/management/management_staff_invite_page.dart';

void main() {
  testWidgets('shows initial loading then the authoritative staff directory', (
    tester,
  ) async {
    final response = Completer<ManagementStaffPage>();
    final repository = _FakeAdministrationRepository(
      onLoad: (_) => response.future,
    );

    await _pumpPage(tester, repository);
    expect(find.byKey(const Key('management-staff-loading')), findsOneWidget);

    response.complete(_page(<ManagementStaffAccount>[_ana]));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('management-staff-list')), findsOneWidget);
    expect(find.text('Ana West'), findsOneWidget);
    expect(find.text('@ana.west'), findsOneWidget);
    expect(find.text('Collector'), findsOneWidget);
    expect(find.text('Active'), findsOneWidget);
    expect(find.text('2 devices'), findsOneWidget);
    expect(find.text(_ana.id), findsNothing);
    expect(find.text('management-phone'), findsNothing);
    expect(repository.loadCalls.single.deviceId, 'management-phone');
  });

  testWidgets('shows a top-level error and retries', (tester) async {
    var attempts = 0;
    final repository = _FakeAdministrationRepository(
      onLoad: (_) async {
        attempts += 1;
        if (attempts == 1) {
          throw const SpinaApiException(
            'The server is unavailable.',
            code: 'network_unavailable',
          );
        }
        return _page(<ManagementStaffAccount>[_ana]);
      },
    );

    await _pumpPage(tester, repository);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('management-staff-error')), findsOneWidget);

    await tester.tap(find.byKey(const Key('management-staff-retry')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('management-staff-list')), findsOneWidget);
    expect(attempts, 2);
  });

  testWidgets('retries installation identity before loading the directory', (
    tester,
  ) async {
    final identityStore = _FlakyDeviceIdentityStore();
    final repository = _FakeAdministrationRepository(
      onLoad: (_) async => _page(<ManagementStaffAccount>[_ana]),
    );

    await _pumpPage(
      tester,
      repository,
      deviceIdentityProvider: DeviceIdentityProvider(
        store: identityStore,
        platformResolver: () => 'android',
        appVersionResolver: () async => '0.4.0+4',
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('management-staff-error')), findsOneWidget);
    expect(repository.loadCalls, isEmpty);

    await tester.tap(find.byKey(const Key('management-staff-retry')));
    await tester.pumpAndSettle();

    expect(identityStore.readAttempts, 2);
    expect(find.byKey(const Key('management-staff-list')), findsOneWidget);
    expect(repository.loadCalls.single.deviceId, 'management-phone');
  });

  testWidgets('permission denial offers refresh and back actions', (
    tester,
  ) async {
    var attempts = 0;
    final repository = _FakeAdministrationRepository(
      onLoad: (_) async {
        attempts += 1;
        if (attempts == 1) {
          throw const SpinaApiException('Permission denied.', statusCode: 403);
        }
        return _page(<ManagementStaffAccount>[_ana]);
      },
    );

    await _pumpPage(tester, repository);
    await tester.pumpAndSettle();
    expect(
      find.byKey(const Key('management-staff-permission-denied')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('management-staff-permission-refresh')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('management-staff-permission-back')),
      findsOneWidget,
    );

    await tester.tap(
      find.byKey(const Key('management-staff-permission-refresh')),
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('management-staff-list')), findsOneWidget);
  });

  testWidgets('distinguishes unfiltered and filtered empty states', (
    tester,
  ) async {
    final repository = _FakeAdministrationRepository(
      onLoad: (_) async => _page(const <ManagementStaffAccount>[]),
    );

    await _pumpPage(tester, repository);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('management-staff-empty')), findsOneWidget);
    expect(
      find.byKey(const Key('management-staff-empty-refresh')),
      findsOneWidget,
    );

    await tester.tap(find.byKey(const Key('management-staff-empty-refresh')));
    await tester.pumpAndSettle();
    expect(repository.loadCalls, hasLength(2));

    await tester.enterText(
      find.byKey(const Key('management-staff-search')),
      'missing',
    );
    await tester.pump(const Duration(milliseconds: 350));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const Key('management-staff-filtered-empty')),
      findsOneWidget,
    );
  });

  testWidgets('debounces server search and applies role and status filters', (
    tester,
  ) async {
    final repository = _FakeAdministrationRepository(
      onLoad: (_) async => _page(<ManagementStaffAccount>[_ana]),
    );

    await _pumpPage(tester, repository);
    await tester.pumpAndSettle();
    expect(repository.loadCalls, hasLength(1));

    await tester.enterText(
      find.byKey(const Key('management-staff-search')),
      '  ana  ',
    );
    await tester.pump(const Duration(milliseconds: 349));
    expect(repository.loadCalls, hasLength(1));
    await tester.pump(const Duration(milliseconds: 1));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('management-staff-role-filter')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Collector').last);
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('management-staff-status-filter')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Active').last);
    await tester.pumpAndSettle();

    final request = repository.loadCalls.last;
    expect(request.query, 'ana');
    expect(request.role, 'collector');
    expect(request.status, 'active');
    expect(request.offset, 0);
    expect(request.deviceId, 'management-phone');
  });

  testWidgets('pull refresh reloads from offset zero', (tester) async {
    final repository = _FakeAdministrationRepository(
      onLoad: (_) async => _page(<ManagementStaffAccount>[_ana]),
    );

    await _pumpPage(tester, repository);
    await tester.pumpAndSettle();
    await tester.drag(
      find.byKey(const Key('management-staff-list')),
      const Offset(0, 350),
    );
    await tester.pumpAndSettle();

    expect(repository.loadCalls, hasLength(2));
    expect(repository.loadCalls.last.offset, 0);
  });

  testWidgets('load more appends and de-duplicates staff UUIDs', (
    tester,
  ) async {
    final repository = _FakeAdministrationRepository(
      onLoad: (request) async => request.offset == 0
          ? ManagementStaffPage(
              items: <ManagementStaffAccount>[_ana],
              nextOffset: 1,
              hasMore: true,
            )
          : ManagementStaffPage(
              items: <ManagementStaffAccount>[_ana, _ben],
              nextOffset: 3,
              hasMore: false,
            ),
    );

    await _pumpPage(tester, repository);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('management-staff-load-more')));
    await tester.pumpAndSettle();

    expect(find.text('Ana West'), findsOneWidget);
    expect(find.text('Ben South'), findsOneWidget);
    expect(repository.loadCalls.last.offset, 1);
    expect(find.byKey(const Key('management-staff-load-more')), findsNothing);
  });

  testWidgets('ignores a late response from an older search', (tester) async {
    final oldResponse = Completer<ManagementStaffPage>();
    final newResponse = Completer<ManagementStaffPage>();
    final repository = _FakeAdministrationRepository(
      onLoad: (request) {
        if (request.query == 'old') {
          return oldResponse.future;
        }
        if (request.query == 'new') {
          return newResponse.future;
        }
        return Future<ManagementStaffPage>.value(
          _page(<ManagementStaffAccount>[_ana]),
        );
      },
    );

    await _pumpPage(tester, repository);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('management-staff-search')),
      'old',
    );
    await tester.pump(const Duration(milliseconds: 350));
    await tester.enterText(
      find.byKey(const Key('management-staff-search')),
      'new',
    );
    await tester.pump(const Duration(milliseconds: 350));

    newResponse.complete(_page(<ManagementStaffAccount>[_ben]));
    await tester.pump();
    oldResponse.complete(_page(<ManagementStaffAccount>[_cara]));
    await tester.pumpAndSettle();

    expect(find.text('Ben South'), findsOneWidget);
    expect(find.text('Cara North'), findsNothing);
  });

  testWidgets('invalidates an in-flight search as soon as the query changes', (
    tester,
  ) async {
    final oldResponse = Completer<ManagementStaffPage>();
    final newResponse = Completer<ManagementStaffPage>();
    final repository = _FakeAdministrationRepository(
      onLoad: (request) {
        if (request.query == 'old') {
          return oldResponse.future;
        }
        if (request.query == 'new') {
          return newResponse.future;
        }
        return Future<ManagementStaffPage>.value(
          _page(<ManagementStaffAccount>[_ana]),
        );
      },
    );

    await _pumpPage(tester, repository);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('management-staff-search')),
      'old',
    );
    await tester.pump(const Duration(milliseconds: 350));
    expect(repository.loadCalls.last.query, 'old');

    await tester.enterText(
      find.byKey(const Key('management-staff-search')),
      'new',
    );
    oldResponse.complete(_page(<ManagementStaffAccount>[_cara]));
    await tester.pump();

    expect(find.text('Cara North'), findsNothing);
    await tester.pump(const Duration(milliseconds: 350));
    newResponse.complete(_page(<ManagementStaffAccount>[_ben]));
    await tester.pumpAndSettle();
    expect(find.text('Ben South'), findsOneWidget);
  });

  testWidgets('fits a small phone with larger text without overflow', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(360, 640));
    addTearDown(() async => tester.binding.setSurfaceSize(null));
    final repository = _FakeAdministrationRepository(
      onLoad: (_) async => _page(<ManagementStaffAccount>[_ana, _ben]),
    );

    await _pumpPage(
      tester,
      repository,
      textScaler: const TextScaler.linear(1.3),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('management-staff-list')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('opens invite only with account management permission', (
    tester,
  ) async {
    final repository = _FakeAdministrationRepository(
      onLoad: (_) async => _page(<ManagementStaffAccount>[_ana]),
    );
    await _pumpPage(tester, repository);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('management-staff-invite')), findsOneWidget);
    await tester.tap(find.byKey(const Key('management-staff-invite')));
    await tester.pumpAndSettle();
    expect(find.byType(ManagementStaffInvitePage), findsOneWidget);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
    await _pumpPage(tester, repository, session: _deviceOnlySession);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('management-staff-invite')), findsNothing);
  });

  testWidgets(
    'failed production directory refresh keeps invite retry blocked',
    (tester) async {
      var loadAttempts = 0;
      final repository = _FakeAdministrationRepository(
        onLoad: (_) async {
          loadAttempts += 1;
          if (loadAttempts > 1) {
            throw const SpinaApiException(
              'The directory refresh failed.',
              code: 'network_unavailable',
            );
          }
          return _page(<ManagementStaffAccount>[_ana]);
        },
        onInvite: () async => throw const SpinaApiException(
          'Connection timed out.',
          code: 'network_unavailable',
        ),
      );
      await _pumpPage(tester, repository);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('management-staff-invite')));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('management-staff-full-name')),
        'Ana West',
      );
      await tester.enterText(
        find.byKey(const Key('management-staff-username')),
        'ana.west',
      );
      await tester.enterText(
        find.byKey(const Key('management-staff-email')),
        'ana@example.com',
      );
      await tester.tap(find.byKey(const Key('management-staff-invite-role')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Collector').last);
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('management-staff-invite-submit')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-staff-invitation')));
      await tester.pumpAndSettle();

      expect(loadAttempts, 2);
      expect(repository.inviteCalls, 1);
      expect(
        tester
            .widget<FilledButton>(
              find.byKey(const Key('management-staff-invite-submit')),
            )
            .onPressed,
        isNull,
      );
    },
  );

  testWidgets(
    'uncertain invitation reconciles exactly and preserves directory filters',
    (tester) async {
      final repository = _FakeAdministrationRepository(
        onLoad: (request) async => request.query == 'stale filter'
            ? _page(const <ManagementStaffAccount>[])
            : _page(<ManagementStaffAccount>[_ana]),
        onInvite: () async => throw const SpinaApiException(
          'Connection timed out.',
          code: 'network_unavailable',
        ),
      );
      await _pumpPage(tester, repository);
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('management-staff-search')),
        'stale filter',
      );
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('management-staff-invite')));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('management-staff-full-name')),
        'Ana West',
      );
      await tester.enterText(
        find.byKey(const Key('management-staff-username')),
        'ana.west',
      );
      await tester.enterText(
        find.byKey(const Key('management-staff-email')),
        'ana@example.com',
      );
      await tester.tap(find.byKey(const Key('management-staff-invite-role')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Collector').last);
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('management-staff-invite-submit')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-staff-invitation')));
      await tester.pumpAndSettle();

      expect(find.byType(ManagementStaffInvitePage), findsNothing);
      expect(find.byKey(const Key('management-staff-invite')), findsOneWidget);
      expect(
        find.byKey(const Key('management-staff-invite-reconcile-pending')),
        findsNothing,
      );
      expect(repository.inviteCalls, 1);
      expect(
        repository.loadCalls.map((call) => call.query),
        contains('ana.west'),
      );
      expect(repository.loadCalls.last.query, 'stale filter');
      expect(
        tester
            .widget<TextField>(find.byKey(const Key('management-staff-search')))
            .controller
            ?.text,
        'stale filter',
      );
      expect(
        find.byKey(const Key('management-staff-filtered-empty')),
        findsOneWidget,
      );
    },
  );

  testWidgets('uncertain invitation rejects a partial identifier match', (
    tester,
  ) async {
    final conflictingAccount = ManagementStaffAccount(
      id: _ana.id,
      username: _ana.username,
      email: 'different@example.com',
      fullName: _ana.fullName,
      status: _ana.status,
      roles: _ana.roles,
      deviceCount: _ana.deviceCount,
      createdAt: _ana.createdAt,
      updatedAt: _ana.updatedAt,
    );
    final repository = _FakeAdministrationRepository(
      onLoad: (request) async => request.query == 'ana.west'
          ? _page(<ManagementStaffAccount>[conflictingAccount])
          : _page(<ManagementStaffAccount>[_ana]),
      onInvite: () async => throw const SpinaApiException(
        'Connection timed out.',
        code: 'network_unavailable',
      ),
    );
    await _pumpPage(tester, repository);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('management-staff-invite')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('management-staff-full-name')),
      'Ana West',
    );
    await tester.enterText(
      find.byKey(const Key('management-staff-username')),
      'ana.west',
    );
    await tester.enterText(
      find.byKey(const Key('management-staff-email')),
      'ana@example.com',
    );
    await tester.tap(find.byKey(const Key('management-staff-invite-role')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Collector').last);
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('management-staff-invite-submit')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('confirm-staff-invitation')));
    await tester.pumpAndSettle();
    await tester.drag(find.byType(ListView).last, const Offset(0, -500));
    await tester.pumpAndSettle();

    expect(find.byType(ManagementStaffInvitePage), findsOneWidget);
    expect(
      find.byKey(const Key('management-staff-invite-reconcile')),
      findsOneWidget,
    );
    expect(find.textContaining('result is still unconfirmed'), findsOneWidget);
    expect(repository.inviteCalls, 1);

    await tester.pageBack();
    await tester.pumpAndSettle();

    expect(find.byType(ManagementStaffInvitePage), findsNothing);
    expect(find.byKey(const Key('management-staff-invite')), findsNothing);
    expect(
      find.byKey(const Key('management-staff-invite-reconcile-pending')),
      findsOneWidget,
    );

    await tester.tap(
      find.byKey(const Key('management-staff-invite-reconcile-pending')),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('management-staff-invite')), findsNothing);
    expect(
      find.byKey(const Key('management-staff-invite-reconcile-pending')),
      findsOneWidget,
    );
    expect(
      find.textContaining('new invitation remains blocked'),
      findsOneWidget,
    );
    expect(repository.inviteCalls, 1);
  });

  testWidgets('opens the exact staff detail page from a directory card', (
    tester,
  ) async {
    final repository = _FakeAdministrationRepository(
      onLoad: (_) async => _page(<ManagementStaffAccount>[_ana]),
    );
    await _pumpPage(tester, repository);
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('management-staff-open')));
    await tester.pumpAndSettle();
    expect(find.byType(ManagementStaffDetailPage), findsOneWidget);
  });
}

Future<void> _pumpPage(
  WidgetTester tester,
  ManagementAdministrationRepository repository, {
  TextScaler? textScaler,
  UserSession session = _session,
  DeviceIdentityProvider? deviceIdentityProvider,
}) async {
  final store = MemoryDeviceIdentityStore()..value = 'management-phone';
  await tester.pumpWidget(
    MaterialApp(
      builder: textScaler == null
          ? null
          : (context, child) => MediaQuery(
              data: MediaQuery.of(context).copyWith(textScaler: textScaler),
              child: child!,
            ),
      home: ManagementStaffDevicesPage(
        session: session,
        repository: repository,
        deviceIdentityProvider:
            deviceIdentityProvider ??
            DeviceIdentityProvider(
              store: store,
              platformResolver: () => 'android',
              appVersionResolver: () async => '0.4.0+4',
            ),
      ),
    ),
  );
  await tester.pump();
}

final class _FlakyDeviceIdentityStore implements DeviceIdentityStore {
  int readAttempts = 0;

  @override
  Future<String?> readInstallationId() async {
    readAttempts += 1;
    if (readAttempts == 1) {
      throw StateError('Secure storage temporarily unavailable.');
    }
    return 'management-phone';
  }

  @override
  Future<void> writeInstallationId(String value) async {}
}

ManagementStaffPage _page(List<ManagementStaffAccount> items) {
  return ManagementStaffPage(
    items: items,
    nextOffset: items.length,
    hasMore: false,
  );
}

const _session = UserSession(
  userId: '99999999-9999-4999-8999-999999999999',
  username: 'manager.one',
  displayName: 'Manager One',
  role: AppRole.management,
  rawRole: 'management',
  accessToken: 'access-token',
  permissions: <String>['account.manage', 'device.manage'],
);

const _deviceOnlySession = UserSession(
  userId: '99999999-9999-4999-8999-999999999999',
  username: 'manager.one',
  displayName: 'Manager One',
  role: AppRole.management,
  rawRole: 'management',
  accessToken: 'access-token',
  permissions: <String>['device.manage'],
);

final _ana = ManagementStaffAccount(
  id: '11111111-1111-4111-8111-111111111111',
  username: 'ana.west',
  email: 'ana@example.com',
  fullName: 'Ana West',
  status: 'active',
  roles: <String>['collector'],
  deviceCount: 2,
  createdAt: _createdAt,
  updatedAt: _updatedAt,
);

final _ben = ManagementStaffAccount(
  id: '22222222-2222-4222-8222-222222222222',
  username: 'ben.south',
  email: 'ben@example.com',
  fullName: 'Ben South',
  status: 'inactive',
  roles: <String>['employee'],
  deviceCount: 1,
  createdAt: _createdAt,
  updatedAt: _updatedAt,
);

final _cara = ManagementStaffAccount(
  id: '33333333-3333-4333-8333-333333333333',
  username: 'cara.north',
  email: null,
  fullName: 'Cara North',
  status: 'pending',
  roles: <String>['management'],
  deviceCount: 0,
  createdAt: _createdAt,
  updatedAt: _updatedAt,
);

final _createdAt = DateTime.utc(2026, 8, 28, 8);
final _updatedAt = DateTime.utc(2026, 8, 28, 9);

final class _LoadCall {
  const _LoadCall({
    required this.deviceId,
    required this.query,
    required this.role,
    required this.status,
    required this.limit,
    required this.offset,
  });

  final String deviceId;
  final String? query;
  final String? role;
  final String? status;
  final int limit;
  final int offset;
}

final class _FakeAdministrationRepository
    implements ManagementAdministrationRepository {
  _FakeAdministrationRepository({required this.onLoad, this.onInvite});

  final Future<ManagementStaffPage> Function(_LoadCall request) onLoad;
  final Future<ManagementStaffAccount> Function()? onInvite;
  final List<_LoadCall> loadCalls = <_LoadCall>[];
  int inviteCalls = 0;

  @override
  Future<ManagementStaffPage> loadStaff(
    UserSession session, {
    required String deviceId,
    String? query,
    String? role,
    String? status,
    int limit = 50,
    int offset = 0,
  }) {
    final request = _LoadCall(
      deviceId: deviceId,
      query: query,
      role: role,
      status: status,
      limit: limit,
      offset: offset,
    );
    loadCalls.add(request);
    return onLoad(request);
  }

  @override
  Future<ManagementStaffAccount> inviteStaff(
    UserSession session, {
    required String deviceId,
    required String username,
    required String email,
    required String fullName,
    required String role,
  }) {
    inviteCalls += 1;
    return onInvite?.call() ?? Future<ManagementStaffAccount>.value(_ana);
  }

  @override
  Future<List<ManagementDevice>> loadDevices(
    UserSession session, {
    required String deviceId,
    required String userId,
  }) async => const <ManagementDevice>[];

  @override
  Future<ManagementStaffAccount> setAccountStatus(
    UserSession session, {
    required String deviceId,
    required String userId,
    required String status,
  }) => throw UnimplementedError();

  @override
  Future<ManagementDevice> setDeviceStatus(
    UserSession session, {
    required String deviceId,
    required String userId,
    required String managedDeviceId,
    required String status,
  }) => throw UnimplementedError();

  @override
  Future<ManagementStaffAccount> setRole(
    UserSession session, {
    required String deviceId,
    required String userId,
    required String role,
  }) => throw UnimplementedError();
}
