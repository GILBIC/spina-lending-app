import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/media/private_image_store.dart';
import 'package:gilbic_mobile/src/core/treasury/collector_surplus_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_repository.dart';
import 'package:gilbic_mobile/src/features/treasury/collector_surplus_page.dart';
import 'package:gilbic_mobile/src/features/treasury/treasury_workspace_page.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:image_picker/image_picker.dart';
import 'support/android_role_fixture.dart';
import 'support/collector_surplus_fixture.dart' as s;
import 'support/treasury_fixture.dart' as t;

Map<String, dynamic> clone(Object value) =>
    treasuryObject(jsonDecode(jsonEncode(value)));

class RetainedFiles extends PrivateImageStore {
  final files = <String, XFile>{};
  int cleanups = 0;
  @override
  Future<XFile> retain(XFile source) async {
    final copy = XFile.fromData(
      await source.readAsBytes(),
      path: '${Directory.systemTemp.path}/synthetic-review/${source.name}',
      name: source.name,
      mimeType: source.mimeType,
    );
    files[copy.path] = copy;
    return copy;
  }

  @override
  Future<T> use<T>(XFile file, Future<T> Function(XFile) read) =>
      read(files[file.path] ?? file);
  @override
  Future<bool> owns(XFile file) async => files.containsKey(file.path);
  @override
  Future<void> cleanup({String? keepPath}) async {
    cleanups++;
    files.removeWhere((path, _) => path != keepPath);
  }
}

TreasuryCommand ownReturn() => TreasuryCommand(
  TreasuryAction.collectorSurplusReturnRequest,
  requestId: t.requestId,
  fields: {
    'credit_id': t.event,
    'credit_version': 1,
    'amount': '40.00',
    'destination': {'kind': 'physical_cash', 'recipient_reference': null},
    'reason': 'Synthetic independent review',
  },
);

