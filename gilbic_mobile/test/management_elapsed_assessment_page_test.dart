import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_elapsed_assessment_page.dart';
import 'elapsed_assessment_evidence_test.dart' as fixtures;

UserSession session({String token = 'token', bool prepare = true}) =>
    UserSession(
      userId: fixtures.elapsedId(2),
      username: 'manager',
      displayName: 'Manager',
      role: AppRole.management,
      rawRole: 'Management',
      accessToken: token,
      permissions: [
        'accounting.view',
        if (prepare) ...[
          'accounting.period.close.prepare',
          'accounting.period.close.post',
        ],
      ],
    );
DeviceIdentityProvider device() => DeviceIdentityProvider(
  store: MemoryDeviceIdentityStore()..value = 'installation',
  platformResolver: () => 'android',
  appVersionResolver: () async => '1.0.0',
);

class Repo implements SourceAccountingRepository {
  final writes = <(String, Map<String, dynamic>)>[];
  bool fail = false;
  bool settled = false;
  Completer<Map<String, dynamic>>? delayed;
  @override
  Future<Map<String, dynamic>> read(
    UserSession session, {
    required String deviceId,
    required String path,
  }) async {
    if (path.endsWith('/book')) return {'book': fixtures.elapsedBook};
    if (path.contains('/ecl-forward-looking-evidence')) {
      return {
        'items': [
          for (var i = 0; i < 2; i++)
            {
              'id': fixtures.elapsedId(10 + i),
              'source_name': 'Forecast ${i + 1}',
              'source_reference': 'Forecast reference ${i + 1}',
              'effective_date': '2026-09-01',
              'forecast_period_start': '2026-09-01',
              'forecast_period_end': '2026-12-31',
              'evidence_status': 'current',
            },
        ],
      };
    }
    if (path.contains('/period-elapsed-assessments/')) {
      return delayed == null
          ? settled
                ? fixtures.settledCandidateFixture
                : fixtures.elapsedCandidateFixture
          : await delayed!.future;
    }
    return {
      'fiscal_periods': [
        {'period_id': fixtures.elapsedId(3), 'label': 'September'},
      ],
    };
  }

  @override
  Future<Map<String, dynamic>> write(
    UserSession session, {
    required String deviceId,
    required String path,
    required Map<String, dynamic> body,
  }) async {
    writes.add((path, jsonDecode(jsonEncode(body)) as Map<String, dynamic>));
    if (fail) {
      throw const SpinaApiException(
        'Lost response',
        code: 'network_unavailable',
      );
    }
    if (path.endsWith('/prepare-settled')) {
      return fixtures.settledPreparationFixture;
    }
    return path.endsWith('/prepare')
        ? fixtures.elapsedPreparationFixture
        : {'posting_id': fixtures.elapsedId(6)};
  }
}

