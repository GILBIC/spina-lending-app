import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/app.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/auth_repository.dart';
import 'package:gilbic_mobile/src/core/auth/session_store.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_repository.dart';

void main() {
  testWidgets('signs in and opens the assigned collector route', (tester) async {
    await tester.pumpWidget(
      GilbicApp(
        sessionStore: MemorySessionStore(),
        authRepository: _FakeAuthRepository(),
        collectorRouteRepository: _FakeCollectorRouteRepository(),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byKey(const Key('username-field')),
      'collector.one',
    );
    await tester.enterText(
      find.byKey(const Key('password-field')),
      'secret',
    );
    await tester.tap(find.byKey(const Key('sign-in-button')));
    await tester.pumpAndSettle();

    expect(find.text('Collector Dashboard'), findsOneWidget);
    expect(find.text('Daily Route'), findsOneWidget);
    expect(find.text('Offline Sync'), findsOneWidget);

    await tester.tap(find.byKey(const Key('daily-route')));
    await tester.pumpAndSettle();

    expect(find.text('Daily Route'), findsOneWidget);
    expect(find.text('Ana Client'), findsOneWidget);
    expect(find.textContaining('Expected collection'), findsOneWidget);
    expect(find.textContaining('Read-only route'), findsOneWidget);
  });
}

class _FakeAuthRepository implements AuthRepository {
  @override
  Future<UserSession> signIn({
    required String username,
    required String password,
  }) async {
    expect(username, 'collector.one');
    expect(password, 'secret');
    return const UserSession(
      userId: 'collector-1',
      username: 'collector.one',
      displayName: 'Test Collector',
      role: AppRole.collector,
      rawRole: 'Collector',
      accessToken: 'test-token',
      permissions: <String>['route.view'],
    );
  }

  @override
  Future<void> signOut(UserSession session) async {}
}

class _FakeCollectorRouteRepository implements CollectorRouteRepository {
  @override
  Future<CollectorRoute> fetchToday(UserSession session) async {
    return CollectorRoute(
      routeDate: DateTime(2026, 7, 31),
      collectorName: 'Test Collector',
      areas: const <String>['Cardona'],
      expectedTotal: 200,
      entries: const <CollectorRouteEntry>[
        CollectorRouteEntry(
          id: 'entry-1',
          clientId: 'client-1',
          loanId: 'loan-1',
          clientName: 'Ana Client',
          area: 'Cardona',
          loanType: 'Regular',
          dailyAmount: 200,
          balance: 4800,
          status: 'Pending',
          passCount: 0,
        ),
      ],
    );
  }
}
