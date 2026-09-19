import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/features/account/client_password_reset_page.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  for (final role in AppRole.values) {
    testWidgets(
      'direct ${role.name} page requires both a staff role and credential permission',
      (tester) async {
        var requests = 0;
        final hasPermission =
            role == AppRole.collector || role == AppRole.client;
        await http.runWithClient(
          () async {
            await _pump(
              tester,
              session: _session(role, permitted: hasPermission),
            );
            expect(
              find.byKey(const Key('client-password-search')),
              findsNothing,
            );
            expect(find.text('Access unavailable'), findsOneWidget);
            expect(requests, 0);
          },
          () => MockClient((request) async {
            requests++;
            return _response(_accounts());
          }),
        );
      },
    );
  }

  for (final failure in <String>['transport', 'server', 'malformed success']) {
    testWidgets(
      '$failure reset result requires a fresh search and acknowledgment before another reset',
      (tester) async {
        var resets = 0;
        await http.runWithClient(
          () async {
            await _pump(tester);
            await _search(tester);
            await _reset(tester);
            expect(resets, 1);
            expect(
              find.byKey(const Key('client-password-reset-uncertain')),
              findsOneWidget,
            );
            expect(tester.widget<TextButton>(_resetButton).onPressed, isNull);

            await _search(tester);
            expect(resets, 1);
            expect(tester.widget<TextButton>(_resetButton).onPressed, isNull);
            await tester.tap(
              find.byKey(const Key('client-password-reset-acknowledge')),
            );
            await tester.pumpAndSettle();
            await _reset(tester);
            expect(resets, 2);
            expect(
              find.byKey(const Key('client-password-reset-result')),
              findsOneWidget,
            );
          },
          () => MockClient((request) async {
            if (request.method == 'GET') return _response(_accounts());
            resets++;
            if (resets > 1) return _response(_resetResult());
            return switch (failure) {
              'transport' => throw http.ClientException(
                'Connection closed after request.',
              ),
              'server' => http.Response('Server unavailable', 503),
              _ => _response(<String, Object?>{
                'credentials': <String, Object?>{},
              }),
            };
          }),
        );
      },
    );
  }

  for (final status in <int>[401, 403, 426]) {
    testWidgets(
      'reset rejection $status clears private accounts and blocks further access even with unreadable response',
      (tester) async {
        var resets = 0;
        await http.runWithClient(
          () async {
            await _pump(tester);
            await _search(tester);
            expect(find.text('Maria Santos'), findsOneWidget);
            await _reset(tester);
            expect(resets, 1);
            expect(find.text('Maria Santos'), findsNothing);
            expect(
              find.byKey(const Key('client-password-reset-result')),
              findsNothing,
            );
            expect(
              find.byKey(const Key('client-password-search')),
              findsNothing,
            );
            expect(find.text('Access unavailable'), findsOneWidget);
          },
          () => MockClient((request) async {
            if (request.method == 'GET') return _response(_accounts());
            resets++;
            return http.Response('Unreadable rejection', status);
          }),
        );
      },
    );
  }

  testWidgets(
    'repeated submitted search action cannot create concurrent requests',
    (tester) async {
      final response = Completer<http.Response>();
      var searches = 0;
      await http.runWithClient(
        () async {
          await _pump(tester);
          await tester.enterText(
            find.byKey(const Key('client-password-search')),
            'Maria',
          );
          final submit = tester
              .widget<TextField>(
                find.byKey(const Key('client-password-search')),
              )
              .onSubmitted!;
          submit('Maria');
          submit('Maria');
          await tester.pump();
          expect(searches, 1);
          response.complete(_response(_accounts()));
          await tester.pumpAndSettle();
          expect(find.text('Maria Santos'), findsOneWidget);
        },
        () => MockClient((request) async {
          searches++;
          return response.future;
        }),
      );
    },
  );

  testWidgets(
    'stale reset action cannot open confirmation while search is refreshing',
    (tester) async {
      final refreshed = Completer<http.Response>();
      var searches = 0;
      await http.runWithClient(
        () async {
          await _pump(tester);
          await _search(tester);
          final reset = tester.widget<TextButton>(_resetButton).onPressed!;
          await tester.tap(
            find.byKey(const Key('client-password-search-submit')),
          );
          await tester.pump();
          reset();
          await tester.pump();
          expect(find.text('Reset Client password?'), findsNothing);
          refreshed.complete(_response(_accounts()));
          await tester.pumpAndSettle();
        },
        () => MockClient((request) async {
          searches++;
          return searches == 1 ? _response(_accounts()) : refreshed.future;
        }),
      );
    },
  );

  testWidgets(
    'account change discards an old in-flight private search result',
    (tester) async {
      final response = Completer<http.Response>();
      await http.runWithClient(() async {
        await _pump(tester);
        await tester.enterText(
          find.byKey(const Key('client-password-search')),
          'Maria',
        );
        await tester.tap(
          find.byKey(const Key('client-password-search-submit')),
        );
        await tester.pump();
        await _pump(tester, session: _session(AppRole.management));
        response.complete(_response(_accounts()));
        await tester.pumpAndSettle();
        expect(find.text('Maria Santos'), findsNothing);
        expect(
          find.byKey(const Key('client-password-reset-result')),
          findsNothing,
        );
      }, () => MockClient((request) async => response.future));
    },
  );
}