Future<void> tap(WidgetTester tester, String key) async {
  final target = find.byKey(Key(key));
  await tester.scrollUntilVisible(
    target,
    250,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pumpAndSettle();
  await tester.tap(target);
  await tester.pumpAndSettle();
}

Future<void> enter(WidgetTester tester, String key, String value) async {
  await tester.scrollUntilVisible(
    find.byKey(Key(key)),
    250,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pumpAndSettle();
  await tester.enterText(find.byKey(Key(key)), value);
  await tester.pumpAndSettle();
}

Future<void> pump(
  WidgetTester tester,
  Repo repo, {
  UserSession? actor,
  DeviceIdentityProvider? identity,
}) async {
  await tester.binding.setSurfaceSize(const Size(700, 1000));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(
    MaterialApp(
      home: ManagementElapsedAssessmentPage(
        session: actor ?? session(),
        deviceIdentityProvider: identity ?? device(),
        repository: repo,
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> lookup(WidgetTester tester) async {
  await tap(tester, 'elapsed-period');
  await tester.tap(find.text('September').last);
  await tester.pumpAndSettle();
  await enter(tester, 'elapsed-loan', fixtures.elapsedId(4));
  await tap(tester, 'elapsed-lookup');
}

Future<void> fill(WidgetTester tester) async {
  final x = fixtures.elapsedInputFixture;
  for (final k in ['evidence_reference', 'review_note']) {
    await enter(tester, 'elapsed-$k', x[k] as String);
  }
  final scenarios = x['scenarios'] as List;
  for (var i = 0; i < 2; i++) {
    final s = scenarios[i] as Map;
    for (final k in [
      'scenario_key',
      'probability',
      'evidence_reference',
      'management_rationale',
    ]) {
      await enter(tester, 'elapsed-s$i-$k', s[k] as String);
    }
    await tap(tester, 'elapsed-s$i-evidence');
    await tester.tap(
      find.text('Forecast ${i + 1} · Forecast reference ${i + 1}').last,
    );
    await tester.pumpAndSettle();
    await enter(tester, 'elapsed-s$i-c0-date', '2026-10-20');
    await enter(tester, 'elapsed-s$i-c0-amount', '5000.00');
  }
  await enter(
    tester,
    'elapsed-review_rationale',
    x['review_rationale'] as String,
  );
}

void main() {
  testWidgets(
    'settled payoff review has no scenarios and separately confirms posting',
    (tester) async {
      final repo = Repo()..settled = true;
      await pump(tester, repo);
      await lookup(tester);
      expect(find.byKey(const Key('elapsed-prepare')), findsNothing);
      await enter(
        tester,
        'elapsed-settled-rationale',
        fixtures.settledRationale,
      );
      await tap(tester, 'elapsed-prepare-settled');
      expect(repo.writes, isEmpty);
      await tap(tester, 'elapsed-confirm');
      expect(repo.writes.single.$1, endsWith('/prepare-settled'));
      expect(repo.writes.single.$2, {
        'expected_book_id': fixtures.elapsedId(1),
        'source_digest': 'a' * 64,
        'payoff_review_id': fixtures.elapsedId(20),
        'review_rationale': fixtures.settledRationale,
        'confirm': true,
      });
      await tap(tester, 'elapsed-post');
      expect(find.textContaining('Allowance change: -4.00'), findsOneWidget);
      expect(repo.writes.length, 1);
      await tap(tester, 'elapsed-confirm');
      expect(repo.writes.length, 2);
      expect(find.textContaining('Assessment posted'), findsOneWidget);
    },
  );
  testWidgets(
    'retains explicit scenarios then separately confirms the dated calculation',
    (tester) async {
      final repo = Repo();
      await pump(tester, repo);
      await lookup(tester);
      await fill(tester);
      await tap(tester, 'elapsed-prepare');
      expect(repo.writes, isEmpty);
      await tap(tester, 'elapsed-confirm');
      expect(repo.writes.length, 1);
      await tester.scrollUntilVisible(
        find.byKey(const Key('elapsed-post')),
        250,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.textContaining('2026-10-05T08:12:00'), findsOneWidget);
      expect(find.textContaining('Allowance change: -0.50'), findsOneWidget);
      await tap(tester, 'elapsed-post');
      expect(repo.writes.length, 1);
      await tap(tester, 'elapsed-confirm');
      expect(repo.writes.length, 2);
      expect(repo.writes.last.$2, {
        'expected_book_id': fixtures.elapsedId(1),
        'confirmation_digest': 'b' * 64,
        'confirm': true,
      });
      expect(find.textContaining('Assessment posted'), findsOneWidget);
    },
  );
  testWidgets(
    'lost result retries identical financial input and view-only sessions cannot prepare',
    (tester) async {
      final repo = Repo()..fail = true;
      await pump(tester, repo);
      await lookup(tester);
      await fill(tester);
      await tap(tester, 'elapsed-prepare');
      await tap(tester, 'elapsed-confirm');
      expect(find.byKey(const Key('elapsed-prepare')), findsNothing);
      repo.fail = false;
      await tap(tester, 'elapsed-retry');
      expect(repo.writes[0].$2, repo.writes[1].$2);
      await pump(tester, repo, actor: session(token: 'new', prepare: false));
      await lookup(tester);
      expect(find.byKey(const Key('elapsed-prepare')), findsNothing);
      expect(
        find.textContaining('preparation permission is required'),
        findsOneWidget,
      );
    },
  );
  testWidgets('session replacement discards a delayed private candidate', (
    tester,
  ) async {
    final repo = Repo()..delayed = Completer<Map<String, dynamic>>();
    final identity = device();
    await pump(tester, repo, identity: identity);
    await tap(tester, 'elapsed-period');
    await tester.tap(find.text('September').last);
    await tester.pumpAndSettle();
    await enter(tester, 'elapsed-loan', fixtures.elapsedId(4));
    await tester.tap(find.byKey(const Key('elapsed-lookup')));
    await tester.pump();
    await tester.pumpWidget(
      MaterialApp(
        home: ManagementElapsedAssessmentPage(
          session: session(token: 'replacement', prepare: false),
          repository: repo,
          deviceIdentityProvider: identity,
        ),
      ),
    );
    repo.delayed!.complete(fixtures.elapsedCandidateFixture);
    await tester.pumpAndSettle();
    expect(find.textContaining('5062.58'), findsNothing);
    expect(repo.writes, isEmpty);
  });
}
