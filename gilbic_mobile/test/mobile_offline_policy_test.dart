import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/offline/mobile_offline_policy.dart';
import 'package:gilbic_mobile/src/features/offline/mobile_offline_policy_page.dart';

void main() {
  test('every role blocks offline financial writes and silent replay', () {
    for (final role in AppRole.values) {
      final policy = MobileOfflinePolicy.forRole(role);

      expect(policy.financialWritesOfflineAllowed, isFalse, reason: role.label);
      expect(policy.financialWritesSilentlyQueued, isFalse, reason: role.label);
      expect(
        policy.financialWritesAutomaticallyRetried,
        isFalse,
        reason: role.label,
      );
    }
  });

  test(
    'protected attendance is conditional and never grants financial retry',
    () {
      expect(
        MobileOfflinePolicy.forRole(AppRole.collector).hasPersistentOfflineData,
        isTrue,
      );
      expect(
        MobileOfflinePolicy.forRole(
          AppRole.collector,
        ).explicitIdempotentRetryAvailable,
        isTrue,
      );

      for (final role in <AppRole>[AppRole.management, AppRole.employee]) {
        final policy = MobileOfflinePolicy.forRole(role);
        expect(policy.hasPersistentOfflineData, isTrue, reason: role.label);
        expect(
          policy.explicitIdempotentRetryAvailable,
          isFalse,
          reason: role.label,
        );
      }
      expect(
        MobileOfflinePolicy.forRole(AppRole.client).hasPersistentOfflineData,
        isFalse,
      );
      expect(
        MobileOfflinePolicy.forRole(
          AppRole.client,
        ).explicitIdempotentRetryAvailable,
        isFalse,
      );
    },
  );

  for (final role in AppRole.values) {
    testWidgets('${role.label} sees its offline and sync boundary', (
      tester,
    ) async {
      await tester.binding.setSurfaceSize(const Size(800, 1400));
      addTearDown(() async {
        await tester.binding.setSurfaceSize(null);
      });

      await tester.pumpWidget(
        MaterialApp(home: MobileOfflinePolicyPage(session: _sessionFor(role))),
      );
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('offline-policy-page')), findsOneWidget);
      expect(find.text('${role.label} offline policy'), findsOneWidget);
      expect(find.text('Financial writes while offline'), findsOneWidget);
      expect(find.text('Silent offline financial write queue'), findsOneWidget);
      expect(find.text('Automatic financial replay'), findsOneWidget);
      expect(find.text('Blocked'), findsOneWidget);
      expect(find.text('Not allowed'), findsNWidgets(2));

      if (role == AppRole.collector) {
        expect(
          find.text('Encrypted route and attendance outbox'),
          findsOneWidget,
        );
        expect(find.byKey(const Key('collector-retry-safety')), findsOneWidget);
        expect(find.textContaining('Offline copy'), findsWidgets);
        expect(find.textContaining('Retry same entry'), findsOneWidget);
      } else if (role == AppRole.employee) {
        expect(find.text('Encrypted attendance outbox'), findsOneWidget);
      } else if (role == AppRole.management) {
        expect(
          find.text('Encrypted own attendance outbox, when configured'),
          findsOneWidget,
        );
        expect(
          find.textContaining('When your own active staff profile'),
          findsOneWidget,
        );
        expect(find.byKey(const Key('collector-retry-safety')), findsNothing);
      } else {
        expect(find.text('None'), findsOneWidget);
        expect(find.byKey(const Key('collector-retry-safety')), findsNothing);
      }
    });
  }
}

UserSession _sessionFor(AppRole role) {
  return UserSession(
    userId: '${role.name}-offline-test',
    username: '${role.name}.one',
    displayName: '${role.label} One',
    role: role,
    rawRole: role.label,
    accessToken: 'token-${role.name}',
    permissions: const <String>[],
  );
}
