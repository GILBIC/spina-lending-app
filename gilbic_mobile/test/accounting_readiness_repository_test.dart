import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/accounting_readiness_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const period = '11111111-1111-4111-8111-111111111111';
const session = UserSession(
  userId: 'manager',
  username: 'manager',
  displayName: 'Manager',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'private-token',
  permissions: ['accounting.view'],
);

void main() {
  test('expanded source families retain explicitly partial coverage', () {
    final coverage = AccountingSourceCoverage.fromPayload({
      'comprehensive_source_coverage': false,
      'source_families': accountingSourceFamilyLabels.keys.toList(),
      'blockers': [],
      'blocker_count': 0,
      'limit': 100,
      'offset': 0,
    });
    expect(
      coverage.sourceFamilies,
      containsAll(['lending', 'tax', 'period_assessment', 'liabilities']),
    );
    expect(coverage.comprehensiveSourceCoverage, isFalse);
  });
  test('an optional missing amount remains unavailable rather than zero', () {
    final blocker = AccountingSourceBlocker.fromPayload({
      'source_type': 'treasury_receipt',
      'source_id': period,
      'effective_date': '2026-09-30',
      'amount': null,
      'reason': 'Review retained evidence',
    });
    expect(blocker.amount, isNull);
    expect(blocker.sourceId, period);
  });
  test(
    'book and period source checks carry the same authenticated device scope',
    () async {
      final requests = <http.Request>[];
      final repository = SpinaAccountingReadinessRepository(
        client: MockClient((request) async {
          requests.add(request);
          return http.Response(
            jsonEncode({
              'success': true,
              'data': request.url.path.endsWith('/book')
                  ? {
                      'book': {
                        'status': 'configured',
                        'book_id': period,
                        'kind': 'corporate_legal',
                        'entity_label': 'Corporate ledger',
                      },
                    }
                  : {
                      'source_coverage': {
                        'fiscal_period_id': period,
                        'limit': 100,
                        'offset': 0,
                        'blocker_count': 1,
                        'comprehensive_source_coverage': false,
                        'source_families': ['treasury', 'collector'],
                        'blockers': [
                          {
                            'source_type': 'treasury_receipt',
                            'source_id': period,
                            'effective_date': '2026-09-30',
                            'amount': '90071992547409.93',
                            'reason': 'Unmapped actual receipt',
                          },
                        ],
                      },
                    },
            }),
            200,
          );
        }),
      );
      final book = await repository.loadBook(session, deviceId: 'phone');
      final coverage = await repository.loadSourceCoverage(
        session,
        deviceId: 'phone',
        periodId: period,
      );
      expect(book.entityLabel, 'Corporate ledger');
      expect(book.kindLabel, 'Corporate legal');
      expect(coverage.comprehensiveSourceCoverage, isFalse);
      expect(coverage.blockers.single.amount, '90071992547409.93');
      expect(requests.map((request) => request.url.path), [
        '/api/mobile/v1/management/financial-accounting/book',
        '/api/mobile/v1/management/financial-accounting/period-close/$period/source-blockers',
      ]);
      for (final request in requests) {
        expect(request.method, 'GET');
        expect(request.headers['Authorization'], 'Bearer private-token');
        expect(request.headers['X-Device-Id'], 'phone');
      }
    },
  );

  test(
    'an absent coverage list or numeric money is never interpreted as readiness',
    () {
      expect(
        () => AccountingSourceCoverage.fromPayload({
          'comprehensive_source_coverage': false,
          'source_families': ['treasury'],
        }),
        throwsFormatException,
      );
      expect(
        () => AccountingSourceBlocker.fromPayload({
          'source_type': 'receipt',
          'source_id': period,
          'effective_date': '2026-09-30',
          'amount': 12.34,
          'reason': 'Review',
        }),
        throwsFormatException,
      );
      expect(
        () => AccountingBookIdentity.fromPayload({
          'status': 'configured',
          'book_id': period,
          'kind': 'unknown',
          'entity_label': 'Unknown',
        }),
        throwsFormatException,
      );
    },
  );

  test(
    'access denial remains a failure rather than an empty source check',
    () async {
      final repository = SpinaAccountingReadinessRepository(
        client: MockClient(
          (_) async => http.Response(
            jsonEncode({
              'detail': {'code': 'forbidden', 'message': 'Access denied'},
            }),
            403,
          ),
        ),
      );
      await expectLater(
        repository.loadSourceCoverage(
          session,
          deviceId: 'phone',
          periodId: period,
        ),
        throwsA(
          isA<SpinaApiException>().having(
            (error) => error.statusCode,
            'statusCode',
            403,
          ),
        ),
      );
    },
  );
}
