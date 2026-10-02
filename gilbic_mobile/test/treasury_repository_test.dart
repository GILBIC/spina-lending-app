import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_repository.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'support/treasury_fixture.dart';

void main() {
  test(
    'owner observation without a reference remains unresolved; verification requires a reference',
    () {
      final rows =
          const TreasuryField(
                'rows',
                'Rows',
                TreasuryFieldKind.observations,
              ).parse([
                {
                  'id': event,
                  'provider': 'gcash',
                  'reference': null,
                  'direction': 'debit',
                  'amount': '20.01',
                  'effective_at': '2026-10-02T00:00:00Z',
                },
              ])
              as List;
      expect((rows.single as Map)['reference'], isNull);
      final verifyReference = treasuryFields[TreasuryAction.receiptVerify]!
          .firstWhere((f) => f.key == 'reference');
      expect(() => verifyReference.parse(null), throwsFormatException);
    },
  );
  test('exact money preserves adjacent values above double precision', () {
    expect(TreasuryMoney('90071992547409.91').text, '90071992547409.91');
    expect(TreasuryMoney('90071992547409.92').text, '90071992547409.92');
    for (final bad in [
      '01.00',
      '1',
      '1.0',
      '1e2',
      '-1.00',
      '10000000000000000.00',
    ]) {
      expect(() => TreasuryMoney(bad), throwsFormatException);
    }
  });
  test('workspace validates actor and unavailable is not zero', () {
    final value = TreasuryWorkspace.fromJson(workspace(), expectedUserId: user);
    expect(value.actor.deviceId, device);
    expect(value.accounts.single.balance!['expected_balance'], isNull);
    expect(
      TreasuryWorkspace.fromJson(
        workspace(private: false),
        expectedUserId: user,
      ).accounts.single.balance,
      isNull,
    );
    expect(
      () => TreasuryWorkspace.fromJson(workspace(), expectedUserId: event),
      throwsFormatException,
    );
  });
  test('command forbids spoofed fields and money numbers', () {
    expect(
      () => TreasuryCommand(
        TreasuryAction.movementClassify,
        requestId: requestId,
        accountId: account,
        expectedVersion: 1,
        fields: {
          'event_id': event,
          'event_version': 1,
          'classification': 'personal',
          'reason': 'reason',
          'actor_user_id': user,
        },
      ),
      throwsFormatException,
    );
    expect(command().toJson()['action'], 'movement_classify');
  });
  test(
    'scope current after async read; external device header never DB identity',
    () async {
      var current = session();
      var changed = false;
      final repo = SpinaTreasuryRepository(
        session: current,
        deviceId: 'gilbic-installation',
        getSession: () => current,
        journal: MemoryTreasuryJournal(),
        client: MockClient((r) async {
          expect(r.headers['X-Device-Id'], 'gilbic-installation');
          if (changed) {
            current = const UserSession(
              userId: event,
              username: 'other',
              displayName: 'Other',
              role: AppRole.client,
              rawRole: 'Client',
              accessToken: 'other',
            );
          }
          return jsonResponse(workspace());
        }),
      );
      expect((await repo.loadWorkspace()).actor.deviceId, device);
      changed = true;
      await expectLater(
        repo.loadWorkspace(),
        throwsA(isA<TreasuryAccessChanged>()),
      );
      expect(repo.workspace, isNull);
    },
  );
  test('offline no POST and delegated history is never requested', () async {
    var posts = 0;
    final repo = SpinaTreasuryRepository(
      session: session(),
      deviceId: 'external',
      isOnline: () => false,
      journal: MemoryTreasuryJournal(),
      client: MockClient((r) async {
        if (r.method == 'POST') posts++;
        return jsonResponse(workspace(private: false));
      }),
    );
    await repo.loadWorkspace();
    await expectLater(
      repo.execute(command(), targetId: event),
      throwsA(isA<StateError>()),
    );
    expect(posts, 0);
    await expectLater(
      repo.list(TreasuryListKind.events, accountId: account),
      throwsA(isA<TreasuryAccessChanged>()),
    );
  });
  test(
    'uncertain result remains exact across read null and restart; explicit retry only',
    () async {
      final journal = MemoryTreasuryJournal();
      var posts = 0;
      var fail = true;
      final sent = <String>[];
      final client = MockClient((r) async {
        if (r.url.path.endsWith('/workspace')) return jsonResponse(workspace());
        if (r.url.path.contains('/requests/')) return jsonResponse(null);
        posts++;
        sent.add(r.body);
        if (fail) throw http.ClientException('Synthetic disconnect');
        return jsonResponse(outcome());
      });
      var repo = SpinaTreasuryRepository(
        session: session(),
        deviceId: 'external',
        journal: journal,
        client: client,
      );
      await repo.loadWorkspace();
      await expectLater(
        repo.execute(command(), targetId: event),
        throwsA(isA<TreasuryUncertain>()),
      );
      expect(repo.pendingRequestId, requestId);
      await expectLater(
        repo.execute(command(), targetId: event),
        throwsStateError,
      );
      expect(await repo.recover(), isNull);
      expect(posts, 1);
      repo.dispose();
      repo = SpinaTreasuryRepository(
        session: session(),
        deviceId: 'external',
        journal: journal,
        client: client,
      );
      await repo.loadWorkspace();
      await repo.restoreAttempt();
      expect(repo.pendingRequestId, requestId);
      expect(posts, 1);
      fail = false;
      expect((await repo.retrySame()).status, 'saved');
      expect(posts, 2);
      expect(sent[1], sent[0]);
      expect(journal.value, isNull);
    },
  );
  test('wrong actor result never clears uncertain command', () async {
    final repo = SpinaTreasuryRepository(
      session: session(),
      deviceId: 'external',
      journal: MemoryTreasuryJournal(),
      client: MockClient(
        (r) async => jsonResponse(
          r.method == 'GET' ? workspace() : outcome(actor: event),
        ),
      ),
    );
    await repo.loadWorkspace();
    await expectLater(
      repo.execute(command(), targetId: event),
      throwsA(isA<TreasuryUncertain>()),
    );
    expect(repo.pendingRequestId, requestId);
  });
  test(
    'paged list rejects malformed paging instead of silent truncation',
    () async {
      final repo = SpinaTreasuryRepository(
        session: session(),
        deviceId: 'external',
        journal: MemoryTreasuryJournal(),
        client: MockClient(
          (r) async => jsonResponse(
            r.url.path.endsWith('/workspace')
                ? workspace()
                : {
                    'items': [],
                    'total_count': 200,
                    'limit': 50,
                    'offset': 0,
                    'has_more': false,
                    'totals': null,
                  },
          ),
        ),
      );
      await repo.loadWorkspace();
      await expectLater(
        repo.list(TreasuryListKind.claims),
        throwsFormatException,
      );
    },
  );
  test(
    'command target is bound even when caller does not supply a target hint',
    () async {
      final bad = outcome();
      bad['target_id'] = ledger;
      (bad['result'] as Map)['event'] = {'id': ledger, 'version': 2};
      final repo = SpinaTreasuryRepository(
        session: session(),
        deviceId: 'external',
        journal: MemoryTreasuryJournal(),
        client: MockClient(
          (r) async => jsonResponse(r.method == 'GET' ? workspace() : bad),
        ),
      );
      await repo.loadWorkspace();
      await expectLater(
        repo.execute(command()),
        throwsA(isA<TreasuryUncertain>()),
      );
      expect(repo.pendingRequestId, requestId);
    },
  );
  test(
    'version zero belongs to actual loan state only, not evidence/opening versions',
    () {
      expect(
        () => TreasuryCommand(
          TreasuryAction.openingActivate,
          requestId: requestId,
          accountId: account,
          expectedVersion: 1,
          fields: {
            'opening_id': event,
            'opening_version': 0,
            'confirmed': true,
            'reason': 'Synthetic',
          },
        ),
        throwsFormatException,
      );
      final apply = TreasuryCommand(
        TreasuryAction.receiptApply,
        requestId: requestId,
        accountId: account,
        expectedVersion: 1,
        fields: {
          'receipt_id': event,
          'digest': 'a' * 64,
          'mode': 'single',
          'total_amount': '20.00',
          'loans': [
            {'loan_id': ledger, 'expected_version': 0},
          ],
          'intent': 'extra_as_advance',
          'covered_dates': ['2026-10-02'],
          'effective_date': '2026-10-02',
        },
      );
      expect((apply.toJson()['loans'] as List).single['expected_version'], 0);
    },
  );
  test(
    'received amount and borrower exactly match verified receipt result',
    () async {
      final w = workspace();
      (w['capabilities'] as Map)['receipt_verify'] = true;
      ((w['accounts'] as List).single['actions'] as List).add('receipt_verify');
      final verify = TreasuryCommand(
        TreasuryAction.receiptVerify,
        requestId: requestId,
        accountId: account,
        expectedVersion: 1,
        fields: {
          'client_id': user,
          'amount': '90071992547409.91',
          'provider': 'gcash',
          'reference': 'Synthetic actual recipient transaction',
          'effective_at': '2026-10-02T00:00:00Z',
          'evidence_id': ledger,
          'recipient_attestation': 'Checked actual recipient history',
          'reason': 'Synthetic fixture',
        },
      );
      final wrong = outcome(action: 'receipt_verify');
      (wrong['result'] as Map).remove('event');
      (wrong['result'] as Map)['receipt'] = {
        'id': event,
        'version': 2,
        'client_id': user,
        'amount': '90071992547409.92',
      };
      final repo = SpinaTreasuryRepository(
        session: session(),
        deviceId: 'external',
        journal: MemoryTreasuryJournal(),
        client: MockClient(
          (r) async => jsonResponse(r.method == 'GET' ? w : wrong),
        ),
      );
      await repo.loadWorkspace();
      await expectLater(
        repo.execute(verify),
        throwsA(isA<TreasuryUncertain>()),
      );
      expect(repo.pendingRequestId, requestId);
    },
  );
}
