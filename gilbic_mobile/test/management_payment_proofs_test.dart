import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_payment_proof_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_payment_proofs_page.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const _proofId = '10000000-0000-4000-8000-000000000001';
const _reviewId = '20000000-0000-4000-8000-000000000001';
const _session = UserSession(
  userId: 'manager',
  username: 'manager',
  displayName: 'Manager',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'token',
  permissions: ['client_payment_proof.review'],
);

Map<String, Object?> _version(int number) => {
  'version_id': '30000000-0000-4000-8000-00000000000$number',
  'version_number': number,
  'media_type': 'application/pdf',
  'byte_count': 4,
  'sha256': sha256.convert(utf8.encode('PDF!')).toString(),
  'uploaded_at': '2026-09-19T10:00:00Z',
  'note': 'Submitted version $number',
};
Map<String, Object?> _review(String decision) => {
  'review_id': _reviewId,
  'decision': decision,
  'reason': decision == 'reviewed' ? '' : 'Recorded review reason',
  'reviewed_at': '2026-09-19T11:00:00Z',
};
Map<String, Object?> _proof({String? decision, String id = _proofId}) => {
  'proof_id': id,
  'loan_id': '40000000-0000-4000-8000-000000000001',
  'loan_number': 'LN-001',
  'loan_type_name': 'Regular',
  'client_name': 'Borrower One',
  'client_code': 'C-001',
  'submitted_at': '2026-09-19T10:00:00Z',
  'status': decision ?? 'under_review',
  'current_version': _version(2),
  'latest_review': decision == null ? null : _review(decision),
  'official_payment_posted': false,
};
Map<String, Object?> _detail({String? decision, String id = _proofId}) => {
  'proof': _proof(decision: decision, id: id),
  'history': [
    {
      'version': _version(2),
      'reviews': [if (decision != null) _review(decision)],
    },
    {
      'version': _version(1),
      'reviews': [_review('correction_required')],
    },
  ],
};
http.Response _ok(Object data) =>
    http.Response(jsonEncode({'success': true, 'data': data}), 200);

