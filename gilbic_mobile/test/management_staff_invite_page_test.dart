import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_administration.dart';
import 'package:gilbic_mobile/src/core/management/management_administration_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_staff_invite_page.dart';

void main() {
  testWidgets(
    'requires staff fields and never offers password or Client role',
    (tester) async {
      final repository = _InviteRepository();
      await _pumpInvite(tester, repository: repository);
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('management-staff-full-name')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('management-staff-username')),
        findsOneWidget,
      );
      expect(find.byKey(const Key('management-staff-email')), findsOneWidget);
      expect(
        find.byKey(const Key('management-staff-invite-role')),
        findsOneWidget,
      );
      expect(find.textContaining('Password'), findsNothing);

      await tester.tap(find.byKey(const Key('management-staff-invite-role')));
      await tester.pumpAndSettle();
      expect(find.text('Collector'), findsOneWidget);
      expect(find.text('Employee'), findsOneWidget);
      expect(find.text('Management'), findsOneWidget);
      expect(find.text('Client'), findsNothing);
      await tester.tapAt(const Offset(5, 5));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('management-staff-invite-submit')));
      await tester.pumpAndSettle();
      expect(
        find.text('Complete all staff invitation fields.'),
        findsOneWidget,
      );
      expect(repository.inviteCalls, 0);
    },
  );

  testWidgets(
    'submits trimmed fields once and pops only after parsed success',
    (tester) async {
      final result = Completer<ManagementStaffAccount>();
      final repository = _InviteRepository(onInvite: () => result.future);
      await _pumpInvite(tester, repository: repository);
      await tester.pumpAndSettle();
      await _fillForm(tester);

      await tester.tap(find.byKey(const Key('management-staff-invite-submit')));
      await tester.pump();
      expect(repository.inviteCalls, 1);
      expect(
        tester
            .widget<FilledButton>(
              find.byKey(const Key('management-staff-invite-submit')),
            )
            .onPressed,
        isNull,
      );
      expect(find.text('Invitation complete'), findsNothing);

      result.complete(_account);
      await tester.pumpAndSettle();
      expect(find.text('Created Ana West'), findsOneWidget);
      expect(repository.lastUsername, 'ana.west');
      expect(repository.lastEmail, 'ana@example.com');
      expect(repository.lastFullName, 'Ana West');
      expect(repository.lastRole, 'collector');
    },
  );

  testWidgets('blocks route exit while the invitation POST is in flight', (
    tester,
  ) async {
    final result = Completer<ManagementStaffAccount>();
    final repository = _InviteRepository(onInvite: () => result.future);
    await _pumpInvite(tester, repository: repository);
    await tester.pumpAndSettle();
    await _fillForm(tester);

    await tester.tap(find.byKey(const Key('management-staff-invite-submit')));
    await tester.pump();
    expect(repository.inviteCalls, 1);

    await tester.pageBack();
    await tester.pump();

    expect(find.byType(ManagementStaffInvitePage), findsOneWidget);
    expect(find.byKey(const Key('open-invite')), findsNothing);
    expect(repository.inviteCalls, 1);

    result.complete(_account);
    await tester.pumpAndSettle();
    expect(find.byType(ManagementStaffInvitePage), findsNothing);
    expect(find.text('Created Ana West'), findsOneWidget);
    expect(repository.inviteCalls, 1);
  });

  testWidgets('uncertain result refreshes directory without automatic repost', (
    tester,
  ) async {
    final refresh = Completer<ManagementStaffAccount?>();
    var refreshCalls = 0;
    final repository = _InviteRepository(
      onInvite: () async => throw const SpinaApiException(
        'Connection timed out.',
        code: 'network_unavailable',
      ),
    );
    await _pumpInvite(
      tester,
      repository: repository,
      onUncertainResult: ({required String username, required String email}) {
        refreshCalls += 1;
        return refresh.future;
      },
    );
    await tester.pumpAndSettle();
    await _fillForm(tester);

    await tester.tap(find.byKey(const Key('management-staff-invite-submit')));
    await tester.pump();
    expect(repository.inviteCalls, 1);
    expect(refreshCalls, 1);
    expect(
      find.text('Refresh the staff list before trying this invitation again.'),
      findsOneWidget,
    );
    expect(
      tester
          .widget<FilledButton>(
            find.byKey(const Key('management-staff-invite-submit')),
          )
          .onPressed,
      isNull,
    );

    refresh.complete(_account);
    await tester.pumpAndSettle();
    expect(repository.inviteCalls, 1);
    expect(
      find.byKey(const Key('management-staff-invite-submit')),
      findsNothing,
    );
    expect(find.byKey(const Key('open-invite')), findsOneWidget);
  });

  testWidgets(
    'failed uncertain-result refresh keeps invitation retry blocked',
    (tester) async {
      final repository = _InviteRepository(
        onInvite: () async => throw const SpinaApiException(
          'Connection timed out.',
          code: 'network_unavailable',
        ),
      );
      await _pumpInvite(
        tester,
        repository: repository,
        onUncertainResult:
            ({required String username, required String email}) async =>
                throw StateError('refresh failed'),
      );
      await tester.pumpAndSettle();
      await _fillForm(tester);

      await tester.tap(find.byKey(const Key('management-staff-invite-submit')));
      await tester.pumpAndSettle();

      expect(repository.inviteCalls, 1);
      expect(
        tester
            .widget<FilledButton>(
              find.byKey(const Key('management-staff-invite-submit')),
            )
            .onPressed,
        isNull,
      );
      expect(
        find.text(
          'Refresh the staff list before trying this invitation again.',
        ),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'uncertain invitation stays blocked until exact account appears',
    (tester) async {
      var reconciliationCalls = 0;
      final repository = _InviteRepository(
        onInvite: () async => throw const SpinaApiException(
          'Connection timed out.',
          code: 'network_unavailable',
        ),
      );
      await _pumpInvite(
        tester,
        repository: repository,
        onUncertainResult:
            ({required String username, required String email}) async {
              reconciliationCalls += 1;
              expect(username, 'ana.west');
              expect(email, 'ana@example.com');
              return reconciliationCalls == 1 ? null : _account;
            },
      );
      await tester.pumpAndSettle();
      await _fillForm(tester);

      await tester.tap(find.byKey(const Key('management-staff-invite-submit')));
      await tester.pumpAndSettle();

      expect(reconciliationCalls, 1);
      expect(
        find.byKey(const Key('management-staff-invite-reconcile')),
        findsOneWidget,
      );
      expect(
        tester
            .widget<FilledButton>(
              find.byKey(const Key('management-staff-invite-submit')),
            )
            .onPressed,
        isNull,
      );

      await tester.tap(
        find.byKey(const Key('management-staff-invite-reconcile')),
      );
      await tester.pumpAndSettle();

      expect(reconciliationCalls, 2);
      expect(find.byKey(const Key('open-invite')), findsOneWidget);
      expect(find.byType(ManagementStaffInvitePage), findsNothing);
    },
  );

  testWidgets('malformed invitation success requires authoritative refresh', (
    tester,
  ) async {
    final refresh = Completer<ManagementStaffAccount?>();
    var refreshCalls = 0;
    final repository = _InviteRepository(
      onInvite: () async => throw const SpinaApiException(
        'The server returned an invalid response.',
        code: 'invalid_server_response',
      ),
    );
    await _pumpInvite(
      tester,
      repository: repository,
      onUncertainResult: ({required String username, required String email}) {
        refreshCalls += 1;
        return refresh.future;
      },
    );
    await tester.pumpAndSettle();
    await _fillForm(tester);

    await tester.tap(find.byKey(const Key('management-staff-invite-submit')));
    await tester.pump();

    expect(refreshCalls, 1);
    expect(repository.inviteCalls, 1);
    expect(
      find.text('Refresh the staff list before trying this invitation again.'),
      findsOneWidget,
    );
    expect(
      tester
          .widget<FilledButton>(
            find.byKey(const Key('management-staff-invite-submit')),
          )
          .onPressed,
      isNull,
    );
    refresh.complete(_account);
    await tester.pumpAndSettle();
    expect(
      find.byKey(const Key('management-staff-invite-submit')),
      findsNothing,
    );
    expect(find.byKey(const Key('open-invite')), findsOneWidget);
  });

  testWidgets(
    'permission loss replaces invitation form with refresh and back',
    (tester) async {
      final repository = _InviteRepository(
        onInvite: () async => throw const SpinaApiException(
          'Permission denied.',
          statusCode: 403,
        ),
      );
      await _pumpInvite(tester, repository: repository);
      await tester.pumpAndSettle();
      await _fillForm(tester);

      await tester.tap(find.byKey(const Key('management-staff-invite-submit')));
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('management-staff-invite-permission-denied')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('management-staff-invite-permission-refresh')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('management-staff-invite-permission-back')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('management-staff-invite-submit')),
        findsNothing,
      );
      expect(repository.inviteCalls, 1);
    },
  );
}

