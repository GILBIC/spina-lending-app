import 'package:gilbic_mobile/src/app.dart';
import 'package:gilbic_mobile/src/core/auth/auth_repository.dart';
import 'package:gilbic_mobile/src/core/auth/session_store.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache.dart';
import 'package:gilbic_mobile/src/features/dashboard/enhanced_role_dashboard.dart';
import 'support/app_platform_dependencies.dart';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/office/office_repository.dart';
import 'package:gilbic_mobile/src/features/office/office_workspace_page.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';

const employee = UserSession(
  userId: 'synthetic-employee',
  username: 'synthetic',
  displayName: 'Synthetic Employee',
  role: AppRole.employee,
  rawRole: 'Employee',
  accessToken: 'synthetic-token',
  permissions: ['client_onboarding.requirement.review', 'employee.portal.view'],
);

class LostAckIntakeRepository extends OfficeRepository {
  final submitted = <OfficeRecord>[];
  Completer<OfficeRecord>? pending;
  @override
  Future<OfficeRecord> findIntakes(
    OfficeIdentity actor, {
    String query = '',
    String status = '',
    String? cursor,
  }) async => {
    'items': [
      {
        'full_name': 'An unrelated saved applicant',
        'phone_number': '09999999999',
        'intake_status': 'requirements_incomplete',
        'intake_reference': 'UNRELATED',
      },
    ],
    'has_more': false,
  };
  @override
  Future<OfficeRecord> loadIntake(
    OfficeIdentity actor,
    String reference,
  ) async => {
    'applicant_id': 'other-applicant',
    'application_reference': reference,
    'full_name': 'An unrelated saved applicant',
    'status': 'requirements_incomplete',
    'requirements': {},
  };
  @override
  Future<OfficeRecord> submitIntake(
    OfficeIdentity actor,
    OfficeRecord information,
  ) async {
    // Model a committed insert whose acknowledgement is lost. The actual server
    // unconditionally allocates a fresh APP sequence + inserts for each POST.
    submitted.add(Map.of(information));
    if (pending != null) return pending!.future;
    throw const SpinaApiException(
      'Synthetic response lost after commit',
      code: 'network_unavailable',
    );
  }
}

Future<void> fillAndSubmit(
  WidgetTester tester, {
  bool settle = true,
  bool submit = true,
}) async {
  for (final entry in {
    'full_name': 'Synthetic Applicant',
    'phone_number': '09123456789',
    'present_address': 'Synthetic address',
    'national_id_egov_evidence_reference': 'synthetic-national',
    'tin_id_egov_evidence_reference': 'synthetic-tin',
    'meralco_bill_evidence_reference': 'synthetic-bill',
  }.entries) {
    final field = find.byKey(Key('office-${entry.key}'));
    await tester.ensureVisible(field);
    await tester.enterText(field, entry.value);
  }
  for (final text in [
    'The applicant’s required privacy consent has been recorded.',
    'The applicant declared the intake information accurate.',
  ]) {
    await tester.ensureVisible(find.text(text));
    await tester.tap(find.text(text));
    await tester.pump();
  }
  await tester.ensureVisible(find.text('Record office intake'));
  if (submit) await tester.tap(find.text('Record office intake'));
  if (settle) {
    await tester.pumpAndSettle();
  } else {
    await tester.pump();
  }
}

UserSession officeSession({
  String userId = 'synthetic-employee',
  String token = 'rotated',
}) => UserSession(
  userId: userId,
  username: 'synthetic',
  displayName: 'Synthetic Employee',
  role: AppRole.employee,
  rawRole: 'Employee',
  accessToken: token,
  permissions: const [
    'client_onboarding.requirement.review',
    'employee.portal.view',
  ],
);
DeviceIdentityProvider officeDevice() => DeviceIdentityProvider(
  store: MemoryDeviceIdentityStore()..value = 'synthetic-device',
  platformResolver: () => 'android',
  appVersionResolver: () async => 'test',
);
Future<void> openIntake(WidgetTester tester) async {
  await tester.tap(find.text('New office intake'));
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 500));
}

