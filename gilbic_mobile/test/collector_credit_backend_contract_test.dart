import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/treasury/collector_surplus_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';

void main() {
  test(
    'actual credit approval, count and acceptance satisfy the complete mobile contract',
    () {
      final fixture =
          jsonDecode(
                File(
                  'test/support/collector_credit_backend_examples.json',
                ).readAsStringSync(),
              )
              as Map;
      expect(fixture['synthetic_only'], true);
      expect(fixture['examples'], hasLength(6));
      for (final e in fixture['examples'] as List) {
        final body = treasuryObject(e['command']);
        final fields = Map<String, dynamic>.from(body)
          ..remove('action')
          ..remove('request_id')
          ..remove('account_id')
          ..remove('expected_version');
        final command = TreasuryCommand(
          TreasuryAction.fromCode(body['action']),
          requestId: body['request_id'],
          accountId: body['account_id'],
          expectedVersion: body['expected_version'],
          fields: fields,
        );
        expect(command.action.code, body['action']);
        final held = <String, dynamic>{
          'body': body,
          'action': body['action'],
          'request_id': body['request_id'],
          'actor_user_id': e['actor']['user_id'],
          'device_id': e['actor']['device_id'],
          'account_id': e['account_id'],
          'ledger_context_id': e['ledger_context_id'],
          'surplus_mode': 'staff',
          'surplus_records': e['records'],
        };
        expect(validateCollectorOutcome(e['response'], held).status, 'saved');
        if (body['action'] == 'collector_count_accept') {
          for (final change in <void Function(Map)>[
            (r) => r['result']['application_entry']['amount'] = '1.00',
            (r) => r['result']['settlement']['physical_amount'] = '1.00',
            (r) => r['result']['action_record']['status'] = 'reserved',
            (r) => r['result']['count']['credit_application']['version']++,
          ]) {
            final bad = jsonDecode(jsonEncode(e['response'])) as Map;
            change(bad);
            expect(
              () => validateCollectorOutcome(bad, held),
              throwsFormatException,
            );
          }
        }
      }
    },
  );
}
