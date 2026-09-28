import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_repository.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collector_cash_status_card.dart';
import 'package:gilbic_mobile/src/features/collector/collector_cash_to_client_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_cash_to_receive_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_field_home_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_renewal_cash_release_page.dart';
import 'package:gilbic_mobile/src/features/collector/collector_renewal_requests_page.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const _recommend = 'renewal.recommend.assigned';
const _custody = 'renewal.cash_custody.assigned';

void main() {
  for (final permission in <String?>[null, _recommend, _custody]) {
    for (final destination in <String>['requests', 'receive', 'give']) {
      testWidgets('$permission renewal navigation: $destination', (
        tester,
      ) async {
        final reads = <String>[];
        await http.runWithClient(
          () async {
            await tester.pumpWidget(
              MaterialApp(
                home: CollectorFieldHomePage(
                  session: _session(permission),
                  onSignOut: () async {},
                  collectorRouteLoader: _EmptyRoute(),
                  paymentSubmissionRepository:
                      SpinaPaymentSubmissionRepository(),
                  deviceIdentityProvider: _device(),
                  collectionDeviceSequence: MemoryCollectionDeviceSequence(),
                ),
              ),
            );
            await tester.pumpAndSettle();
            final card = tester.widget<CollectorCashStatusCard>(
              find.byType(CollectorCashStatusCard),
            );
            final Type expectedType;
            switch (destination) {
              case 'requests':
                card.onOpenRenewals();
                expectedType = CollectorRenewalRequestsPage;
              case 'receive':
                card.onOpenCashToReceive();
                expectedType = CollectorCashToReceivePage;
              default:
                card.onOpenCashToClient();
                expectedType = CollectorCashToClientPage;
            }
            await tester.pumpAndSettle();
            expect(
              find.byType(expectedType),
              permission == null ? findsNothing : findsOneWidget,
            );
            if (permission == null) {
              expect(reads, isEmpty);
              expect(find.textContaining('does not allow'), findsOneWidget);
            } else {
              expect(
                reads.where((path) => path.contains('renewal')),
                hasLength(2),
              );
              expect(find.textContaining('does not allow'), findsNothing);
            }
            expect(tester.takeException(), isNull);
          },
          () => MockClient((request) async {
            expect(request.method, 'GET');
            reads.add(request.url.path);
            return _json({'requests': <Object?>[]});
          }),
        );
      });
    }
  }

  for (final permission in <String>[_recommend, _custody]) {
    for (final stage in <String>['pending', 'receive', 'give', 'proof']) {
      testWidgets('$permission gets only its $stage renewal action', (
        tester,
      ) async {
        await tester.binding.setSurfaceSize(const Size(1000, 1800));
        addTearDown(() => tester.binding.setSurfaceSize(null));
        var reads = 0;
        final repository = SpinaCollectorRenewalWorkflowRepository(
          client: MockClient((request) async {
            expect(request.method, 'GET');
            reads++;
            return _json({
              'requests': [_request(stage)],
            });
          }),
        );
        await tester.pumpWidget(
          MaterialApp(
            home: CollectorRenewalRequestsPage(
              session: _session(permission),
              deviceIdentityProvider: _device(),
              repository: repository,
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(reads, 1);
        expect(find.text('Borrower'), findsOneWidget);
        expect(
          find.byKey(const Key('renewal-recommend-renewal-1')),
          stage == 'pending' && permission == _recommend
              ? findsOneWidget
              : findsNothing,
        );
        expect(
          find.byKey(const Key('renewal-do-not-recommend-renewal-1')),
          stage == 'pending' && permission == _recommend
              ? findsOneWidget
              : findsNothing,
        );
        for (final action in <String, String>{
          'receive': 'cash-received',
          'give': 'cash-given',
          'proof': 'proof',
        }.entries) {
          expect(
            find.byKey(Key('renewal-${action.value}-renewal-1')),
            stage == action.key && permission == _custody
                ? findsOneWidget
                : findsNothing,
          );
        }
        expect(tester.takeException(), isNull);
      });
    }

    testWidgets('$permission release confirmation requires cash custody', (
      tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          home: CollectorRenewalCashReleasePage(
            session: _session(permission),
            deviceIdentityProvider: _device(),
            request: CollectorRenewalRequest.fromPayload(_request('receive')),
          ),
        ),
      );
      await tester.pumpAndSettle();
      final button = tester.widget<FilledButton>(
        find.byKey(const Key('cash-release-confirm-received')),
      );
      expect(button.onPressed, permission == _custody ? isNotNull : isNull);
      expect(tester.takeException(), isNull);
    });

    for (final stage in <String>['give', 'proof']) {
      testWidgets('$permission cash queue $stage requires cash custody', (
        tester,
      ) async {
        final repository = SpinaCollectorRenewalWorkflowRepository(
          client: MockClient((request) async {
            expect(request.method, 'GET');
            return _json({
              'requests': [_request(stage)],
            });
          }),
        );
        await tester.pumpWidget(
          MaterialApp(
            home: CollectorCashToClientPage(
              session: _session(permission),
              deviceIdentityProvider: _device(),
              repository: repository,
              routeRepository: _EmptyRoute(),
            ),
          ),
        );
        await tester.pumpAndSettle();
        final key = Key(
          'cash-to-client-${stage == 'give' ? 'confirm' : 'proof'}-renewal-1',
        );
        final button = tester.widget<ButtonStyleButton>(find.byKey(key));
        expect(button.onPressed, permission == _custody ? isNotNull : isNull);
        expect(tester.takeException(), isNull);
      });
    }
  }
}

UserSession _session(String? permission) => UserSession(
  userId: 'collector',
  username: 'collector',
  displayName: 'Collector',
  role: AppRole.collector,
  rawRole: 'collector',
  accessToken: 'test-token',
  permissions: <String>[if (permission != null) permission],
);

DeviceIdentityProvider _device() => DeviceIdentityProvider(
  store: MemoryDeviceIdentityStore()..value = 'device',
  platformResolver: () => 'android',
  appVersionResolver: () async => 'test',
);

http.Response _json(Object value) => http.Response(
  jsonEncode(value),
  200,
  headers: {'content-type': 'application/json'},
);

class _EmptyRoute implements CollectorRouteLoader, CollectorRouteRepository {
  @override
  Future<CollectorRoute> fetchToday(UserSession session) async =>
      const CollectorRoute(
        routeDate: null,
        collectorName: 'Collector',
        areas: <String>[],
        entries: <CollectorRouteEntry>[],
        expectedTotal: 0,
      );

  @override
  Future<CollectorRouteLoadResult> loadToday(UserSession session) async =>
      CollectorRouteLoadResult(
        route: await fetchToday(session),
        syncedAt: DateTime.utc(2026, 9, 28),
        isFromCache: false,
      );
}

Map<String, dynamic> _request(String stage) => <String, dynamic>{
  'request_id': 'renewal-1',
  'client_id': 'client-1',
  'client_code': 'C1',
  'client_name': 'Borrower',
  'area': 'Area',
  'loan_id': 'loan-1',
  'loan_number': 'LN-1',
  'loan_type_name': 'Regular',
  'current_principal': '1000.00',
  'remaining_balance': '100.00',
  'contractual_total': '1100.00',
  'paid_cash': '1000.00',
  'paid_percent': '90.00',
  'requested_amount': '1000.00',
  'status': stage == 'pending' ? 'pending' : 'approved',
  'submitted_at': '2026-09-20T00:00:00Z',
  'signer_readiness_status': 'ready',
  'handover_proof_status': 'missing',
  'activation_status': 'pending',
  'amount_locked_at': '2026-09-20T01:00:00Z',
  'net_release_amount': '900.00',
  if (stage != 'pending')
    'cash_released_to_collector_at': '2026-09-20T02:00:00Z',
  if (stage == 'give' || stage == 'proof')
    'collector_cash_received_at': '2026-09-20T03:00:00Z',
  if (stage == 'proof') 'cash_given_to_client_at': '2026-09-20T04:00:00Z',
};