Future<void> mountOffice(
  WidgetTester tester,
  LostAckIntakeRepository repo,
  DeviceIdentityProvider d,
) async {
  await tester.binding.setSurfaceSize(const Size(900, 1800));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(
    MaterialApp(
      home: OfficeWorkspacePage(
        session: employee,
        deviceIdentityProvider: d,
        repository: repo,
      ),
    ),
  );
  await tester.pumpAndSettle();
  await openIntake(tester);
}

class AppAuth extends Fake
    implements AuthRepository, SessionValidationRepository {
  UserSession current = employee;
  @override
  Future<UserSession> validate(UserSession session) async => current;
  @override
  Future<void> signOut(UserSession session) async {}
  @override
  Future<UserSession> signIn({
    required String username,
    required String password,
  }) async => current;
}

void main() {
  testWidgets(
    'app authority keeps create locked after double Back and compatible refresh',
    (tester) async {
      final store = MemorySessionStore();
      await store.write(employee);
      final auth = AppAuth(),
          repo = LostAckIntakeRepository(),
          d = testAppDeviceIdentity();
      await tester.binding.setSurfaceSize(const Size(1000, 1800));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        GilbicApp(
          sessionStore: store,
          authRepository: auth,
          deviceIdentityProvider: d,
          imageRecoveryController: testAppImageRecovery(),
          collectorRouteCache: MemoryCollectorRouteCache(),
        ),
      );
      await tester.pumpAndSettle();
      Future<void> openWorkspace() async {
        final navigator = tester.state<NavigatorState>(
          find.byType(Navigator).first,
        );
        navigator.push<void>(
          MaterialPageRoute(
            builder: (_) => OfficeWorkspacePage(
              session: auth.current,
              deviceIdentityProvider: d,
              repository: repo,
            ),
          ),
        );
        await tester.pumpAndSettle();
        await openIntake(tester);
      }

      await openWorkspace();
      await fillAndSubmit(tester);
      expect(repo.submitted, hasLength(1));
      await tester.pageBack();
      await tester.pumpAndSettle();
      await tester.pageBack();
      await tester.pumpAndSettle();
      auth.current = officeSession();
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pumpAndSettle();
      await openWorkspace();
      await fillAndSubmit(tester);
      expect(repo.submitted, hasLength(1));
      await tester.pageBack();
      await tester.pumpAndSettle();
      await tester.pageBack();
      await tester.pumpAndSettle();
      final logout = tester
          .widget<EnhancedRoleDashboard>(find.byType(EnhancedRoleDashboard))
          .onSignOut();
      await tester.pumpAndSettle();
      await logout;
      auth.current = officeSession(userId: 'new-authority');
      await tester.enterText(
        find.byKey(const Key('username-field')),
        'synthetic',
      );
      await tester.enterText(
        find.byKey(const Key('password-field')),
        'synthetic-password',
      );
      await tester.tap(find.byKey(const Key('sign-in-button')));
      await tester.pumpAndSettle();
      await openWorkspace();
      await fillAndSubmit(tester);
      expect(repo.submitted, hasLength(2));
    },
  );

  testWidgets('saved-record Finder cannot provide a fresh create owner', (
    tester,
  ) async {
    final repo = LostAckIntakeRepository(), d = officeDevice();
    await mountOffice(tester, repo, d);
    await fillAndSubmit(tester);
    await tester.pageBack();
    await tester.pumpAndSettle();
    await tester.tap(
      find.widgetWithText(FilledButton, 'Find an intake or application'),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Continue UNRELATED'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Find by intake reference'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('office-reference')), '');
    await tester.pumpAndSettle();
    await fillAndSubmit(tester, submit: false);
    expect(
      tester
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, 'Record office intake'),
          )
          .onPressed,
      isNull,
    );
    expect(repo.submitted, hasLength(1));
  });

  for (final success in [false, true]) {
    testWidgets(
      'system Back preserves in-flight create and original completion $success',
      (tester) async {
        final repo = LostAckIntakeRepository()
          ..pending = Completer<OfficeRecord>();
        final d = officeDevice();
        await mountOffice(tester, repo, d);
        await fillAndSubmit(tester, settle: false);
        expect(repo.submitted, hasLength(1));
        await tester.binding.handlePopRoute();
        await tester.pumpAndSettle();
        await tester.pumpWidget(
          MaterialApp(
            home: OfficeWorkspacePage(
              session: officeSession(),
              deviceIdentityProvider: d,
              repository: repo,
            ),
          ),
        );
        await tester.pumpAndSettle();
        await openIntake(tester);
        await fillAndSubmit(tester, settle: false, submit: false);
        expect(
          tester
              .widget<FilledButton>(
                find.widgetWithText(FilledButton, 'Record office intake'),
              )
              .onPressed,
          isNull,
        );
        if (success) {
          repo.pending!.complete({
            'application_reference': 'ORIGINAL-1',
            'applicant_id': 'original',
            'full_name': 'Synthetic Applicant',
          });
        } else {
          repo.pending!.completeError(
            const SpinaApiException(
              'Lost response',
              code: 'network_unavailable',
            ),
          );
        }
        await tester.pumpAndSettle();
        repo.pending = null;
        if (success) {
          await tester.tap(find.text('Record office intake'));
          await tester.pumpAndSettle();
          expect(repo.submitted, hasLength(2));
        } else {
          expect(
            tester
                .widget<FilledButton>(
                  find.widgetWithText(FilledButton, 'Record office intake'),
                )
                .onPressed,
            isNull,
          );
          expect(repo.submitted, hasLength(1));
        }
      },
    );
  }
  testWidgets(
    'unrelated saved intake read cannot resolve unknown create; authority replacement can',
    (tester) async {
      final repo = LostAckIntakeRepository();
      final d = officeDevice();
      await mountOffice(tester, repo, d);
      await fillAndSubmit(tester);
      await tester.pageBack();
      await tester.pumpAndSettle();
      await openIntake(tester);
      await tester.tap(find.text('Find by intake reference'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('office-reference')),
        'UNRELATED',
      );
      await tester.tap(find.text('Open office intake'));
      await tester.pumpAndSettle();
      expect(find.text('An unrelated saved applicant'), findsOneWidget);
      await tester.pageBack();
      await tester.pumpAndSettle();
      await openIntake(tester);
      expect(
        tester
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, 'Record office intake'),
            )
            .onPressed,
        isNull,
      );
      await tester.pumpWidget(
        MaterialApp(
          home: OfficeWorkspacePage(
            session: officeSession(userId: 'new-authority'),
            deviceIdentityProvider: d,
            repository: repo,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Office workflow'), findsOneWidget);
      await openIntake(tester);
      await fillAndSubmit(tester);
      expect(repo.submitted, hasLength(2));
    },
  );

  testWidgets(
    'ordinary Back cannot discard an uncertain Office intake and permit a duplicate',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(900, 1800));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final repo = LostAckIntakeRepository();
      final device = DeviceIdentityProvider(
        store: MemoryDeviceIdentityStore()..value = 'synthetic-device',
        platformResolver: () => 'android',
        appVersionResolver: () async => 'test',
      );
      await tester.pumpWidget(
        MaterialApp(
          home: OfficeWorkspacePage(
            session: employee,
            deviceIdentityProvider: device,
            repository: repo,
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('New office intake'));
      await tester.pumpAndSettle();
      await fillAndSubmit(tester);
      expect(repo.submitted, hasLength(1));
      final submit = tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Record office intake'),
      );
      expect(
        submit.onPressed,
        isNull,
        reason: 'The current mount correctly blocks the uncertain write',
      );
      await tester.pageBack();
      await tester.pumpAndSettle();
      // No explicit discard/cancel/reconciliation occurred; ordinary Back loses
      // the mount-owned blocked state, and the launcher constructs a fresh one.
      if (find.text('Office workflow').evaluate().isNotEmpty) {
        await tester.tap(find.text('New office intake'));
        await tester.pumpAndSettle();
        await fillAndSubmit(tester);
      }
      expect(
        repo.submitted,
        hasLength(1),
        reason:
            'Uncertain create must remain blocked across ordinary navigation until its authoritative outcome is reconciled',
      );
    },
  );
}