final _resetButton = find.byKey(const Key('client-password-reset-client-1'));

UserSession _session(AppRole role, {bool permitted = true}) => UserSession(
  userId: 'staff-${role.name}',
  username: '${role.name}.one',
  displayName: 'Staff One',
  role: role,
  rawRole: role.label,
  accessToken: 'staff-token',
  permissions: permitted
      ? const <String>['client.credential.manage']
      : const <String>[],
);

Future<void> _pump(WidgetTester tester, {UserSession? session}) async {
  await tester.binding.setSurfaceSize(const Size(650, 1200));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(
    MaterialApp(
      home: ClientPasswordResetPage(
        session: session ?? _session(AppRole.employee),
        deviceIdentityProvider: DeviceIdentityProvider(
          store: MemoryDeviceIdentityStore()..value = 'staff-device',
          platformResolver: () => 'android',
          appVersionResolver: () async => '1.0.0',
        ),
      ),
    ),
  );
  // A pending HTTP operation must not prevent testing a session change.
  await tester.pump();
}

Future<void> _search(WidgetTester tester) async {
  await tester.enterText(
    find.byKey(const Key('client-password-search')),
    'Maria',
  );
  await tester.tap(find.byKey(const Key('client-password-search-submit')));
  await tester.pumpAndSettle();
}

Future<void> _reset(WidgetTester tester) async {
  await tester.ensureVisible(_resetButton);
  await tester.tap(_resetButton);
  await tester.pumpAndSettle();
  await tester.tap(find.widgetWithText(FilledButton, 'Reset password'));
  await tester.pumpAndSettle();
}

http.Response _response(Map<String, Object?> data) => http.Response(
  jsonEncode(<String, Object?>{'success': true, 'data': data}),
  200,
);
Map<String, Object?> _account() => <String, Object?>{
  'id': 'client-1',
  'username': 'maria.client',
  'full_name': 'Maria Santos',
  'status': 'active',
  'email': 'maria@example.com',
  'roles': <String>['client'],
};
Map<String, Object?> _accounts() => <String, Object?>{
  'accounts': <Object?>[_account()],
};
Map<String, Object?> _resetResult() => <String, Object?>{
  'account': _account(),
  'credentials': <String, Object?>{
    'username': 'maria.client',
    'password': 'temporary-secret',
  },
  'delivery': <String, Object?>{
    'sent': true,
    'detail': 'Credentials sent by email.',
  },
  'audit_recorded': true,
};
