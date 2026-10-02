import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_repository.dart';
import 'package:http/testing.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance_repository.dart';
import 'package:gilbic_mobile/src/core/notifications/remittance_notification_repository.dart';
import 'support/treasury_fixture.dart';

void main() {
  test(
    'explicit feature-off receiving permission preserves the ordinary full-reviewed handover',
    () async {
      var writes = 0;
      final repo = SpinaRemittanceRepository(
        client: MockClient((r) async {
          if (r.method == 'GET') {
            return jsonResponse({
              'collector_surplus_contract_version': 1,
              'remittance_id': event,
              'recipient_user_id': user,
              'count_required': false,
              'legacy_receive_allowed': true,
            });
          }
          writes++;
          expect(r.url.path, '/api/mobile/v1/remittances/$event/receive');
          return jsonResponse({
            'id': event,
            'remittance_number': 'Synthetic REM',
            'recipient_user_id': user,
            'collector_user_id': ledger,
            'status': 'received',
            'total_amount': '100.00',
          });
        }),
      );
      final result = await repo.confirmReceived(
        session(),
        deviceId: 'external',
        remittanceId: event,
      );
      expect(result.isReceived, isTrue);
      expect(writes, 1);
    },
  );
  test(
    'count-required or malformed gate cannot infer feature-off cash acceptance',
    () async {
      for (final gate in [
        {
          'collector_surplus_contract_version': 1,
          'remittance_id': event,
          'recipient_user_id': user,
          'count_required': true,
          'legacy_receive_allowed': false,
        },
        {
          'collector_surplus_contract_version': 1,
          'remittance_id': event,
          'recipient_user_id': ledger,
          'count_required': false,
          'legacy_receive_allowed': true,
        },
        {
          'collector_surplus_contract_version': 1,
          'remittance_id': event,
          'recipient_user_id': user,
          'count_required': false,
          'legacy_receive_allowed': false,
        },
      ]) {
        var writes = 0;
        final repo = SpinaRemittanceRepository(
          client: MockClient((r) async {
            if (r.method == 'POST') writes++;
            return jsonResponse(gate);
          }),
        );
        try {
          await repo.confirmReceived(
            session(),
            deviceId: 'external',
            remittanceId: event,
          );
          fail('Invalid gate must block');
        } catch (e) {
          expect(e, isNot(isA<TestFailure>()));
        }
        expect(writes, 0);
      }
    },
  );
  test(
    'observed return reversal has exact principal and original action identity',
    () {
      final command = TreasuryCommand(
        TreasuryAction.fromCode('collector_surplus_return_reverse'),
        requestId: requestId,
        accountId: account,
        expectedVersion: 1,
        fields: {
          'action_id': event,
          'action_version': 1,
          'amount': '10.00',
          'provider': 'gcash',
          'reference': 'Synthetic incoming reversal',
          'effective_at': '2026-10-02T00:00:00Z',
          'evidence_id': ledger,
          'recipient_attestation': 'Actual incoming return reviewed',
          'reason': 'Provider returned this principal',
        },
      );
      expect(command.toJson()['amount'], '10.00');
      expect(command.toJson()['action_id'], event);
    },
  );
  test(
    'ordinary and notification receiving cannot send a boolean count fallback',
    () async {
      var posts = 0;
      final client = MockClient((r) async {
        if (r.method == 'POST') posts++;
        return jsonResponse({
          'id': event,
          'remittance_id': event,
          'remittance_number': 'Synthetic',
          'status': 'received',
        });
      });
      try {
        await SpinaRemittanceRepository(
          client: client,
        ).confirmReceived(session(), deviceId: 'external', remittanceId: event);
      } catch (_) {}
      expect(posts, 0);
      try {
        await SpinaRemittanceNotificationRepository(
          client: client,
        ).acceptRemittance(
          session(),
          deviceId: 'external',
          notificationId: event,
        );
      } catch (_) {}
      expect(posts, 0);
    },
  );
  test('count retains exact zero and refuses inferred required cash', () {
    final action = TreasuryAction.fromCode('collector_count_record');
    final fields = {
      'remittance_id': event,
      'source_digest': 'a' * 64,
      'counted_amount': '0.00',
      'counted_at': '2026-10-02T08:00:00+08:00',
      'evidence_id': ledger,
      'recipient_attestation': 'Actual count reviewed',
      'review_acknowledged': true,
    };
    final value = TreasuryCommand(
      action,
      requestId: requestId,
      accountId: account,
      expectedVersion: 1,
      fields: fields,
    );
    expect(value.toJson()['counted_amount'], '0.00');
    expect(
      () => TreasuryCommand(
        action,
        requestId: requestId,
        accountId: account,
        expectedVersion: 1,
        fields: {...fields, 'required_amount': '0.00'},
      ),
      throwsFormatException,
    );
  });
  test('safe own workspace reads without private account grants', () async {
    final repo = SpinaTreasuryRepository(
      session: session(),
      deviceId: 'external',
      journal: MemoryTreasuryJournal(),
      client: MockClient((r) async {
        expect(r.url.path, '/api/v1/treasury/collector-surplus/workspace');
        return jsonResponse({
          'collector_surplus_contract_version': 1,
          'actor': {'user_id': user, 'device_id': device},
          'mode': 'own',
          'readiness': {
            'enabled': false,
            'treasury_ready': false,
            'application_enabled': false,
            'application_supported': false,
            'historical_correction_supported': false,
            'gl_supported': false,
            'blockers': [],
          },
          'capabilities': {'view': true},
          'accounts': [],
          'collector_choices': [],
          'kind': 'credits',
          'items': [],
          'total_count': 0,
          'totals': {},
          'has_more': false,
          'limit': 50,
          'offset': 0,
        });
      }),
    );
    final dynamic native = repo;
    final dynamic result = await native.loadCollectorSurplus();
    expect(result.mode, 'own');
    expect(result.accounts, isEmpty);
    expect(result.page.totalCount, 0);
    expect(repo.workspace, isNull);
    repo.dispose();
  });
  test('actual Collector return does not borrow a Client refund source', () {
    final result = TreasuryCommand(
      TreasuryAction.disbursementRecord,
      requestId: requestId,
      accountId: account,
      expectedVersion: 1,
      fields: {
        'amount': '40.00',
        'fee': '2.00',
        'provider': 'gcash',
        'reference': 'synthetic-return',
        'effective_at': '2026-10-02T08:00:00+08:00',
        'evidence_id': ledger,
        'recipient_attestation': 'Actual outgoing observed',
        'purpose': 'collector_surplus_return',
        'source_id': event,
        'source_version': 1,
        'payee_id': user,
        'reason': 'Partial Collector return',
      },
    );
    expect(result.toJson()['purpose'], 'collector_surplus_return');
  });
}
