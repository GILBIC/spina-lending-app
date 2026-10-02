import 'package:gilbic_mobile/src/core/treasury/collector_surplus_models.dart';
import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_repository.dart';
import 'package:http/testing.dart';
import 'support/treasury_fixture.dart' as t;

void main() {
  test(
    'actual saved source-conflict fixture preserves debit and unpaid reservation with exact bound event',
    () {
      final examples =
          (jsonDecode(
                    File(
                      'test/support/collector_surplus_backend_examples.json',
                    ).readAsStringSync(),
                  )['examples']
                  as List)
              .cast<Map>();
      final sample = examples.singleWhere(
        (e) =>
            e['kind'] == 'disbursement_record' &&
            e['response']['data']['result']['source_link']['status'] ==
                'blocked',
      );
      final raw = treasuryObject(sample['response']['data']),
          detail = treasuryObject(raw['result']);
      final held = {
        'body': sample['command'],
        'actor_user_id': sample['actor']['user_id'],
        'device_id': sample['actor']['device_id'],
        'account_id': detail['account_id'],
        'ledger_context_id': detail['ledger_context_id'],
        'collector_source': detail['source_link']['action_record'],
      };
      validateCollectorDebitOutcome(TreasuryResult.fromJson(raw), held);
      expect(detail['source_link']['action_record']['status'], 'reserved');
      expect(detail['event']['classification'], 'verified_unclassified');
      detail['source_link']['observed_event_id'] = t.event;
      expect(
        () => validateCollectorDebitOutcome(TreasuryResult.fromJson(raw), held),
        throwsFormatException,
      );
    },
  );

  for (final wrong in [false, true]) {
    test(
      'real outgoing debit ${wrong ? 'rejects substituted reserved principal' : 'remains confirmation pending without certifying paid'}',
      () async {
        final examples =
            (jsonDecode(
                      File(
                        'test/support/collector_surplus_backend_examples.json',
                      ).readAsStringSync(),
                    )['examples']
                    as List)
                .cast<Map>();
        final sample = examples.singleWhere(
          (e) =>
              e['kind'] == 'disbursement_record' &&
              e['response']['data']['result']['source_link']['status'] ==
                  'confirmation_pending',
        );
        final body = Map<String, dynamic>.from(sample['command']);
        final result = Map<String, dynamic>.from(sample['response']['data']);
        final actor = sample['actor'] as Map;
        final session = UserSession(
          userId: actor['user_id'] as String,
          username: 'synthetic',
          displayName: 'Synthetic owner',
          role: AppRole.management,
          rawRole: 'Management',
          accessToken: 'synthetic',
          permissions: const ['treasury.view'],
        );
        final generic = t.workspace();
        generic['actor'] = actor;
        generic['capabilities'] = {'disbursement_record': true};
        final account = (generic['accounts'] as List).single as Map;
        account['id'] = body['account_id'];
        account['ledger_context_id'] = result['result']['ledger_context_id'];
        account['version'] = body['expected_version'];
        account['actions'] = ['disbursement_record'];
        final staff = examples.firstWhere(
          (e) => e['kind'] == 'staff-workspace-credits',
        )['response']['data'];
        final original = examples.singleWhere(
          (e) =>
              e['kind'] == 'collector_surplus_return_prepare' &&
              e['response']['data']['result']['action_record']['id'] ==
                  body['source_id'],
        )['response']['data']['result']['action_record'];
        if (wrong) {
          result['result']['source_link']['action_record']['amount'] = '0.01';
        }
        final repo = SpinaTreasuryRepository(
          session: session,
          deviceId: 'external',
          journal: MemoryTreasuryJournal(),
          client: MockClient((r) async {
            if (r.url.path.endsWith('/collector-surplus/workspace')) {
              return t.jsonResponse(staff);
            }
            if (r.url.path.endsWith('/workspace')) {
              return t.jsonResponse(generic);
            }
            if (r.url.path.contains('/collector-surplus/actions/')) {
              return t.jsonResponse(original);
            }
            expect(r.method, 'POST');
            expect(
              jsonDecode(r.body),
              Map<String, dynamic>.from(body)..removeWhere((k, v) => v == null),
            );
            return t.jsonResponse(result);
          }),
        );
        final fields = Map<String, dynamic>.from(body)
          ..remove('action')
          ..remove('request_id')
          ..remove('account_id')
          ..remove('expected_version');
        final command = TreasuryCommand(
          TreasuryAction.disbursementRecord,
          requestId: body['request_id'] as String,
          accountId: body['account_id'] as String,
          expectedVersion: body['expected_version'] as int,
          fields: fields,
        );
        if (wrong) {
          await expectLater(
            repo.execute(command),
            throwsA(isA<TreasuryUncertain>()),
          );
          expect(repo.pendingRequestId, body['request_id']);
        } else {
          final value = await repo.execute(command);
          expect(
            value.result['source_link']['disposition'],
            'return_debited_confirmation_pending',
          );
          expect(repo.pendingRequestId, isNull);
        }
        repo.dispose();
      },
    );
  }
}
