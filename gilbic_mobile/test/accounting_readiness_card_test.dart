import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/accounting_readiness_repository.dart';
import 'package:gilbic_mobile/src/features/management/accounting_readiness_card.dart';

const first = '11111111-1111-4111-8111-111111111111';
const second = '22222222-2222-4222-8222-222222222222';
const session = UserSession(
  userId: 'manager',
  username: 'manager',
  displayName: 'Manager',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'private-token',
  permissions: ['accounting.view'],
);

void main() {
  testWidgets('restricted sources stay in the count without private values', (
    tester,
  ) async {
    final repository = _Repository();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: AccountingReadinessCard(
            session: session,
            deviceIdentityProvider: _device(),
            repository: repository,
            periodId: first,
            showBook: false,
          ),
        ),
      ),
    );
    await tester.pump();
    repository.pending[first]!.complete(
      AccountingSourceCoverage.fromPayload({
        'comprehensive_source_coverage': false,
        'source_families': ['treasury', 'collector'],
        'limit': 100,
        'offset': 0,
        'blocker_count': 120,
        'blockers': [
          {
            'source_type': 'restricted_source',
            'source_id': null,
            'effective_date': null,
            'amount': null,
            'reason': 'treasury_account_access_required',
          },
        ],
      }),
    );
    await tester.pumpAndSettle();
    expect(
      find.text('Restricted source — Treasury account access required'),
      findsOneWidget,
    );
    expect(find.text('Showing 1–1 of 120 source blockers.'), findsOneWidget);
    expect(
      find.textContaining('full blocker inventory is not shown'),
      findsOneWidget,
    );
    expect(find.textContaining('Source reference:'), findsNothing);
    expect(find.textContaining('PHP'), findsNothing);
    expect(find.textContaining('null'), findsNothing);
  });

  testWidgets('unconfigured book and balanced-ledger limits stay explicit', (
    tester,
  ) async {
    final repository = _Repository();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: AccountingReadinessCard(
            session: session,
            deviceIdentityProvider: _device(),
            repository: repository,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(
      find.textContaining('Book identity is unconfigured'),
      findsOneWidget,
    );
    expect(find.textContaining('posted ledger only'), findsOneWidget);
    expect(
      find.textContaining('does not establish accounting readiness'),
      findsOneWidget,
    );
  });

  testWidgets(
    'period changes discard the old private response and empty results never certify readiness',
    (tester) async {
      final repository = _Repository();
      final device = _device();
      Future<void> render(String period) => tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AccountingReadinessCard(
              session: session,
              deviceIdentityProvider: device,
              repository: repository,
              periodId: period,
              showBook: false,
            ),
          ),
        ),
      );
      await render(first);
      await tester.pump();
      await render(second);
      await tester.pump();
      repository.pending[first]!.complete(_coverage('Old private source'));
      await tester.pump();
      expect(find.textContaining('Old private source'), findsNothing);
      repository.pending[second]!.complete(_coverage(null));
      await tester.pumpAndSettle();
      expect(find.textContaining('Partial source coverage'), findsOneWidget);
      expect(find.textContaining('does not certify readiness'), findsWidgets);
    },
  );

  testWidgets('session authority changes erase already loaded private rows', (
    tester,
  ) async {
    final repository = _Repository();
    final device = _device();
    Future<void> render(UserSession actor) => tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: AccountingReadinessCard(
            session: actor,
            deviceIdentityProvider: device,
            repository: repository,
            periodId: first,
            showBook: false,
          ),
        ),
      ),
    );
    await render(session);
    await tester.pump();
    repository.pending[first]!.complete(_coverage('Private source evidence'));
    await tester.pumpAndSettle();
    expect(find.text('Private source evidence'), findsOneWidget);
    const denied = UserSession(
      userId: 'other',
      username: 'other',
      displayName: 'Other',
      role: AppRole.employee,
      rawRole: 'Employee',
      accessToken: 'other-token',
    );
    await render(denied);
    await tester.pumpAndSettle();
    expect(find.text('Private source evidence'), findsNothing);
    expect(
      find.textContaining('Accounting access is unavailable'),
      findsOneWidget,
    );
  });
}

DeviceIdentityProvider _device() => DeviceIdentityProvider(
  store: MemoryDeviceIdentityStore()..value = 'phone',
  platformResolver: () => 'android',
  appVersionResolver: () async => '1.0',
);
AccountingSourceCoverage _coverage(String? reason) =>
    AccountingSourceCoverage.fromPayload({
      'comprehensive_source_coverage': false,
      'limit': 100,
      'offset': 0,
      'blocker_count': reason == null ? 0 : 1,
      'source_families': ['treasury', 'collector'],
      'blockers': [
        if (reason != null)
          {
            'source_type': 'treasury_receipt',
            'source_id': first,
            'effective_date': '2026-09-30',
            'amount': '12.34',
            'reason': reason,
          },
      ],
    });

class _Repository implements AccountingReadinessRepository {
  final pending = <String, Completer<AccountingSourceCoverage>>{};
  @override
  Future<AccountingBookIdentity> loadBook(
    UserSession session, {
    required String deviceId,
  }) async => AccountingBookIdentity.fromPayload({
    'status': 'unconfigured',
    'book_id': null,
    'kind': null,
    'entity_label': null,
  });
  @override
  Future<AccountingSourceCoverage> loadSourceCoverage(
    UserSession session, {
    required String deviceId,
    required String periodId,
  }) => (pending[periodId] = Completer<AccountingSourceCoverage>()).future;
}
