import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/combined_payment_submission.dart';
import 'package:gilbic_mobile/src/core/payments/combined_payment_submission_repository.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  final draft = CombinedPaymentSubmissionDraft(
    idempotencyKey: '11111111-1111-4111-8111-111111111111',
    clientId: '22222222-2222-4222-8222-222222222222',
    collectionDate: DateTime(2026, 8, 28),
    recordedAt: DateTime.utc(2026, 8, 28),
    deviceId: 'synthetic-device',
    deviceSequence: 1,
    cashReceivedAmount: '150.00',
    legs: const [
      CombinedPaymentLegDraft(
        routeEntryId: '33333333-3333-4333-8333-333333333333',
        loanId: '33333333-3333-4333-8333-333333333333',
        routeRevision: 'r1',
      ),
      CombinedPaymentLegDraft(
        routeEntryId: '44444444-4444-4444-8444-444444444444',
        loanId: '44444444-4444-4444-8444-444444444444',
        routeRevision: 'r2',
      ),
    ],
  );
  final canonical = <String, Object?>{
    'status': 'accepted',
    'duplicate': false,
    'client_transaction_id': draft.idempotencyKey,
    'client_id': draft.clientId,
    'total_amount': '150.00',
    'legs': [
      {
        'loan_id': draft.legs[0].loanId,
        'transaction_id': 'tx1',
        'receipt_number': 'receipt1',
        'official_balance': '1000.00',
        'applied_amount': '50.00',
      },
      {
        'loan_id': draft.legs[1].loanId,
        'transaction_id': 'tx2',
        'receipt_number': 'receipt2',
        'official_balance': '2000.00',
        'applied_amount': '100.00',
      },
    ],
  };
  final baseLegs = (canonical['legs']! as List).cast<Map<String, String>>();
  final hash = 'a' * 64;
  CombinedPaymentSubmissionDraft reviewed({
    bool short = false,
    bool extra = false,
  }) => draft.withAllocationReview(
    cashReceivedAmount: short
        ? '50.00'
        : extra
        ? '170.00'
        : '150.00',
    reviewedAllocationHash: hash,
    extraAllocationChoice: extra
        ? CombinedExtraAllocationChoice.sevenBySevenAdvance
        : null,
    preview: CombinedPaymentAllocationPreview.fromPayload({
      'status': short
          ? 'short'
          : extra
          ? 'extra'
          : 'exact',
      'requires_review': short || extra,
      'allocation_hash': hash,
      'cash_received_amount': short
          ? '50.00'
          : extra
          ? '170.00'
          : '150.00',
      'expected_total_amount': '150.00',
      'short_amount': short ? '100.00' : '0.00',
      'extra_amount': extra ? '20.00' : '0.00',
      'extra_choice_required': false,
      'regular_past_due_followup_required': short,
      'legs': [
        {
          'loan_id': draft.legs[0].loanId,
          'loan_type': 'seven_by_seven',
          'scheduled_amount': '50.00',
          'extra_amount': extra ? '20.00' : '0.00',
          'total_amount': extra ? '70.00' : '50.00',
        },
        {
          'loan_id': draft.legs[1].loanId,
          'loan_type': 'regular',
          'scheduled_amount': short ? '0.00' : '100.00',
          'extra_amount': '0.00',
          'total_amount': short ? '0.00' : '100.00',
        },
      ],
    }),
  );
  final reviewedPayload = {
    ...canonical,
    'allocation_hash': hash,
    'legs': [
      {...baseLegs[0], 'allocation_component': 'seven_by_seven_scheduled'},
      {...baseLegs[1], 'allocation_component': 'regular_scheduled'},
    ],
  };
  final reviewedLegs = (reviewedPayload['legs'] as List)
      .cast<Map<String, String>>();
  for (final entry in <String, Map<String, Object?>>{
    'missing reviewed component': {
      ...reviewedPayload,
      'legs': [
        {...reviewedLegs.first, 'applied_amount': '150.00'},
      ],
    },
    'shifted reviewed amounts': {
      ...reviewedPayload,
      'legs': [
        {...reviewedLegs.first, 'applied_amount': '100.00'},
        {...reviewedLegs.last, 'applied_amount': '50.00'},
      ],
    },
    'wrong reviewed hash': {...reviewedPayload, 'allocation_hash': 'b' * 64},
    'duplicate receipt': {
      ...reviewedPayload,
      'legs': [
        reviewedLegs.first,
        {...reviewedLegs.last, 'receipt_number': 'receipt1'},
      ],
    },
    'unexpected extra component': {
      ...reviewedPayload,
      'legs': [
        reviewedLegs.first,
        {
          ...reviewedLegs.last,
          'allocation_component': 'regular_scheduled_and_extra',
        },
      ],
    },
  }.entries) {
    test('reviewed acknowledgment rejects ${entry.key} as uncertain', () async {
      final repository = SpinaCombinedPaymentSubmissionRepository(
        client: MockClient(
          (_) async => http.Response(
            jsonEncode({'success': true, 'data': entry.value}),
            200,
          ),
        ),
      );
      await expectLater(
        repository.submit(session, reviewed()),
        throwsA(
          isA<SpinaApiException>().having(
            (e) => e.statusCode,
            'uncertain',
            isNull,
          ),
        ),
      );
    });
  }
  for (final count in [1, 2, 3]) {
    test(
      'reviewed acknowledgment accepts exact $count receipt components',
      () async {
        final payload = {
          ...reviewedPayload,
          'total_amount': count == 1
              ? '50.00'
              : count == 3
              ? '170.00'
              : '150.00',
          'extra_allocation_choice': count == 3
              ? 'seven_by_seven_advance'
              : null,
          'legs': [
            reviewedLegs.first,
            if (count > 1) reviewedLegs.last,
            if (count == 3)
              {
                ...reviewedLegs.first,
                'transaction_id': 'tx3',
                'receipt_number': 'receipt3',
                'applied_amount': '20.00',
                'allocation_component': 'seven_by_seven_advance',
              },
          ],
        };
        final repository = SpinaCombinedPaymentSubmissionRepository(
          client: MockClient(
            (_) async => http.Response(
              jsonEncode({'success': true, 'data': payload}),
              200,
            ),
          ),
        );
        expect(
          (await repository.submit(
            session,
            reviewed(short: count == 1, extra: count == 3),
          )).receiptNumbers,
          hasLength(count),
        );
      },
    );
  }
  for (final entry in <String, Map<String, Object?>>{
    'foreign command': {...canonical, 'client_transaction_id': 'foreign'},
    'foreign borrower': {...canonical, 'client_id': 'foreign'},
    'empty receipt legs': {...canonical, 'legs': []},
    'wrong amount': {...canonical, 'total_amount': '999.00'},
    'contradictory duplicate': {...canonical, 'duplicate': true},
  }.entries) {
    test('combined result rejects ${entry.key}', () async {
      final repository = SpinaCombinedPaymentSubmissionRepository(
        client: MockClient(
          (_) async => http.Response(
            jsonEncode({'success': true, 'data': entry.value}),
            200,
          ),
        ),
      );
      await expectLater(
        repository.submit(session, draft),
        throwsA(isA<SpinaApiException>()),
      );
    });
  }
  test('valid combined result control', () async {
    final repository = SpinaCombinedPaymentSubmissionRepository(
      client: MockClient(
        (_) async => http.Response(
          jsonEncode({'success': true, 'data': canonical}),
          200,
        ),
      ),
    );
    expect((await repository.submit(session, draft)).isFinalSuccess, isTrue);
  });
  test('malformed combined HTTP200 remains uncertain', () async {
    final repository = SpinaCombinedPaymentSubmissionRepository(
      client: MockClient((_) async => http.Response('invalid json', 200)),
    );
    await expectLater(
      repository.submit(session, draft),
      throwsA(
        isA<SpinaApiException>().having(
          (e) => e.statusCode,
          'uncertain status',
          isNull,
        ),
      ),
    );
  });
}

const session = UserSession(
  userId: 'collector-1',
  username: 'test',
  displayName: 'Synthetic',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'synthetic',
  permissions: ['collection.create'],
);
