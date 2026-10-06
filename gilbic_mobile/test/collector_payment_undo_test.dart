import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/collection_correction.dart';
import 'package:gilbic_mobile/src/core/payments/collection_payment_undo_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collection_payment_undo_page.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test(
    'route keeps explicit undo availability through offline serialization',
    () {
      final entry = CollectorRouteEntry.fromPayload({
        'id': 'loan-1',
        'client_id': 'client-1',
        'loan_id': 'loan-1',
        'client_name': 'Borrower',
        'loan_type': 'Regular',
        'can_undo_today': true,
      })!;
      expect(entry.toJson()['can_undo_today'], isTrue);
      final restored = CollectorRouteEntry.fromPayload(entry.toJson())!;
      expect(restored.toJson()['can_undo_today'], isTrue);
    },
  );

  test(
    'incomplete correction response cannot falsely report a zero balance',
    () {
      expect(
        () =>
            CollectionCorrectionResult.fromPayload({'transaction_id': 'tx-1'}),
        throwsA(isA<Exception>()),
      );
    },
  );

  for (final damage in [
    'none',
    'missing',
    'wrong receipt',
    'wrong loan',
    'old revision',
  ]) {
    test(
      'undo binds server confirmation to reviewed receipt: $damage',
      () async {
        var calls = 0;
        final repo = SpinaCollectionPaymentUndoRepository(
          client: MockClient((request) async {
            calls++;
            expect(request.method, 'POST');
            expect(
              request.url.path,
              '/api/mobile/v1/collector/collections/tx-1/undo-payment',
            );
            expect(request.headers['X-Device-Id'], 'device-1');
            expect(jsonDecode(request.body), {
              'reason': 'Mistaken tap',
              'expected_route_revision': 'loan:loan-1:v1',
            });
            final data = <String, Object?>{
              'transaction_id': 'tx-1',
              'loan_id': 'loan-1',
              'receipt_number': 'R1',
              'route_revision': 'loan:loan-1:v2',
              'restored_balance': '5000.00',
              'voided_at': '2026-10-06T01:00:00+08:00',
            };
            if (damage == 'missing') data.remove('restored_balance');
            if (damage == 'wrong receipt') data['transaction_id'] = 'tx-2';
            if (damage == 'wrong loan') data['loan_id'] = 'loan-2';
            if (damage == 'old revision') {
              data['route_revision'] = 'loan:loan-1:v1';
            }
            return http.Response(
              jsonEncode({'success': true, 'data': data}),
              200,
            );
          }),
        );
        final result = repo.undo(
          _session,
          deviceId: 'device-1',
          transactionId: 'tx-1',
          loanId: 'loan-1',
          expectedRouteRevision: 'loan:loan-1:v1',
          reason: 'Mistaken tap',
        );
        if (damage == 'none') {
          await result;
        } else {
          await expectLater(result, throwsA(isA<SpinaApiException>()));
        }
        expect(calls, 1);
      },
    );
  }

  testWidgets(
    'undo requires confirmation and prevents repeat taps during submission',
    (tester) async {
      final repo = _UndoRepository()..pending = Completer<void>();
      await _show(tester, repo);
      await tester.enterText(
        find.byKey(const Key('payment-undo-reason')),
        'Mistaken tap',
      );
      await tester.tap(find.byKey(const Key('submit-payment-undo')));
      await tester.pumpAndSettle();
      expect(repo.reasons, isEmpty);
      await tester.tap(find.byKey(const Key('confirm-payment-undo')));
      await tester.pumpAndSettle();
      expect(repo.reasons, ['Mistaken tap']);
      expect(
        tester
            .widget<FilledButton>(find.byKey(const Key('submit-payment-undo')))
            .onPressed,
        isNull,
      );
      repo.pending!.complete();
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('payment-undo-saved')), findsOneWidget);
      expect(
        find.textContaining('one missed-payment event (+1)'),
        findsOneWidget,
      );
      expect(repo.reasons.length, 1);
    },
  );

  testWidgets(
    'lost response freezes the reason and retries only the same undo',
    (tester) async {
      final repo = _UndoRepository()..fail = true;
      await _show(tester, repo);
      await tester.enterText(
        find.byKey(const Key('payment-undo-reason')),
        'Mistaken tap',
      );
      await tester.tap(find.byKey(const Key('submit-payment-undo')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-payment-undo')));
      await tester.pumpAndSettle();
      expect(find.text('Retry same undo'), findsOneWidget);
      expect(
        tester
            .widget<TextField>(find.byKey(const Key('payment-undo-reason')))
            .enabled,
        isFalse,
      );
      repo.fail = false;
      await tester.tap(find.byKey(const Key('submit-payment-undo')));
      await tester.pumpAndSettle();
      expect(repo.reasons, ['Mistaken tap', 'Mistaken tap']);
      expect(find.byKey(const Key('payment-undo-saved')), findsOneWidget);
    },
  );
}

const _session = UserSession(
  userId: 'collector',
  username: 'collector',
  displayName: 'Collector',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'test-token',
  permissions: ['collection.correct.own_unremitted'],
);

Future<void> _show(WidgetTester tester, _UndoRepository repo) async {
  await tester.binding.setSurfaceSize(const Size(430, 950));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  final store = MemoryDeviceIdentityStore()..value = 'device-1';
  await tester.pumpWidget(
    MaterialApp(
      home: CollectionPaymentUndoPage(
        session: _session,
        entry: const CollectorRouteEntry(
          id: 'loan-1',
          clientId: 'client-1',
          loanId: 'loan-1',
          clientName: 'Borrower',
          area: 'Area',
          loanType: 'Regular',
          dailyAmount: 50,
          balance: 4950,
          status: 'Paid today',
          passCount: 0,
          canUndoToday: true,
          canEditToday: false,
          todayTransactionId: 'tx-1',
          routeRevision: 'loan:loan-1:v1',
        ),
        repository: repo,
        deviceIdentityProvider: DeviceIdentityProvider(
          store: store,
          platformResolver: () => 'android',
          appVersionResolver: () async => 'test',
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

class _UndoRepository implements CollectionPaymentUndoRepository {
  final reasons = <String>[];
  bool fail = false;
  Completer<void>? pending;
  @override
  Future<void> undo(
    UserSession session, {
    required String deviceId,
    required String transactionId,
    required String loanId,
    required String expectedRouteRevision,
    required String reason,
  }) async {
    expect(transactionId, 'tx-1');
    expect(loanId, 'loan-1');
    expect(expectedRouteRevision, 'loan:loan-1:v1');
    reasons.add(reason);
    if (fail) {
      throw const SpinaApiException('Lost response', code: 'undo_unconfirmed');
    }
    await pending?.future;
  }
}
