import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance_repository.dart';
import 'package:gilbic_mobile/src/core/remittance/cross_remittance_repository.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const _digest =
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const _session = UserSession(
  userId: 'collector',
  username: 'collector',
  displayName: 'Collector',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'token',
  permissions: ['remittance.create'],
);

void main() {
  for (final cross in [false, true]) {
    test(
      '${cross ? 'Cross' : 'Normal'} preview digest is sent unchanged, without another preview',
      () async {
        final calls = <http.Request>[];
        final client = MockClient((request) async {
          calls.add(request);
          return http.Response(
            jsonEncode({
              'success': true,
              'data': request.method == 'GET'
                  ? {'review_digest': _digest, 'items': []}
                  : {'remittance_id': 'saved', 'remittance_number': 'REM-ONE'},
            }),
            200,
          );
        });
        if (cross) {
          final repo = SpinaCrossRemittanceRepository(client: client);
          final summary = await repo.loadPreview(
            _session,
            deviceId: 'device',
            recipientUserId: 'recipient',
            collectionDate: DateTime(2026, 10, 6),
          );
          await repo.submit(
            _session,
            deviceId: 'device',
            recipientUserId: 'recipient',
            collectionDate: DateTime(2026, 10, 6),
            note: 'Reviewed command',
            expectedReviewDigest: summary.reviewDigest!,
          );
        } else {
          final repo = SpinaRemittanceRepository(client: client);
          final summary = await repo.loadPreview(
            _session,
            deviceId: 'device',
            collectionDate: DateTime(2026, 10, 6),
          );
          await repo.submit(
            _session,
            deviceId: 'device',
            recipientUserId: 'recipient',
            collectionDate: DateTime(2026, 10, 6),
            note: 'Reviewed command',
            expectedReviewDigest: summary.reviewDigest!,
          );
        }
        expect(calls.map((r) => r.method).toList(), ['GET', 'POST']);
        expect(jsonDecode(calls.last.body)['expected_review_digest'], _digest);
        expect(jsonDecode(calls.last.body)['note'], 'Reviewed command');
      },
    );
    test(
      '${cross ? 'Cross' : 'Normal'} missing review digest is an explicit refresh error',
      () async {
        final client = MockClient(
          (_) async => http.Response(
            jsonEncode({
              'success': true,
              'data': {'items': []},
            }),
            200,
          ),
        );
        final read = cross
            ? SpinaCrossRemittanceRepository(client: client).loadPreview(
                _session,
                deviceId: 'device',
                recipientUserId: 'recipient',
                collectionDate: DateTime(2026, 10, 6),
              )
            : SpinaRemittanceRepository(client: client).loadPreview(
                _session,
                deviceId: 'device',
                collectionDate: DateTime(2026, 10, 6),
              );
        await expectLater(
          read,
          throwsA(
            isA<SpinaApiException>().having(
              (e) => e.message,
              'message',
              contains('Refresh and review'),
            ),
          ),
        );
      },
    );
  }
  test('old saved records remain readable without a live review digest', () {
    final record = RemittanceRecord.fromPayload({
      'remittance_id': 'old',
      'remittance_number': 'OLD',
      'items': [],
    });
    expect(record, isNotNull);
    expect(record!.summary.hasReviewDigest, isFalse);
  });
}
