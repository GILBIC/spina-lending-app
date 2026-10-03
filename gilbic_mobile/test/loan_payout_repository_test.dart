import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_repository.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/treasury_fixture.dart';

void main() {
  test(
    'native loan payout uses the unchanged preview and recovers one saved request after restart',
    () async {
      final w = workspace();
      (w['capabilities'] as Map)['loan_payout_prepare'] = true;
      (w['accounts'] as List).first['actions'] = ['loan_payout_prepare'];
      final input = <String, dynamic>{
        'account_id': account,
        'expected_version': 1,
        'source_kind': 'first_loan',
        'source_id': event,
        'destination': 'collector',
        'recipient_reference': 'Reviewed wallet',
        'authorization_id': event,
        'packet_hash': 'a' * 64,
        'contract_evidence_reference': 'office-evidence:$event',
      };
      final preview = {
        ...input,
        'contract_version': 1,
        'actor': w['actor'],
        'ledger_context_id': ledger,
        'account_version': 1,
        'payee_id': user,
        'client_id': event,
        'amount': '1000.00',
        'source_digest': 'b' * 64,
      };
      final saved = {
        ...outcome(action: 'loan_payout_prepare'),
        'version': 1,
        'result': {
          'actor_user_id': user,
          'device_id': device,
          'account_id': account,
          'ledger_context_id': ledger,
          'payout': {
            ...input,
            'id': event,
            'version': 1,
            'status': 'prepared',
            'amount': '1000.00',
            'source_digest': 'b' * 64,
          },
        },
      };
      int posts = 0;
      final journal = MemoryTreasuryJournal();
      final client = MockClient((request) async {
        if (request.url.path.endsWith('/workspace')) return jsonResponse(w);
        if (request.url.path.endsWith('/loan-payout-preview')) {
          return jsonResponse(preview);
        }
        if (request.url.path.contains('/requests/')) return jsonResponse(saved);
        posts++;
        throw http.ClientException('Lost response');
      });
      final repo = SpinaTreasuryRepository(
        session: session(),
        deviceId: 'synthetic-install',
        client: client,
        journal: journal,
      );
      await repo.loadWorkspace();
      await (repo as dynamic).loanPayoutPreview(input);
      final fields = {...input}
        ..remove('account_id')
        ..remove('expected_version');
      fields['source_digest'] = 'b' * 64;
      await expectLater(
        repo.execute(
          TreasuryCommand(
            TreasuryAction.loanPayoutPrepare,
            requestId: requestId,
            accountId: account,
            expectedVersion: 1,
            fields: fields,
          ),
        ),
        throwsA(isA<TreasuryUncertain>()),
      );
      expect(posts, 1);
      repo.dispose();
      final resumed = SpinaTreasuryRepository(
        session: session(),
        deviceId: 'synthetic-install',
        client: client,
        journal: journal,
      );
      await resumed.restoreAttempt();
      expect((await resumed.recover())!.targetId, event);
      expect(posts, 1);
      expect(resumed.pendingRequestId, isNull);
      resumed.dispose();
    },
  );
}