Future<void> _fillForm(WidgetTester tester) async {
  await tester.enterText(
    find.byKey(const Key('management-staff-full-name')),
    ' Ana West ',
  );
  await tester.enterText(
    find.byKey(const Key('management-staff-username')),
    ' ana.west ',
  );
  await tester.enterText(
    find.byKey(const Key('management-staff-email')),
    ' ANA@EXAMPLE.COM ',
  );
  await tester.tap(find.byKey(const Key('management-staff-invite-role')));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Collector').last);
  await tester.pumpAndSettle();
}

Future<void> _pumpInvite(
  WidgetTester tester, {
  required _InviteRepository repository,
  InvitationReconciler? onUncertainResult,
  Future<void> Function()? onDirectoryRefresh,
}) async {
  final store = MemoryDeviceIdentityStore()..value = 'management-phone';
  await tester.pumpWidget(
    MaterialApp(
      home: _InviteHost(
        repository: repository,
        deviceIdentityProvider: DeviceIdentityProvider(
          store: store,
          platformResolver: () => 'android',
          appVersionResolver: () async => '0.4.0+4',
        ),
        onUncertainResult:
            onUncertainResult ??
            ({required String username, required String email}) async => null,
        onDirectoryRefresh: onDirectoryRefresh ?? () async {},
      ),
    ),
  );
  await tester.tap(find.byKey(const Key('open-invite')));
  await tester.pumpAndSettle();
}

