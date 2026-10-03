import 'package:flutter_test/flutter_test.dart';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/testing.dart';
import 'package:gilbic_mobile/src/core/treasury/collector_surplus_models.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_repository.dart';
import 'package:gilbic_mobile/src/features/treasury/collector_surplus_page.dart';
import 'support/collector_surplus_fixture.dart';
import 'support/treasury_fixture.dart' as t;
import 'collector_surplus_phase_test.dart' show held;

void main() {
  final exception = {
    'id': surplusAck,
    'version': 2,
    'account_id': t.account,
    'ledger_context_id': t.ledger,
    'collector_user_id': surplusCollector,
    'remittance_id': surplusRemittance,
    'status': 'held_disputed',
    'retained_amount': '9900.00',
    'returned_amount': '0.00',
    'included_amount': '0.00',
    'remaining_held_amount': '9900.00',
    'reserved_amount': '0.00',
    'available_amount': '9900.00',
  };
  final preview = surplusPreview()
    ..addAll({
      'physical_cash_required': '100.00',
      'retained_cash_amount': '9900.00',
      'retained_exception_id': surplusAck,
      'retained_exception_version': 2,
    });
  testWidgets(
    'recipient explicitly reviews held cash before entering only new cash',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(800, 1600));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final requests = <Map>[];
      final repo = SpinaTreasuryRepository(
        session: t.session(),
        deviceId: 'external',
        journal: MemoryTreasuryJournal(),
        client: MockClient((request) async {
          if (request.url.path.endsWith('/preview')) {
            requests.add(jsonDecode(request.body) as Map);
            return t.jsonResponse(preview);
          }
          return t.jsonResponse(
            surplusWorkspace(
              own: false,
              kind: CollectorSurplusKind.values.byName(
                request.url.queryParameters['kind'] ?? 'exceptions',
              ),
            ),
          );
        }),
      );
      addTearDown(repo.dispose);
      await repo.loadCollectorSurplus(kind: CollectorSurplusKind.exceptions);
      await tester.pumpWidget(
        MaterialApp(
          home: CollectorSurplusRecordPage(
            repository: repo,
            kind: CollectorSurplusKind.exceptions,
            record: exception,
          ),
        ),
      );
      expect(find.text('Record actual cash count'), findsNothing);
      await tester.tap(find.text('Review inclusion of retained cash'));
      await tester.pumpAndSettle();
      expect(requests.single['retained_exception_id'], surplusAck);
      expect(requests.single['retained_exception_version'], 2);
      await tester.ensureVisible(find.text('Record actual cash count'));
      await tester.tap(find.text('Record actual cash count'));
      await tester.pumpAndSettle();
      expect(
        find.text(
          'Enter only new cash counted now. Previously retained cash is included separately from the reviewed record.',
        ),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
    },
  );
  test(
    'repository rejects a substituted exception or omitted held amount in preview',
    () async {
      for (final change in [
        {'retained_exception_id': t.event},
        {'retained_exception_version': 3},
        {'retained_cash_amount': '0.00'},
      ]) {
        final repo = SpinaTreasuryRepository(
          session: t.session(),
          deviceId: 'external',
          journal: MemoryTreasuryJournal(),
          client: MockClient(
            (request) async => t.jsonResponse(
              request.url.path.endsWith('/preview')
                  ? {...preview, ...change}
                  : surplusWorkspace(
                      own: false,
                      kind: CollectorSurplusKind.remittances,
                    ),
            ),
          ),
        );
        addTearDown(repo.dispose);
        await expectLater(
          repo.collectorSettlementPreview(
            surplusRemittance,
            t.account,
            retainedExceptionId: surplusAck,
            retainedExceptionVersion: 2,
          ),
          throwsFormatException,
        );
      }
    },
  );
  test('acceptance cannot omit or substitute the reviewed retained cash', () {
    final count = surplusCountRow()
      ..addAll({
        'counted_amount': '100.00',
        'physical_cash_required': '100.00',
        'difference': '0.00',
        'retained_cash_amount': '9900.00',
        'retained_exception_id': surplusAck,
        'retained_exception_version': 2,
      });
    final settlement = {
      'id': surplusAction,
      'version': 1,
      'account_id': t.account,
      'ledger_context_id': t.ledger,
      'count_id': surplusCount,
      'remittance_id': surplusRemittance,
      'collector_user_id': surplusCollector,
      'recipient_user_id': t.user,
      'physical_amount': '100.00',
      'authorized_credit_amount': '0.00',
      'gross_obligation': count['gross_obligation'],
      'event_id': t.event,
      'retained_cash_amount': '9900.00',
      'retained_exception_id': surplusAck,
      'retained_exception_version': 2,
    };
    final attempt = held(
      'collector_count_accept',
      {'count_id': surplusCount},
      {'count': count},
    );
    Map<String, dynamic> outcome(Map<String, dynamic> row) => surplusOutcome(
      action: 'collector_count_accept',
      slot: 'settlement',
      principal: row,
      disposition: 'accepted_exact',
      extra: {'count': count},
    );
    expect(
      validateCollectorOutcome(outcome(settlement), attempt).status,
      'saved',
    );
    for (final change in [
      {'retained_cash_amount': '0.00'},
      {'retained_exception_id': null},
      {'retained_exception_version': 3},
    ]) {
      expect(
        () => validateCollectorOutcome(
          outcome({...settlement, ...change}),
          attempt,
        ),
        throwsFormatException,
      );
    }
  });
}