void main() {
  final fixture =
      jsonDecode(
            File(
              'test/support/collector_surplus_backend_examples.json',
            ).readAsStringSync(),
          )
          as Map;
  final examples = (fixture['examples'] as List).cast<Map>();
  final accept = examples.firstWhere(
    (e) => e['kind'] == 'collector_count_accept',
  );
  final count = examples.firstWhere(
    (e) => e['kind'] == 'collector_count_record',
  )['response']['data']['result']['count'];
  final original = clone(accept['response']['data']);
  final held = <String, dynamic>{
    'request_id': accept['command']['request_id'],
    'action': accept['command']['action'],
    'actor_user_id': accept['actor']['user_id'],
    'device_id': accept['actor']['device_id'],
    'account_id': original['result']['account_id'],
    'ledger_context_id': original['result']['ledger_context_id'],
    'surplus_mode': 'staff',
    'body': accept['command'],
    'surplus_records': {'count': count},
  };
  for (final entry in <String, void Function(Map<String, dynamic>)>{
    'unsupported authorized credit': (v) =>
        v['result']['settlement']['authorized_credit_amount'] = '100.00',
    'changed settlement gross': (v) =>
        v['result']['settlement']['gross_obligation'] = '9999.00',
    'changed count gross': (v) =>
        v['result']['count']['gross_obligation'] = '9999.00',
    'changed count difference': (v) =>
        v['result']['count']['difference'] = '9999.00',
    'changed case excess': (v) =>
        v['result']['case']['received_excess_amount'] = '9999.00',
    'changed case unidentified': (v) =>
        v['result']['case']['unidentified_amount'] = '9999.00',
    'foreign case Collector': (v) =>
        v['result']['case']['collector_user_id'] = v['result']['account_id'],
    'foreign case settlement': (v) =>
        v['result']['case']['settlement_id'] = v['result']['account_id'],
  }.entries) {
    test('actual count acceptance rejects ${entry.key}', () {
      expect(validateCollectorOutcome(original, held).status, 'saved');
      final changed = clone(original);
      entry.value(changed);
      expect(
        () => validateCollectorOutcome(changed, held),
        throwsFormatException,
      );
    });
  }
  for (final key in [
    'accounts',
    'collector_choices',
    'opening_choices',
    'private_identifier',
  ]) {
    test('own workspace and export reject private top-level $key', () async {
      final page = s.surplusWorkspace(rows: [s.surplusCredit()]);
      page[key] = key == 'private_identifier'
          ? 'SYNTHETIC OFFICE METADATA'
          : [
              {'private_identifier': 'SYNTHETIC OFFICE METADATA'},
            ];
      expect(
        () => CollectorSurplusWorkspace(
          page,
          expectedUserId: t.user,
          kind: CollectorSurplusKind.credits,
          limit: 50,
          offset: 0,
        ),
        throwsFormatException,
      );
      final repo = SpinaTreasuryRepository(
        session: t.session(),
        deviceId: 'external',
        journal: MemoryTreasuryJournal(),
        images: RetainedFiles(),
        client: MockClient(
          (r) async => t.jsonResponse(
            r.url.path.endsWith('/export')
                ? page
                : s.surplusWorkspace(rows: [s.surplusCredit()]),
          ),
        ),
      );
      await repo.loadCollectorSurplus(mode: 'own');
      await expectLater(repo.exportCollectorSurplus(), throwsFormatException);
      repo.dispose();
    });
  }
  test(
    'own totals cannot expose an unrecognized private wallet amount',
    () async {
      final page = s.surplusWorkspace(rows: [s.surplusCredit()]);
      page['totals']['actual_wallet_amount'] = '10000.00';
      expect(
        () => CollectorSurplusWorkspace(
          page,
          expectedUserId: t.user,
          kind: CollectorSurplusKind.credits,
          limit: 50,
          offset: 0,
        ),
        throwsFormatException,
      );
      final repo = SpinaTreasuryRepository(
        session: t.session(),
        deviceId: 'external',
        journal: MemoryTreasuryJournal(),
        images: RetainedFiles(),
        client: MockClient(
          (r) async => t.jsonResponse(
            r.url.path.endsWith('/export') ? page : s.surplusWorkspace(),
          ),
        ),
      );
      await repo.loadCollectorSurplus(mode: 'own');
      await expectLater(repo.exportCollectorSurplus(), throwsFormatException);
      repo.dispose();
    },
  );
  for (final key in [
    'reason',
    'unknown_borrower',
    'entry_private',
    'resolution_private',
    'destination_private',
    'ack_private',
    'kind_compound',
    'entry_compound',
    'resolution_compound',
  ]) {
    test('own detail rejects investigation or unknown nested $key', () async {
      final row = s.surplusCredit();
      if (key == 'entry_private') {
        row['entries'] = [
          {
            'id': s.surplusAction,
            'kind': 'return',
            'amount': '1.00',
            'private_identifier': 'SYNTHETIC OFFICE',
          },
        ];
      } else if (key == 'resolution_private') {
        row['resolutions'] = [
          {
            'id': s.surplusAction,
            'kind': 'recognized',
            'amount': '1.00',
            'reason': 'SYNTHETIC INVESTIGATION',
          },
        ];
      } else if (key == 'destination_private') {
        row['destination'] = {
          'kind': 'physical_cash',
          'recipient_reference': null,
          'private_identifier': 'SYNTHETIC OFFICE',
        };
      } else if (key == 'ack_private') {
        row['acknowledgment'] = {
          'id': s.surplusAction,
          'version': 1,
          'collector_user_id': t.user,
          'reason': 'SYNTHETIC INVESTIGATION',
        };
      } else if (key == 'kind_compound') {
        row['kind'] = {'private_identifier': 'SYNTHETIC OFFICE'};
      } else if (key == 'entry_compound') {
        row['entries'] = [
          {
            'id': s.surplusAction,
            'kind': {'private_identifier': 'SYNTHETIC OFFICE'},
            'amount': '1.00',
          },
        ];
      } else if (key == 'resolution_compound') {
        row['resolutions'] = [
          {
            'id': s.surplusAction,
            'kind': ['SYNTHETIC INVESTIGATION'],
            'amount': '1.00',
          },
        ];
      } else {
        row[key] = 'SYNTHETIC INVESTIGATION';
      }
      final repo = SpinaTreasuryRepository(
        session: t.session(),
        deviceId: 'external',
        journal: MemoryTreasuryJournal(),
        images: RetainedFiles(),
        client: MockClient(
          (r) async => t.jsonResponse(
            r.url.path.contains('/credits/') ? row : s.surplusWorkspace(),
          ),
        ),
      );
      await repo.loadCollectorSurplus(mode: 'own');
      await expectLater(
        repo.collectorSurplusDetail(CollectorSurplusKind.credits, t.event),
        throwsFormatException,
      );
      repo.dispose();
    });
  }
  for (final entry in <String, void Function(Map<String, dynamic>)>{
    'unknown result root': (v) =>
        v['result']['private_identifier'] = 'SYNTHETIC OFFICE',
    'unknown result envelope': (v) =>
        v['private_identifier'] = 'SYNTHETIC OFFICE',
    'untyped acknowledgment slot': (v) => v['result']['acknowledgment'] = {
      'kind': {'private_identifier': 'SYNTHETIC OFFICE'},
    },
    'private blocker metadata': (v) => v['result']['blockers'] = [
      {
        'code': 'synthetic',
        'message': 'Synthetic blocker',
        'private_identifier': 'SYNTHETIC OFFICE',
      },
    ],
  }.entries) {
    test('actual own phase rejects ${entry.key}', () {
      final own = examples.firstWhere(
        (e) => e['kind'] == 'collector_surplus_return_request',
      );
      final raw = clone(own['response']['data']);
      final attempt = <String, dynamic>{
        'request_id': own['command']['request_id'],
        'action': own['command']['action'],
        'actor_user_id': own['actor']['user_id'],
        'device_id': own['actor']['device_id'],
        'account_id': raw['result']['account_id'],
        'ledger_context_id': raw['result']['ledger_context_id'],
        'surplus_mode': 'own',
        'body': own['command'],
        'surplus_records': {'credit': raw['result']['credit']},
      };
      expect(validateCollectorOutcome(raw, attempt).status, 'saved');
      final changed = clone(raw);
      entry.value(changed);
      expect(
        () => validateCollectorOutcome(changed, attempt),
        throwsFormatException,
      );
    });
  }
  test(
    'own export rejects private metadata outside the data envelope',
    () async {
      final repo = SpinaTreasuryRepository(
        session: t.session(),
        deviceId: 'external',
        journal: MemoryTreasuryJournal(),
        images: RetainedFiles(),
        client: MockClient(
          (r) async => r.url.path.endsWith('/export')
              ? http.Response(
                  jsonEncode({
                    'success': true,
                    'data': s.surplusWorkspace(),
                    'private_identifier': 'SYNTHETIC OFFICE',
                  }),
                  200,
                  headers: {'content-type': 'application/json'},
                )
              : t.jsonResponse(s.surplusWorkspace()),
        ),
      );
      await repo.loadCollectorSurplus(mode: 'own');
      await expectLater(repo.exportCollectorSurplus(), throwsFormatException);
      repo.dispose();
    },
  );
  testWidgets(
    'lost own return survives remount through ordinary Treasury entry',
    (tester) async {
      final journal = MemoryTreasuryJournal();
      final files = RetainedFiles();
      var posts = 0;
      final client = MockClient((r) async {
        if (r.method == 'POST') {
          posts++;
          throw Exception('Synthetic lost response');
        }
        if (r.url.path.contains('/collector-surplus/workspace')) {
          expect(r.url.queryParameters['mode'], 'own');
          return t.jsonResponse(s.surplusWorkspace());
        }
        if (r.url.path.endsWith('/workspace')) {
          return t.jsonResponse(t.workspace());
        }
        if (r.url.path.contains('/credits/')) {
          return t.jsonResponse(s.surplusCredit());
        }
        if (r.url.path.endsWith('/claims')) {
          return t.jsonResponse({
            'items': [],
            'total_count': 0,
            'limit': 50,
            'offset': 0,
            'has_more': false,
            'totals': null,
          });
        }
        return t.jsonResponse(null);
      });
      final first = SpinaTreasuryRepository(
        session: t.session(),
        deviceId: 'external',
        journal: journal,
        images: files,
        client: client,
      );
      await first.loadCollectorSurplus(mode: 'own');
      await expectLater(
        first.execute(ownReturn()),
        throwsA(isA<TreasuryUncertain>()),
      );
      final retained = journal.value;
      first.dispose();
      final restored = SpinaTreasuryRepository(
        session: t.session(),
        deviceId: 'external',
        journal: journal,
        images: files,
        client: client,
      );
      await pumpAndroidRoleFixture(
        tester,
        size: const Size(412, 900),
        textScaler: TextScaler.noScaling,
        home: TreasuryWorkspacePage(session: t.session(), repository: restored),
      );
      await tester.pumpAndSettle();
      expect(restored.pendingRequestId, t.requestId);
      expect(journal.value, retained);
      expect(files.cleanups, 0);
      expect(await restored.recover(), isNull);
      expect(restored.pendingRequestId, t.requestId);
      expect(posts, 1);
    },
  );
  testWidgets(
    'lost evidence upload survives remount through own Collector entry',
    (tester) async {
      final journal = MemoryTreasuryJournal();
      final files = RetainedFiles();
      var posts = 0;
      final client = MockClient((r) async {
        if (r.method == 'POST') {
          posts++;
          throw Exception('Synthetic lost upload response');
        }
        if (r.url.path.contains('/collector-surplus/workspace')) {
          return t.jsonResponse(s.surplusWorkspace());
        }
        if (r.url.path.endsWith('/workspace')) {
          return t.jsonResponse(t.workspace());
        }
        return t.jsonResponse(null);
      });
      final first = SpinaTreasuryRepository(
        session: t.session(),
        deviceId: 'external',
        journal: journal,
        images: files,
        client: client,
      );
      await expectLater(
        first.uploadEvidence(
          requestId: t.requestId,
          accountId: t.account,
          purpose: 'recipient',
          file: XFile.fromData(
            Uint8List.fromList([0x89, 0x50, 0x4e, 0x47, 13, 10, 26, 10]),
            name: 'proof.png',
            mimeType: 'image/png',
          ),
        ),
        throwsA(isA<TreasuryUncertain>()),
      );
      final retained = journal.value;
      first.dispose();
      final restored = SpinaTreasuryRepository(
        session: t.session(),
        deviceId: 'external',
        journal: journal,
        images: files,
        client: client,
      );
      await pumpAndroidRoleFixture(
        tester,
        size: const Size(412, 900),
        textScaler: TextScaler.noScaling,
        home: CollectorSurplusPage(
          session: t.session(),
          repository: restored,
          ownMode: true,
        ),
      );
      await tester.pumpAndSettle();
      expect(restored.pendingRequestId, t.requestId);
      expect(journal.value, retained);
      expect(files.files, hasLength(1));
      expect(files.cleanups, 0);
      expect(await restored.recover(), isNull);
      expect(files.files, hasLength(1));
      expect(posts, 1);
      restored.dispose();
    },
  );
  test(
    'unavailable authorization retains pending journal and prohibits another write',
    () async {
      final journal = MemoryTreasuryJournal();
      final files = RetainedFiles();
      final first = SpinaTreasuryRepository(
        session: t.session(),
        deviceId: 'external',
        journal: journal,
        images: files,
        client: MockClient((r) async {
          if (r.url.path.endsWith('/workspace')) {
            return t.jsonResponse(s.surplusWorkspace());
          }
          if (r.url.path.contains('/credits/')) {
            return t.jsonResponse(s.surplusCredit());
          }
          throw Exception('Synthetic lost response');
        }),
      );
      await expectLater(
        first.execute(ownReturn()),
        throwsA(isA<TreasuryUncertain>()),
      );
      final retained = journal.value;
      first.dispose();
      final restored = SpinaTreasuryRepository(
        session: t.session(),
        deviceId: 'external',
        journal: journal,
        images: files,
        client: MockClient(
          (_) async => http.Response('{"detail":"Unavailable"}', 503),
        ),
      );
      await expectLater(restored.restoreAttempt(), throwsA(isA<Exception>()));
      expect(journal.value, retained);
      expect(restored.pendingRequestId, t.requestId);
      expect(files.cleanups, 0);
      await expectLater(restored.execute(ownReturn()), throwsStateError);
      restored.dispose();
    },
  );
}