class _InviteHost extends StatefulWidget {
  const _InviteHost({
    required this.repository,
    required this.deviceIdentityProvider,
    required this.onUncertainResult,
    required this.onDirectoryRefresh,
  });

  final ManagementAdministrationRepository repository;
  final DeviceIdentityProvider deviceIdentityProvider;
  final InvitationReconciler onUncertainResult;
  final Future<void> Function() onDirectoryRefresh;

  @override
  State<_InviteHost> createState() => _InviteHostState();
}

class _InviteHostState extends State<_InviteHost> {
  String? _result;

  Future<void> _open() async {
    final account = await Navigator.of(context).push<ManagementStaffAccount>(
      MaterialPageRoute<ManagementStaffAccount>(
        builder: (_) => ManagementStaffInvitePage(
          session: _session,
          repository: widget.repository,
          deviceIdentityProvider: widget.deviceIdentityProvider,
          onUncertainResult: widget.onUncertainResult,
          onDirectoryRefresh: widget.onDirectoryRefresh,
        ),
      ),
    );
    if (mounted && account != null) {
      setState(() => _result = 'Created ${account.fullName}');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          FilledButton(
            key: const Key('open-invite'),
            onPressed: _open,
            child: const Text('Open'),
          ),
          if (_result != null) Text(_result!),
        ],
      ),
    );
  }
}

const _session = UserSession(
  userId: '99999999-9999-4999-8999-999999999999',
  username: 'manager.one',
  displayName: 'Manager One',
  role: AppRole.management,
  rawRole: 'management',
  accessToken: 'access-token',
  permissions: <String>['account.manage'],
);

final _account = ManagementStaffAccount(
  id: '11111111-1111-4111-8111-111111111111',
  username: 'ana.west',
  email: 'ana@example.com',
  fullName: 'Ana West',
  status: 'pending',
  roles: const <String>['collector'],
  deviceCount: 0,
  createdAt: DateTime.utc(2026, 8, 29, 8),
  updatedAt: DateTime.utc(2026, 8, 29, 8),
);

final class _InviteRepository implements ManagementAdministrationRepository {
  _InviteRepository({this.onInvite});

  final Future<ManagementStaffAccount> Function()? onInvite;
  int inviteCalls = 0;
  String? lastUsername;
  String? lastEmail;
  String? lastFullName;
  String? lastRole;

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
    lastUsername = username;
    lastEmail = email;
    lastFullName = fullName;
    lastRole = role;
    return onInvite?.call() ?? Future<ManagementStaffAccount>.value(_account);
  }

  @override
  Future<List<ManagementDevice>> loadDevices(
    UserSession session, {
    required String deviceId,
    required String userId,
  }) => throw UnimplementedError();

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
