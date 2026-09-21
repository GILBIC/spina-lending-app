import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/features/collector/collector_cash_status_card.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  testWidgets('initial cash load shows progress without invented amounts',
      (tester) async {
    final pending = Completer<http.Response>();
    await http.runWithClient(
      () async {
        await _pump(tester);
        expect(find.byType(CircularProgressIndicator), findsOneWidget);
        _expectNoCashAmounts();
        pending.complete(_cashResponse());
        await tester.pumpAndSettle();
        _expectActualCash();
      },
      () => MockClient((request) => pending.future),
    );
  });

  testWidgets('device failure shows unavailable and sends no cash request',
      (tester) async {
    var requests = 0;
    await http.runWithClient(
      () async {
        await _pump(tester, identity: _identity(fail: true));
        await tester.pumpAndSettle();
        _expectUnavailable();
        expect(requests, 0);
      },
      () => MockClient((request) async {
        requests++;
        return _cashResponse();
      }),
    );
  });

  for (final failure in <String>[
    'offline',
    '401',
    '403',
    '503',
    'missing total',
    'invalid total',
  ]) {
    testWidgets('$failure cash load stays unavailable instead of showing zero',
        (tester) async {
      await http.runWithClient(
        () async {
          await _pump(tester);
          await tester.pumpAndSettle();
          _expectUnavailable();
          expect(
            tester
                .widget<IconButton>(
                  find.byKey(const Key('collector-cash-status-refresh')),
                )
                .onPressed,
            isNotNull,
          );
        },
        () => MockClient((request) async {
          if (failure == 'offline') throw http.ClientException('Offline');
          if (failure == 'missing total') {
            return _response(_payload()..remove('total_cash_held'));
          }
          if (failure == 'invalid total') {
            return _response(_payload()..['assigned_area_cash_held'] = 'NaN');
          }
          return http.Response('{"detail":{"message":"Unavailable"}}',
              int.parse(failure));
        }),
      );
    });
  }

  testWidgets('failed refresh clears previous amounts and retry recovers',
      (tester) async {
    var calls = 0;
    final refresh = Completer<http.Response>();
    await http.runWithClient(
      () async {
        await _pump(tester);
        await tester.pumpAndSettle();
        _expectActualCash();

        await tester.tap(find.byKey(const Key('collector-cash-status-refresh')));
        await tester.pump();
        _expectNoCashAmounts();
        refresh.completeError(http.ClientException('Offline'));
        await tester.pumpAndSettle();
        _expectUnavailable();

        await tester.tap(find.byKey(const Key('collector-cash-status-refresh')));
        await tester.pumpAndSettle();
        _expectActualCash();
        expect(find.textContaining('Cash status unavailable'), findsNothing);
        expect(calls, 3);
      },
      () => MockClient((request) async {
        calls++;
        return calls == 2 ? refresh.future : _cashResponse();
      }),
    );
  });

  testWidgets('verified zero amounts still display as zero', (tester) async {
    await http.runWithClient(
      () async {
        await _pump(tester);
        await tester.pumpAndSettle();
        expect(find.text('₱0.00'), findsNWidgets(3));
        expect(find.textContaining('Cash status unavailable'), findsNothing);
      },
      () => MockClient((request) async => _cashResponse(zero: true)),
    );
  });

  for (final canLoadRenewals in <bool>[false, true]) {
    testWidgets(
        'no cash permission hides cash figures and avoids cash requests (renewals=$canLoadRenewals)',
        (tester) async {
      final paths = <String>[];
      await http.runWithClient(
        () async {
          await _pump(
            tester,
            permissions: <String>[
              if (canLoadRenewals) 'renewal.recommend.assigned',
            ],
          );
          await tester.pumpAndSettle();
          _expectNoCashAmounts();
          expect(find.text('Field cash'), findsNothing);
          expect(
            paths.where((path) => path.contains('cash-accountability')),
            isEmpty,
          );
          expect(paths.length, canLoadRenewals ? 1 : 0);
        },
        () => MockClient((request) async {
          paths.add(request.url.path);
          return _response(<String, Object?>{'requests': <Object?>[]});
        }),
      );
    });
  }

  testWidgets('renewal endpoint failure does not hide valid cash summary',
      (tester) async {
    await http.runWithClient(
      () async {
        await _pump(tester, permissions: <String>[
          'remittance.view',
          'renewal.recommend.assigned',
        ]);
        await tester.pumpAndSettle();
        _expectActualCash();
      },
      () => MockClient((request) async {
        if (request.url.path.endsWith('/cash-accountability')) {
          return _cashResponse();
        }
        throw http.ClientException('Renewals unavailable');
      }),
    );
  });
}

void _expectNoCashAmounts() {
  expect(find.byKey(const Key('collector-total-cash-held')), findsNothing);
  expect(find.textContaining('₱'), findsNothing);
}

void _expectUnavailable() {
  _expectNoCashAmounts();
  expect(find.textContaining('Cash status unavailable'), findsOneWidget);
}

void _expectActualCash() {
  expect(find.text('₱555.00'), findsOneWidget);
  expect(find.text('₱505.00'), findsOneWidget);
  expect(find.text('₱50.00'), findsOneWidget);
}

Future<void> _pump(
  WidgetTester tester, {
  DeviceIdentityProvider? identity,
  List<String> permissions = const <String>['remittance.view'],
}) async {
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(
      body: CollectorCashStatusCard(
        session: UserSession(
          userId: 'cash-test-collector',
          username: 'cash.test.collector',
          displayName: 'Cash Test Collector',
          role: AppRole.collector,
          rawRole: 'Collector',
          accessToken: 'test-token',
          permissions: permissions,
        ),
        deviceIdentityProvider: identity ?? _identity(),
        onOpenRemittance: () {},
        onOpenRenewals: () {},
        onOpenCashToReceive: () {},
        onOpenCashToClient: () {},
      ),
    ),
  ));
}

DeviceIdentityProvider _identity({bool fail = false}) => DeviceIdentityProvider(
      store: MemoryDeviceIdentityStore()..value = 'cash-test-device',
      platformResolver: () => 'android',
      appVersionResolver: () async {
        if (fail) throw StateError('Device identity unavailable');
        return '0.4.0+4';
      },
    );

http.Response _cashResponse({bool zero = false}) => _response(zero
    ? <String, Object?>{
        'total_cash_held': '0.00',
        'assigned_area_cash_held': 0,
        'other_area_cash_held': 0.0,
        'other_area_by_collector': <Object?>[],
        'ready_to_remit_amount': '0.00',
        'ready_to_remit_count': 0,
        'awaiting_acceptance_amount': '0.00',
        'awaiting_acceptance_count': 0,
      }
    : _payload());

Map<String, Object?> _payload() => <String, Object?>{
      'total_cash_held': '555.00',
      'assigned_area_cash_held': '505.00',
      'other_area_cash_held': '50.00',
      'other_area_by_collector': <Object?>[],
      'ready_to_remit_amount': '455.00',
      'ready_to_remit_count': 3,
      'awaiting_acceptance_amount': '100.00',
      'awaiting_acceptance_count': 1,
    };

http.Response _response(Map<String, Object?> payload) => http.Response(
      jsonEncode(<String, Object?>{'success': true, 'data': payload}),
      200,
      headers: const <String, String>{'content-type': 'application/json'},
    );
