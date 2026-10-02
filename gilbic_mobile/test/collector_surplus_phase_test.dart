import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/treasury/collector_surplus_models.dart';
import 'support/collector_surplus_fixture.dart';
import 'support/treasury_fixture.dart' as t;

Map<String, dynamic> held(
  String action,
  Map<String, dynamic> body,
  Map<String, dynamic> snapshots,
) => {
  'request_id': t.requestId,
  'action': action,
  'actor_user_id': t.user,
  'device_id': t.device,
  'account_id': t.account,
  'ledger_context_id': t.ledger,
  'surplus_mode': 'staff',
  'body': body,
  'surplus_records': snapshots,
};
void main() {
  test(
    'zero cash PASS accepts no physical event, positive cash requires actual UUID',
    () {
      final count = surplusCountRow()
        ..['counted_amount'] = '0.00'
        ..['physical_cash_required'] = '0.00'
        ..['gross_obligation'] = '0.00'
        ..['difference'] = '0.00';
      final settlement = {
        'id': surplusAction,
        'version': 1,
        'account_id': t.account,
        'ledger_context_id': t.ledger,
        'count_id': surplusCount,
        'remittance_id': surplusRemittance,
        'collector_user_id': surplusCollector,
        'recipient_user_id': t.user,
        'physical_amount': '0.00',
        'authorized_credit_amount': '0.00',
        'gross_obligation': '0.00',
        'event_id': null,
      };
      final outcome = surplusOutcome(
        action: 'collector_count_accept',
        slot: 'settlement',
        principal: settlement,
        disposition: 'accepted_exact',
        extra: {'count': count},
      );
      final attempt = held(
        'collector_count_accept',
        {'count_id': surplusCount},
        {'count': count},
      );
      expect(validateCollectorOutcome(outcome, attempt).status, 'saved');
      count['counted_amount'] = '1.00';
      settlement['physical_amount'] = '1.00';
      settlement['event_id'] = 'not-an-event';
      expect(
        () => validateCollectorOutcome(outcome, attempt),
        throwsFormatException,
      );
    },
  );
  test(
    'reversal preserves reviewed reservation and binds incoming observation at equivalent instant',
    () {
      final original = surplusActionRow(own: false, status: 'paid');
      final returned = {
        ...original,
        'version': 3,
        'status': 'partly_reversed',
        'reversed_amount': '10.00',
      };
      final body = {
        'action_id': surplusAction,
        'amount': '10.00',
        'provider': 'physical_cash',
        'reference': 'Actual reversal',
        'effective_at': '2026-10-02T08:00:00+08:00',
        'evidence_id': t.event,
      };
      final event = {
        'id': surplusAck,
        'version': 1,
        'account_id': t.account,
        'ledger_context_id': t.ledger,
        'amount': '10.00',
        'direction': 'credit',
        'provider': 'physical_cash',
        'reference': 'Actual reversal',
        'effective_at': '2026-10-02T00:00:00Z',
        'evidence_id': t.event,
      };
      final outcome = surplusOutcome(
        action: 'collector_surplus_return_reverse',
        slot: 'action_record',
        principal: returned,
        disposition: 'return_reversed',
        extra: {'incoming_event': event},
      );
      final attempt = held('collector_surplus_return_reverse', body, {
        'action_record': original,
      });
      expect(validateCollectorOutcome(outcome, attempt).status, 'saved');
      event['effective_at'] = '2026-10-03T00:00:00Z';
      expect(
        () => validateCollectorOutcome(outcome, attempt),
        throwsFormatException,
      );
    },
  );
  test('nested returned phase cannot substitute another account context', () {
    final credit = surplusCredit(own: false);
    final request = {
      'id': surplusRequest,
      'version': 1,
      'collector_user_id': surplusCollector,
      'ledger_context_id': t.ledger,
      'account_id': t.account,
      'amount': '40.00',
      'status': 'requested',
    };
    final outcome = surplusOutcome(
      action: 'collector_surplus_return_request',
      slot: 'request',
      principal: request,
      disposition: 'requested',
      extra: {'credit': credit},
    );
    final attempt = held(
      'collector_surplus_return_request',
      {'amount': '40.00'},
      {'credit': credit},
    );
    expect(validateCollectorOutcome(outcome, attempt).status, 'saved');
    credit['ledger_context_id'] = surplusAck;
    expect(
      () => validateCollectorOutcome(outcome, attempt),
      throwsFormatException,
    );
  });
}
