import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow.dart';
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

  for (final cashFails in <bool>[false, true]) {
    testWidgets(
        'pending renewal does not block cash ${cashFails ? 'unavailability' : 'success'} or refresh',
        (tester) async {
      final renewal = Completer<http.Response>();
      final alerts = <String>[];
      var cashRequests = 0;
      var renewalRequests = 0;
      await http.runWithClient(
        () async {
          await _pump(
            tester,
            permissions: _cashAndRenewalPermissions,
            onCashReleaseAlert: (request) => alerts.add(request.requestId),
          );
          await tester.pump();
          if (cashFails) {
            _expectUnavailable();
          } else {
            _expectActualCash();
          }
          expect(renewalRequests, 1);
          expect(alerts, isEmpty);
          expect(
            tester
                .widget<IconButton>(
                  find.byKey(const Key('collector-cash-status-refresh')),
                )
                .onPressed,
            isNotNull,
          );

          await tester.tap(find.byKey(const Key('collector-cash-status-refresh')));
          await tester.pumpAndSettle();
          expect(find.text('₱0.00'), findsNWidgets(3));
          expect(cashRequests, 2);
          expect(renewalRequests, 1);

          renewal.complete(_renewalResponse());
          await tester.pumpAndSettle();
          expect(alerts, <String>['release-1']);
          expect(find.text('₱0.00'), findsNWidgets(3));
        },
        () => MockClient((request) async {
          if (request.url.path.endsWith('/cash-accountability')) {
            cashRequests++;
            if (cashFails && cashRequests == 1) {
              throw http.ClientException('Cash unavailable');
            }
            return _cashResponse(zero: cashRequests > 1);
          }
          renewalRequests++;
          return renewal.future;
        }),
      );
    });
  }

  testWidgets('failed optional renewal can be checked again on cash refresh',
      (tester) async {
    final renewal = Completer<http.Response>();
    final alerts = <String>[];
    var renewalRequests = 0;
    await http.runWithClient(
      () async {
        await _pump(
          tester,
          permissions: _cashAndRenewalPermissions,
          onCashReleaseAlert: (request) => alerts.add(request.requestId),
        );
        await tester.pump();
        _expectActualCash();
        renewal.completeError(http.ClientException('Renewals unavailable'));
        await tester.pumpAndSettle();
        expect(alerts, isEmpty);
        _expectActualCash();

        await tester.tap(find.byKey(const Key('collector-cash-status-refresh')));
        await tester.pumpAndSettle();
        expect(renewalRequests, 2);
        expect(alerts, <String>['release-1']);
        _expectActualCash();
      },
      () => MockClient((request) async {
        if (request.url.path.endsWith('/cash-accountability')) {
          return _cashResponse();
        }
        renewalRequests++;
        return renewalRequests == 1 ? renewal.future : _renewalResponse();
      }),
    );
  });

  testWidgets('disposed card ignores a delayed renewal alert', (tester) async {
    final renewal = Completer<http.Response>();
    final alerts = <String>[];
    await http.runWithClient(
      () async {
        await _pump(
          tester,
          permissions: _cashAndRenewalPermissions,
          onCashReleaseAlert: (request) => alerts.add(request.requestId),
        );
        await tester.pump();
        await tester.pumpWidget(const SizedBox.shrink());
        renewal.complete(_renewalResponse());
        await tester.pumpAndSettle();
        expect(alerts, isEmpty);
        expect(tester.takeException(), isNull);
      },
      () => MockClient((request) async =>
          request.url.path.endsWith('/cash-accountability')
              ? _cashResponse()
              : renewal.future),
    );
  });

  testWidgets('renewal-only permission still delivers the release alert',
      (tester) async {
    final alerts = <String>[];
    await http.runWithClient(
      () async {
        await _pump(
          tester,
          permissions: <String>['renewal.recommend.assigned'],
          onCashReleaseAlert: (request) => alerts.add(request.requestId),
        );
        await tester.pumpAndSettle();
        expect(alerts, <String>['release-1']);
        _expectNoCashAmounts();
      },
      () => MockClient((request) async {
        expect(request.url.path, isNot(endsWith('/cash-accountability')));
        return _renewalResponse();
      }),
    );
  });
}

const _cashAndRenewalPermissions = <String>[
  'remittance.view',
  'renewal.recommend.assigned',
];

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
  ValueChanged<CollectorRenewalRequest>? onCashReleaseAlert,
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
        onCashReleaseAlert: onCashReleaseAlert,
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

http.Response _renewalResponse() => _response(<String, Object?>{
      'requests': <Object?>[
        <String, Object?>{
          'request_id': 'release-1',
          'client_id': 'renewal-client',
          'client_code': 'TEST-1',
          'client_name': 'Test Renewal Client',
          'area': 'Test Area',
          'loan_id': 'renewal-loan',
          'loan_number': 'TEST-LOAN-1',
          'loan_type_name': 'Regular',
          'is_7x7': false,
          'current_principal': '1000.00',
          'remaining_balance': '100.00',
          'contractual_total': '1200.00',
          'paid_cash': '1100.00',
          'paid_percent': '91.67',
          'regular_50_percent_eligible': true,
          'requested_amount': '1000.00',
          'client_message': '',
          'status': 'approved',
          'submitted_at': '2026-09-20T01:00:00Z',
          'collector_recommendation': 'recommend',
          'collector_reason_code': '',
          'collector_comment': '',
          'recommended_at': '2026-09-20T02:00:00Z',
          'approved_principal': '1000.00',
          'review_note': '',
          'management_override_reason': '',
          'reviewed_at': '2026-09-20T03:00:00Z',
          'client_decision': 'accepted',
          'client_decided_at': '2026-09-20T04:00:00Z',
          'signer_readiness_status': 'complete',
          'office_processing_required': false,
          'signers': <Object?>[],
          'renewal_offset_amount': '100.00',
          'net_release_amount': '900.00',
          'amount_locked_at': '2026-09-20T05:00:00Z',
          'cash_released_to_collector_at': '2026-09-20T06:00:00Z',
          'collector_cash_received_at': null,
          'cash_given_to_client_at': null,
          'client_cash_confirmed_at': null,
          'handover_proof_status': 'pending',
          'activation_status': 'pending',
          'new_loan_id': null,
          'ready_for_activation': false,
        },
      ],
    });
