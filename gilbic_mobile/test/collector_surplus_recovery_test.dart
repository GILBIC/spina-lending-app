import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/treasury/collector_surplus_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_repository.dart';
import 'package:http/testing.dart';
import 'support/treasury_fixture.dart' as t;
import 'support/collector_surplus_fixture.dart';

TreasuryCommand ownReturn() => TreasuryCommand(
  TreasuryAction.collectorSurplusReturnRequest,
  requestId: t.requestId,
  fields: {
    'credit_id': t.event,
    'credit_version': 1,
    'amount': '40.00',
    'destination': {'kind': 'physical_cash', 'recipient_reference': null},
    'reason': 'Partial return requested',
  },
);
Map<String, dynamic> requestRow() => {
  'id': surplusRequest,
  'version': 1,
  'kind': 'return',
  'credit_id': t.event,
  'collector_user_id': t.user,
  'account_id': t.account,
  'ledger_context_id': t.ledger,
  'amount': '40.00',
  'destination': {'kind': 'physical_cash', 'recipient_reference': null},
  'remittance_id': null,
  'source_digest': null,
  'status': 'requested',
  'created_at': '2026-10-02T00:00:00Z',
};
void main() {
  test(
    'multi-role own detail and private export retain explicit own scope',
    () async {
      final repo = SpinaTreasuryRepository(
        session: t.session(),
        deviceId: 'external',
        journal: MemoryTreasuryJournal(),
        client: MockClient((r) async {
          expect(r.url.queryParameters['mode'], 'own');
          if (r.url.path.contains('/credits/')) {
            return t.jsonResponse(surplusCredit());
          }
          return t.jsonResponse(surplusWorkspace(rows: [surplusCredit()]));
        }),
      );
      await repo.loadCollectorSurplus(mode: 'own');
      final record = await repo.collectorSurplusDetail(
        CollectorSurplusKind.credits,
        t.event,
      );
      expect(record['collector_user_id'], t.user);
      final exported = await repo.exportCollectorSurplus();
      expect(jsonDecode(utf8.decode(exported.bytes))['data']['mode'], 'own');
      repo.dispose();
    },
  );

  test(
    'incomplete linked credit cannot unlock an otherwise valid intent result',
    () async {
      final repo = SpinaTreasuryRepository(
        session: t.session(),
        deviceId: 'external',
        journal: MemoryTreasuryJournal(),
        client: MockClient((r) async {
          if (r.url.path.endsWith('/workspace')) {
            return t.jsonResponse(surplusWorkspace());
          }
          if (r.url.path.contains('/credits/')) {
            return t.jsonResponse(surplusCredit());
          }
          return t.jsonResponse(
            surplusOutcome(
              action: 'collector_surplus_return_request',
              slot: 'request',
              principal: requestRow(),
              disposition: 'requested',
              extra: {
                'credit': {
                  'id': t.event,
                  'version': 1,
                  'collector_user_id': t.user,
                },
              },
            ),
          );
        }),
      );
      await expectLater(
        repo.execute(ownReturn()),
        throwsA(isA<TreasuryUncertain>()),
      );
      expect(repo.pendingRequestId, t.requestId);
      repo.dispose();
    },
  );
  test('multi-role Collector explicitly selects safe own projection', () async {
    final repo = SpinaTreasuryRepository(
      session: t.session(),
      deviceId: 'external',
      journal: MemoryTreasuryJournal(),
      client: MockClient((r) async {
        expect(r.url.queryParameters['mode'], 'own');
        return t.jsonResponse(surplusWorkspace());
      }),
    );
    final dynamic native = repo;
    final dynamic value = await native.loadCollectorSurplus(mode: 'own');
    expect(value.mode, 'own');
    expect(value.accounts, isEmpty);
    repo.dispose();
  });
  test(
    'own request has no account grant; saved intent never claims payout',
    () async {
      final journal = MemoryTreasuryJournal();
      Map<String, dynamic>? sent;
      final repo = SpinaTreasuryRepository(
        session: t.session(),
        deviceId: 'external',
        journal: journal,
        client: MockClient((r) async {
          if (r.url.path.endsWith('/workspace')) {
            return t.jsonResponse(surplusWorkspace());
          }
          if (r.url.path.contains('/credits/')) {
            return t.jsonResponse(surplusCredit());
          }
          sent = jsonDecode(r.body);
          return t.jsonResponse(
            surplusOutcome(
              action: 'collector_surplus_return_request',
              slot: 'request',
              principal: requestRow(),
              disposition: 'requested',
              extra: {'credit': surplusCredit()},
            ),
          );
        }),
      );
      final result = await repo.execute(ownReturn());
      expect(result.result['disposition'], 'requested');
      expect(sent!.containsKey('account_id'), isFalse);
      expect(sent!['amount'], '40.00');
      expect(repo.pendingRequestId, isNull);
      expect(journal.value, isNull);
      repo.dispose();
    },
  );
  test(
    'unknown submitted own phase survives restart and GETnull without POST',
    () async {
      final journal = MemoryTreasuryJournal();
      var posts = 0;
      final client = MockClient((r) async {
        if (r.url.path.endsWith('/workspace')) {
          return t.jsonResponse(surplusWorkspace());
        }
        if (r.url.path.contains('/credits/')) {
          return t.jsonResponse(surplusCredit());
        }
        if (r.method == 'POST') {
          posts++;
          throw Exception('Synthetic lost response');
        }
        return t.jsonResponse(null);
      });
      final first = SpinaTreasuryRepository(
        session: t.session(),
        deviceId: 'external',
        journal: journal,
        client: client,
      );
      await expectLater(
        first.execute(ownReturn()),
        throwsA(isA<TreasuryUncertain>()),
      );
      first.dispose();
      final restored = SpinaTreasuryRepository(
        session: t.session(),
        deviceId: 'external',
        journal: journal,
        client: client,
      );
      await restored.loadCollectorSurplus();
      await restored.restoreAttempt();
      expect(restored.pendingRequestId, t.requestId);
      expect(await restored.recover(), isNull);
      expect(posts, 1);
      expect(restored.pendingRequestId, t.requestId);
      expect(journal.value, isNotNull);
      restored.dispose();
    },
  );
  test(
    'wrong returned Collector or principal never unlocks submitted request',
    () async {
      for (final changes in [
        {'collector_user_id': surplusCollector},
        {'amount': '41.00'},
        {'credit_id': t.ledger},
      ]) {
        final journal = MemoryTreasuryJournal();
        final repo = SpinaTreasuryRepository(
          session: t.session(),
          deviceId: 'external',
          journal: journal,
          client: MockClient((r) async {
            if (r.url.path.endsWith('/workspace')) {
              return t.jsonResponse(surplusWorkspace());
            }
            if (r.url.path.contains('/credits/')) {
              return t.jsonResponse(surplusCredit());
            }
            return t.jsonResponse(
              surplusOutcome(
                action: 'collector_surplus_return_request',
                slot: 'request',
                principal: {...requestRow(), ...changes},
                disposition: 'requested',
              ),
            );
          }),
        );
        await expectLater(
          repo.execute(ownReturn()),
          throwsA(isA<TreasuryUncertain>()),
        );
        expect(repo.pendingRequestId, t.requestId);
        expect(journal.value, isNotNull);
        repo.dispose();
      }
    },
  );
  test('own durable result cannot expose staff private evidence', () async {
    final repo = SpinaTreasuryRepository(
      session: t.session(),
      deviceId: 'external',
      journal: MemoryTreasuryJournal(),
      client: MockClient((r) async {
        if (r.url.path.endsWith('/workspace')) {
          return t.jsonResponse(surplusWorkspace());
        }
        if (r.url.path.contains('/credits/')) {
          return t.jsonResponse(surplusCredit());
        }
        return t.jsonResponse(
          surplusOutcome(
            action: 'collector_surplus_return_request',
            slot: 'request',
            principal: requestRow(),
            disposition: 'requested',
            extra: {
              'credit': {...surplusCredit(), 'evidence_id': t.ledger},
            },
          ),
        );
      }),
    );
    await expectLater(
      repo.execute(ownReturn()),
      throwsA(isA<TreasuryUncertain>()),
    );
    expect(repo.pendingRequestId, t.requestId);
    repo.dispose();
  });
  test(
    'short count remains rejected and cannot become physical acceptance',
    () async {
      var posts = 0;
      final repo = SpinaTreasuryRepository(
        session: t.session(),
        deviceId: 'external',
        journal: MemoryTreasuryJournal(),
        client: MockClient((r) async {
          if (r.url.path.endsWith('/workspace')) {
            return t.jsonResponse(
              surplusWorkspace(
                own: false,
                kind: CollectorSurplusKind.values.byName(
                  r.url.queryParameters['kind'] ?? 'credits',
                ),
              ),
            );
          }
          if (r.url.path.contains('/counts/')) {
            return t.jsonResponse(surplusCountRow(short: true));
          }
          if (r.url.path.endsWith('/preview')) {
            return t.jsonResponse(surplusPreview());
          }
          posts++;
          throw StateError('A rejected count must not be accepted');
        }),
      );
      await expectLater(
        repo.execute(
          TreasuryCommand(
            TreasuryAction.collectorCountAccept,
            requestId: t.requestId,
            accountId: t.account,
            expectedVersion: 1,
            fields: {
              'count_id': surplusCount,
              'count_version': 1,
              'source_digest': 'a' * 64,
              'physical_receipt_acknowledged': true,
            },
          ),
        ),
        throwsStateError,
      );
      expect(posts, 0);
      expect(repo.pendingRequestId, isNull);
      repo.dispose();
    },
  );
  test('own projection rejects private wallet and foreign credit history', () {
    for (final row in [
      {
        ...surplusCredit(),
        'balance': {'expected_balance': '1.00'},
      },
      {...surplusCredit(), 'collector_user_id': surplusCollector},
    ]) {
      expect(
        () => CollectorSurplusWorkspace(
          surplusWorkspace(rows: [row]),
          expectedUserId: t.user,
          kind: CollectorSurplusKind.credits,
          limit: 50,
          offset: 0,
        ),
        throwsFormatException,
      );
    }
  });
}
