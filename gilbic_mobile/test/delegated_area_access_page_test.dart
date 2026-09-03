import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/delegated_area_access.dart';
import 'package:gilbic_mobile/src/core/collector/delegated_area_repository.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/features/collector/delegated_area_access_page.dart';

void main() {
  testWidgets(
    'assigned collector can approve only own-area request and visitor sees active grant',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(900, 1600));
      addTearDown(() async => tester.binding.setSurfaceSize(null));
      final repository = _DelegatedRepository();

      await tester.pumpWidget(
        MaterialApp(
          home: DelegatedAreaAccessPage(
            session: _collectorSession,
            deviceIdentityProvider: _deviceIdentityProvider(),
            repository: repository,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Temporary Area Access'), findsOneWidget);
      expect(find.textContaining('never changes route ownership'), findsOneWidget);
      expect(find.textContaining('SECOND TEST AREA'), findsWidgets);
      expect(find.text('Visiting Collector'), findsOneWidget);
      expect(find.byKey(const Key('approve-delegated-request-in')), findsOneWidget);

      await tester.tap(find.byKey(const Key('approve-delegated-request-in')));
      await tester.pumpAndSettle();
      expect(find.text('Allow temporary access?'), findsOneWidget);
      await tester.tap(find.text('Allow Access').last);
      await tester.pumpAndSettle();

      expect(repository.approved, <String>['request-in']);
    },
  );

  testWidgets('Request All Areas fans out one owner-specific request per collector',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(900, 1600));
    addTearDown(() async => tester.binding.setSurfaceSize(null));
    final repository = _DelegatedRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: DelegatedAreaAccessPage(
          session: _collectorSession,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('request-delegated-access')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('delegated-request-reason')),
      'Help cover today route',
    );
    await tester.tap(find.byKey(const Key('request-all-delegated-areas')));
    await tester.pumpAndSettle();

    expect(repository.createdOwners.toSet(), <String>{'owner-two', 'owner-three'});
    expect(repository.createdAllOwnerAreas, everyElement(isTrue));
  });
}

const UserSession _collectorSession = UserSession(
  userId: 'collector-one',
  username: 'collector.one',
  displayName: 'Collector One',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'collector-token',
  permissions: <String>[
    'delegated_area.view',
    'delegated_area.request',
    'delegated_area.grant',
  ],
);

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'android-delegated-test';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0-test',
  );
}

class _DelegatedRepository implements DelegatedAreaRepository {
  final List<String> approved = <String>[];
  final List<String> createdOwners = <String>[];
  final List<bool> createdAllOwnerAreas = <bool>[];

  @override
  Future<List<DelegatedAreaScope>> availableScopes(UserSession session) async {
    return const <DelegatedAreaScope>[
      DelegatedAreaScope(
        assignmentId: 'assignment-two',
        ownerUserId: 'owner-two',
        ownerName: 'Collector Two',
        areaPath: 'AREA TWO',
        sortOrder: 1,
      ),
      DelegatedAreaScope(
        assignmentId: 'assignment-three',
        ownerUserId: 'owner-three',
        ownerName: 'Collector Three',
        areaPath: 'AREA THREE',
        sortOrder: 2,
      ),
    ];
  }

  @override
  Future<List<DelegatedAreaRequest>> incomingRequests(UserSession session) async {
    return <DelegatedAreaRequest>[
      DelegatedAreaRequest(
        requestId: 'request-in',
        requesterUserId: 'visitor-two',
        requesterName: 'Visiting Collector',
        requestedOwnerUserId: session.userId,
        requestedOwnerName: session.displayName,
        scopeMode: 'all_owner_areas',
        reason: 'Route help',
        requestedExpiresAt: DateTime.utc(2026, 8, 19, 4),
        status: 'pending',
        decisionReason: '',
        createdAt: DateTime.utc(2026, 8, 18, 4),
        scopes: const <DelegatedAreaScope>[
          DelegatedAreaScope(
            assignmentId: 'assignment-owned',
            ownerUserId: 'collector-one',
            ownerName: 'Collector One',
            areaPath: 'MY TEST AREA',
            sortOrder: 1,
            includeDescendants: true,
          ),
        ],
      ),
    ];
  }

  @override
  Future<List<DelegatedAreaRequest>> outgoingRequests(UserSession session) async {
    return const <DelegatedAreaRequest>[];
  }

  @override
  Future<List<DelegatedAreaGrant>> activeGrants(UserSession session) async {
    return <DelegatedAreaGrant>[
      DelegatedAreaGrant(
        grantId: 'grant-active',
        sourceRequestId: 'request-active',
        grantorUserId: 'owner-two',
        grantorName: 'Collector Two',
        visitingCollectorUserId: session.userId,
        visitingCollectorName: session.displayName,
        effectiveAt: DateTime.utc(2026, 8, 18, 3),
        expiresAt: DateTime.utc(2026, 8, 19, 3),
        revokedAt: null,
        revocationReason: '',
        scopes: const <DelegatedAreaScope>[
          DelegatedAreaScope(
            assignmentId: 'assignment-active',
            ownerUserId: 'owner-two',
            ownerName: 'Collector Two',
            areaPath: 'SECOND TEST AREA',
            sortOrder: 1,
            includeDescendants: true,
          ),
        ],
      ),
    ];
  }

  @override
  Future<DelegatedAreaRequest> createRequest(
    UserSession session, {
    required String ownerUserId,
    required List<DelegatedAreaScope> scopes,
    required bool allOwnerAreas,
    required String reason,
    required DateTime expiresAt,
  }) async {
    createdOwners.add(ownerUserId);
    createdAllOwnerAreas.add(allOwnerAreas);
    return DelegatedAreaRequest(
      requestId: 'new-$ownerUserId',
      requesterUserId: session.userId,
      requesterName: session.displayName,
      requestedOwnerUserId: ownerUserId,
      requestedOwnerName: ownerUserId,
      scopeMode: allOwnerAreas ? 'all_owner_areas' : 'selected_paths',
      reason: reason,
      requestedExpiresAt: expiresAt,
      status: 'pending',
      decisionReason: '',
      createdAt: DateTime.now().toUtc(),
      scopes: scopes,
    );
  }

  @override
  Future<DelegatedAreaGrant> approveRequest(
    UserSession session,
    String requestId, {
    String reason = '',
  }) async {
    approved.add(requestId);
    return DelegatedAreaGrant(
      grantId: 'approved-$requestId',
      sourceRequestId: requestId,
      grantorUserId: session.userId,
      grantorName: session.displayName,
      visitingCollectorUserId: 'visitor-two',
      visitingCollectorName: 'Visiting Collector',
      effectiveAt: DateTime.now().toUtc(),
      expiresAt: DateTime.now().toUtc().add(const Duration(hours: 24)),
      revokedAt: null,
      revocationReason: '',
      scopes: const <DelegatedAreaScope>[],
    );
  }

  @override
  Future<DelegatedAreaRequest> declineRequest(
    UserSession session,
    String requestId, {
    String reason = '',
  }) async {
    return incomingRequests(session).then((items) => items.first);
  }

  @override
  Future<DelegatedAreaRequest> cancelRequest(
    UserSession session,
    String requestId, {
    String reason = '',
  }) async {
    throw UnimplementedError();
  }

  @override
  Future<DelegatedAreaGrant> revokeGrant(
    UserSession session,
    String grantId, {
    required String reason,
  }) async {
    throw UnimplementedError();
  }
}