void main() {
  testWidgets(
    'Repeated confirmation callbacks cannot replace an uncertain review identity',
    (tester) async {
      final submissions = <Map<String, dynamic>>[];
      final repository = SpinaManagementPaymentProofRepository(
        client: MockClient((request) async {
          if (request.method == 'POST') {
            submissions.add(jsonDecode(request.body) as Map<String, dynamic>);
            throw http.ClientException('Lost response');
          }
          if (request.url.path.endsWith(_proofId)) return _ok(_detail());
          return _ok({
            'proofs': [_proof()],
            'has_more': false,
          });
        }),
      );
      await _pump(tester, repository);
      await tester.tap(find.byKey(const Key('management-proof-$_proofId')));
      await tester.pumpAndSettle();
      final submit = tester
          .widget<FilledButton>(
            find.byKey(const Key('submit-management-proof-review')),
          )
          .onPressed!;
      submit();
      submit();
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-payment-proof')).last);
      await tester.pumpAndSettle();
      // An obsolete dialog must never start another request. If confirmation is
      // serialized, this finder is already absent after the first response.
      final obsoleteConfirmation = find.byKey(
        const Key('confirm-payment-proof'),
      );
      if (obsoleteConfirmation.evaluate().isNotEmpty) {
        await tester.tap(obsoleteConfirmation);
        await tester.pumpAndSettle();
      }
      expect(submissions, hasLength(1));
      await tester.ensureVisible(find.text('Retry same review'));
      await tester.tap(find.text('Retry same review'));
      await tester.pumpAndSettle();
      expect(submissions, hasLength(2));
      expect(submissions[1], submissions[0]);
    },
  );

  test(
    'A stale matching historical decision cannot confirm a new review',
    () async {
      final stale = _detail(decision: 'reviewed');
      final history = stale['history']! as List;
      (history.first['reviews'] as List).add({
        ..._review('reviewed'),
        'review_id': 'older-review',
      });
      final repository = SpinaManagementPaymentProofRepository(
        client: MockClient((_) async => _ok(stale)),
      );
      await expectLater(
        repository.review(
          _session,
          deviceId: 'device',
          attempt: const ManagementProofReviewAttempt(
            proofId: _proofId,
            requestId: 'new-request',
            expectedVersion: 2,
            expectedReviewId: _reviewId,
            decision: 'reviewed',
            reason: '',
          ),
        ),
        throwsA(isA<SpinaApiException>()),
      );
    },
  );

  testWidgets(
    'Queue pagination appends server pages without losing earlier evidence',
    (tester) async {
      final offsets = <String?>[];
      final repository = SpinaManagementPaymentProofRepository(
        client: MockClient((request) async {
          final offset = request.url.queryParameters['offset'];
          offsets.add(offset);
          return _ok({
            'proofs': [_proof(id: offset == '0' ? _proofId : 'second-proof')],
            'has_more': offset == '0',
          });
        }),
      );
      await _pump(tester, repository);
      await tester.tap(find.byKey(const Key('more-management-proofs')));
      await tester.pumpAndSettle();
      expect(offsets, ['0', '1']);
      expect(
        find.byKey(const Key('management-proof-$_proofId')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('management-proof-second-proof')),
        findsOneWidget,
      );
      expect(find.byKey(const Key('more-management-proofs')), findsNothing);
    },
  );

  testWidgets(
    'Conflict clears review controls until fresh evidence is opened',
    (tester) async {
      var posts = 0;
      final repository = SpinaManagementPaymentProofRepository(
        client: MockClient((request) async {
          if (request.method == 'POST') {
            posts++;
            return http.Response('{"detail":"Changed"}', 409);
          }
          if (request.url.path.endsWith(_proofId)) return _ok(_detail());
          return _ok({
            'proofs': [_proof()],
            'has_more': false,
          });
        }),
      );
      await _pump(tester, repository);
      await tester.tap(find.byKey(const Key('management-proof-$_proofId')));
      await tester.pumpAndSettle();
      await tester.ensureVisible(
        find.byKey(const Key('submit-management-proof-review')),
      );
      await tester.tap(find.byKey(const Key('submit-management-proof-review')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('cancel-payment-proof')));
      await tester.pumpAndSettle();
      expect(posts, 0);
      await tester.tap(find.byKey(const Key('submit-management-proof-review')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-payment-proof')));
      await tester.pumpAndSettle();
      expect(posts, 1);
      expect(
        find.byKey(const Key('submit-management-proof-review')),
        findsNothing,
      );
      expect(find.text('Retry same review'), findsNothing);
      await tester.tap(find.byKey(const Key('management-proof-$_proofId')));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('submit-management-proof-review')),
        findsOneWidget,
      );
    },
  );

  for (final decision in ['correction_required', 'rejected']) {
    testWidgets('$decision requires a reason and binds the latest review', (
      tester,
    ) async {
      Map<String, dynamic>? submission;
      final repository = SpinaManagementPaymentProofRepository(
        client: MockClient((request) async {
          if (request.method == 'POST') {
            submission = jsonDecode(request.body) as Map<String, dynamic>;
            return http.Response('{"detail":"Changed"}', 409);
          }
          if (request.url.path.endsWith(_proofId)) {
            return _ok(_detail(decision: 'reviewed'));
          }
          return _ok({
            'proofs': [_proof(decision: 'reviewed')],
            'has_more': false,
          });
        }),
      );
      await _pump(tester, repository);
      await tester.tap(find.byKey(const Key('management-proof-$_proofId')));
      await tester.pumpAndSettle();
      await tester.ensureVisible(
        find.byKey(const Key('management-proof-decision')),
      );
      await tester.tap(find.byKey(const Key('management-proof-decision')));
      await tester.pumpAndSettle();
      await tester.tap(
        find
            .text(decision == 'rejected' ? 'Rejected' : 'Correction required')
            .last,
      );
      await tester.pumpAndSettle();
      await tester.ensureVisible(
        find.byKey(const Key('submit-management-proof-review')),
      );
      await tester.tap(find.byKey(const Key('submit-management-proof-review')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('confirm-payment-proof')), findsNothing);
      expect(submission, isNull);
      await tester.enterText(
        find.byKey(const Key('management-proof-reason')),
        'Unreadable receipt',
      );
      await tester.ensureVisible(
        find.byKey(const Key('submit-management-proof-review')),
      );
      await tester.tap(find.byKey(const Key('submit-management-proof-review')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-payment-proof')));
      await tester.pumpAndSettle();
      expect(submission?['expected_review_id'], _reviewId);
      expect(submission?['expected_version'], 2);
      expect(submission?['decision'], decision);
      expect(submission?['reason'], 'Unreadable receipt');
    });
  }

  test('Management queue sends protected identity and page offset', () async {
    final repository = SpinaManagementPaymentProofRepository(
      client: MockClient((request) async {
        expect(request.url.path, '/api/mobile/v1/management/payment-proofs');
        expect(request.url.queryParameters, {'limit': '50', 'offset': '50'});
        expect(request.headers['Authorization'], 'Bearer token');
        expect(request.headers['X-Device-Id'], 'device');
        return _ok({
          'proofs': [_proof()],
          'has_more': true,
        });
      }),
    );
    final page = await repository.list(
      _session,
      deviceId: 'device',
      offset: 50,
    );
    expect(page.hasMore, isTrue);
    expect(page.proofs.single.clientName, 'Borrower One');
  });

  test(
    'Review sends exact snapshot and rejects another proof response',
    () async {
      final repository = SpinaManagementPaymentProofRepository(
        client: MockClient((request) async {
          expect(request.method, 'POST');
          expect(
            request.url.path,
            '/api/mobile/v1/management/payment-proofs/$_proofId/reviews',
          );
          expect(jsonDecode(request.body), {
            'request_id': _reviewId,
            'expected_version': 2,
            'expected_review_id': null,
            'decision': 'reviewed',
            'reason': '',
          });
          return _ok(_detail(decision: 'reviewed', id: 'wrong-proof'));
        }),
      );
      await expectLater(
        repository.review(
          _session,
          deviceId: 'device',
          attempt: const ManagementProofReviewAttempt(
            proofId: _proofId,
            requestId: _reviewId,
            expectedVersion: 2,
            expectedReviewId: null,
            decision: 'reviewed',
            reason: '',
          ),
        ),
        throwsA(isA<SpinaApiException>()),
      );
    },
  );

  test('Private proof content checks media type and byte count', () async {
    final repository = SpinaManagementPaymentProofRepository(
      client: MockClient((request) async {
        expect(request.headers['Authorization'], 'Bearer token');
        expect(
          request.url.path,
          '/api/mobile/v1/management/payment-proofs/$_proofId/versions/2/content',
        );
        return http.Response(
          'oops',
          200,
          headers: {'content-type': 'text/html'},
        );
      }),
    );
    final detail = ManagementProofDetail.fromPayload(_detail());
    await expectLater(
      repository.download(
        _session,
        deviceId: 'device',
        proofId: _proofId,
        version: detail.proof.currentVersion,
      ),
      throwsA(isA<SpinaApiException>()),
    );
  });

  test(
    'Private proof download rejects altered content with matching type and length',
    () async {
      final repository = SpinaManagementPaymentProofRepository(
        client: MockClient(
          (_) async => http.Response(
            'BAD!',
            200,
            headers: {'content-type': 'application/pdf'},
          ),
        ),
      );
      await expectLater(
        repository.download(
          _session,
          deviceId: 'device',
          proofId: _proofId,
          version: ManagementProofDetail.fromPayload(
            _detail(),
          ).proof.currentVersion,
        ),
        throwsA(isA<SpinaApiException>()),
      );
    },
  );

  testWidgets(
    'Full evidence history downloads and retries one immutable review',
    (tester) async {
      final submissions = <Map<String, dynamic>>[];
      var downloads = 0;
      final repository = SpinaManagementPaymentProofRepository(
        client: MockClient((request) async {
          if (request.method == 'POST') {
            submissions.add(jsonDecode(request.body) as Map<String, dynamic>);
            if (submissions.length == 1) {
              throw http.ClientException('Lost response');
            }
            return _ok(_detail(decision: 'reviewed'));
          }
          if (request.url.path.endsWith('/content')) {
            downloads++;
            return http.Response(
              'PDF!',
              200,
              headers: {'content-type': 'application/pdf'},
            );
          }
          if (request.url.path.endsWith(_proofId)) return _ok(_detail());
          return _ok({
            'proofs': [_proof()],
            'has_more': false,
          });
        }),
      );
      await _pump(
        tester,
        repository,
        saver: (document) async {
          expect(document.bytes, utf8.encode('PDF!'));
          return true;
        },
      );
      await tester.tap(find.byKey(const Key('management-proof-$_proofId')));
      await tester.pumpAndSettle();
      expect(find.text('Submitted version 1'), findsOneWidget);
      expect(find.text('Recorded review reason'), findsOneWidget);
      await tester.tap(find.byKey(const Key('download-management-proof-2')));
      await tester.pumpAndSettle();
      expect(downloads, 1);
      await tester.ensureVisible(
        find.byKey(const Key('submit-management-proof-review')),
      );
      await tester.tap(find.byKey(const Key('submit-management-proof-review')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-payment-proof')));
      await tester.pumpAndSettle();
      expect(find.text('Retry same review'), findsOneWidget);
      await tester.tap(find.text('Retry same review'));
      await tester.pumpAndSettle();
      expect(submissions, hasLength(2));
      expect(submissions[1], submissions[0]);
      expect(submissions[0]['expected_version'], 2);
      expect(submissions[0]['expected_review_id'], isNull);
      await tester.drag(find.byType(Scrollable).first, const Offset(0, 1200));
      await tester.pumpAndSettle();
      expect(find.textContaining('No payment was posted'), findsWidgets);
    },
  );

  for (final status in [401, 403, 426]) {
    testWidgets(
      'Denied refresh $status clears borrower data and review controls',
      (tester) async {
        var denied = false;
        final repository = SpinaManagementPaymentProofRepository(
          client: MockClient((request) async {
            if (denied) return http.Response('Access unavailable', status);
            if (request.url.path.endsWith(_proofId)) return _ok(_detail());
            return _ok({
              'proofs': [_proof()],
              'has_more': false,
            });
          }),
        );
        await _pump(tester, repository);
        await tester.tap(find.byKey(const Key('management-proof-$_proofId')));
        await tester.pumpAndSettle();
        denied = true;
        await tester.tap(find.byTooltip('Refresh payment evidence'));
        await tester.pumpAndSettle();
        expect(find.textContaining('Borrower One'), findsNothing);
        expect(
          find.byKey(const Key('submit-management-proof-review')),
          findsNothing,
        );
      },
    );
  }
}

Future<void> _pump(
  WidgetTester tester,
  ManagementPaymentProofRepository repository, {
  Future<bool> Function(dynamic)? saver,
}) async {
  await tester.binding.setSurfaceSize(const Size(600, 1400));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  final store = MemoryDeviceIdentityStore()..value = 'device';
  await tester.pumpWidget(
    MaterialApp(
      home: ManagementPaymentProofsPage(
        session: _session,
        deviceIdentityProvider: DeviceIdentityProvider(
          store: store,
          platformResolver: () => 'android',
          appVersionResolver: () async => '1',
        ),
        repository: repository,
        saver: saver ?? (_) async => true,
      ),
    ),
  );
  await tester.pumpAndSettle();
}
