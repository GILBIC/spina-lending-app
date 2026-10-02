import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'support/treasury_fixture.dart' as t;

void main() {
  test(
    'all 17 native surplus command families serialize the frozen backend schema',
    () async {
      final schema =
          jsonDecode(
                await File(
                  '../docs/operations/collector-surplus-command-schema.json',
                ).readAsString(),
              )
              as Map;
      final defs = schema[r'$defs'] as Map;
      final bodies = <Map<String, dynamic>>[];
      for (final action in TreasuryAction.values.where(
        isCollectorSurplusAction,
      )) {
        final fields = <String, dynamic>{};
        for (final f in treasuryFields[action]!) {
          if (!f.required) continue;
          fields[f.key] = switch (f.kind) {
            TreasuryFieldKind.id => t.event,
            TreasuryFieldKind.integer => 1,
            TreasuryFieldKind.money ||
            TreasuryFieldKind.positiveMoney => '40.00',
            TreasuryFieldKind.digest => 'a' * 64,
            TreasuryFieldKind.instant => '2026-10-02T00:00:00+08:00',
            TreasuryFieldKind.boolean => true,
            TreasuryFieldKind.choice => f.choices.first,
            TreasuryFieldKind.destination => {
              'kind': 'physical_cash',
              'recipient_reference': null,
            },
            _ => 'Synthetic controlled observation',
          };
        }
        if (action == TreasuryAction.collectorSurplusResolveSource) {
          fields.addAll({'case_id': t.event, 'case_version': 1});
        }
        final own = collectorOwnActions.contains(action);
        final body = TreasuryCommand(
          action,
          requestId: t.requestId,
          accountId: own ? null : t.account,
          expectedVersion: own ? null : 1,
          fields: fields,
        ).toJson();
        final definition = defs.values.whereType<Map>().singleWhere(
          (d) =>
              d['properties'] is Map &&
              d['properties']['action'] is Map &&
              d['properties']['action']['const'] == action.code,
        );
        final properties = definition['properties'] as Map;
        expect(
          body.keys.where((k) => !properties.containsKey(k)),
          isEmpty,
          reason: action.code,
        );
        expect(
          (definition['required'] as List).where((k) => !body.containsKey(k)),
          isEmpty,
          reason: action.code,
        );
        expect(body.containsKey('account_id'), !own);
        bodies.add(body);
      }
      expect(bodies.length, 17);
      final output = Platform.environment['SPINA_SURPLUS_CONTRACT_OUTPUT'];
      if (output != null) {
        await File(output).writeAsString(
          jsonEncode({'contract_version': 1, 'commands': bodies}),
        );
      }
    },
  );
}
