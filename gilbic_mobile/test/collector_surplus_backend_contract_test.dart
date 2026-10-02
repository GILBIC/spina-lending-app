import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/treasury/collector_surplus_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';

void main() {
  final fixture =
      jsonDecode(
            File(
              'test/support/collector_surplus_backend_examples.json',
            ).readAsStringSync(),
          )
          as Map;
  final examples = (fixture['examples'] as List).cast<Map>();
  final records = <String, Map<String, dynamic>>{};
  test(
    'real disposable backend lifecycle envelopes validate without fabricated rows',
    () {
      expect(fixture['synthetic_only'], true);
      var validated = 0;
      for (final example in examples) {
        if (example['command'] is! Map) continue;
        final body = treasuryObject(example['command']);
        final action = TreasuryAction.values.singleWhere(
          (a) => a.code == body['action'],
        );
        if (!isCollectorSurplusAction(action)) continue;
        final fields = Map<String, dynamic>.from(body)
          ..remove('action')
          ..remove('request_id')
          ..remove('account_id')
          ..remove('expected_version');
        final command = TreasuryCommand(
          action,
          requestId: body['request_id'] as String,
          accountId: body['account_id'] as String?,
          expectedVersion: body['expected_version'] as int?,
          fields: fields,
        );
        expect(command.action, action);
        final result = treasuryObject(example['response']['data']);
        final detail = treasuryObject(result['result']);
        final snapshots = <String, dynamic>{};
        for (final slot in [
          'count',
          'case',
          'credit',
          'exception',
          'action_record',
          'request',
          'opening_anchor',
        ]) {
          final bodyKey = switch (slot) {
            'action_record' => 'action_id',
            'request' => 'collector_request_id',
            'opening_anchor' => 'anchor_id',
            _ => '${slot}_id',
          };
          if (body[bodyKey] != null && records[body[bodyKey]] != null) {
            snapshots[slot] = records[body[bodyKey]];
          }
        }
        final held = {
          'request_id': body['request_id'],
          'action': action.code,
          'actor_user_id': example['actor']['user_id'],
          'device_id': example['actor']['device_id'],
          'account_id': detail['account_id'],
          'ledger_context_id': detail['ledger_context_id'],
          'surplus_mode': collectorOwnActions.contains(action)
              ? 'own'
              : 'staff',
          'body': body,
          'surplus_records': snapshots,
        };
        final accepted = validateCollectorOutcome(result, held);
        expect(
          accepted.raw['target_id'],
          result['target_id'],
          reason: action.code,
        );
        for (final slot in [
          'count',
          'case',
          'credit',
          'exception',
          'action_record',
          'request',
          'opening_anchor',
        ]) {
          if (detail[slot] is Map) {
            final row = treasuryObject(detail[slot]);
            records[row['id'] as String] = row;
          }
        }
        validated++;
      }
      expect(validated, 16);
    },
  );
  for (final example in examples.where(
    (e) => (e['kind'] as String).contains('workspace'),
  )) {
    test('actual backend ${example['kind']} retains exact safe scope', () {
      final data = treasuryObject(example['response']['data']);
      final kind = CollectorSurplusKind.values.byName(data['kind'] as String);
      final workspace = CollectorSurplusWorkspace(
        data,
        expectedUserId: example['actor']['user_id'] as String,
        kind: kind,
        limit: data['limit'] as int,
        offset: data['offset'] as int,
      );
      expect(
        workspace.mode,
        (example['kind'] as String).startsWith('own') ? 'own' : 'staff',
      );
    });
  }
  test(
    'actual protected preview includes complete digest basis and no inferred count',
    () {
      final e = examples.singleWhere((e) => e['kind'] == 'preview');
      final data = treasuryObject(e['response']['data']);
      final staff = treasuryObject(
        examples.firstWhere(
          (e) => e['kind'] == 'staff-workspace-credits',
        )['response']['data'],
      );
      final account = CollectorSurplusAccount({
        ...treasuryObject(
          (staff['accounts'] as List).singleWhere(
            (a) => a['id'] == data['account_id'],
          ),
        ),
        'version': data['account_version'],
      });
      final preview = CollectorSettlementPreview(
        data,
        userId: e['actor']['user_id'] as String,
        deviceId: e['actor']['device_id'] as String,
        remittanceId: data['remittance_id'] as String,
        account: account,
      );
      expect(preview.raw['source_items'], isA<List>());
      expect(preview.raw['source_snapshot'], isA<Map>());
      expect(preview.canCount, true);
    },
  );
}
