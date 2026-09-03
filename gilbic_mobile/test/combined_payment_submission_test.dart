import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/combined_payment_submission.dart';
import 'package:gilbic_mobile/src/core/payments/combined_payment_submission_repository.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  CombinedPaymentSubmissionDraft draft({
    double cashReceivedAmount = 150,
    CombinedExtraAllocationChoice? extraChoice,
    String? reviewedAllocationHash,
    PastDueFollowupDraft? regularPastDueFollowup,
  }) {
    return CombinedPaymentSubmissionDraft(
      idempotencyKey: '11111111-1111-4111-8111-111111111111',
      clientId: '22222222-2222-4222-8222-222222222222',
      collectionDate: DateTime(2026, 8, 28),
      recordedAt: DateTime.utc(2026, 8, 28, 1),
      deviceId: 'collector-device',
      deviceSequence: 7,
      cashReceivedAmount: cashReceivedAmount,
      extraAllocationChoice: extraChoice,
      reviewedAllocationHash: reviewedAllocationHash,
      regularPastDueFollowup: regularPastDueFollowup,
      legs: const <CombinedPaymentLegDraft>[
        CombinedPaymentLegDraft(
          routeEntryId: '33333333-3333-4333-8333-333333333333',
          loanId: '33333333-3333-4333-8333-333333333333',
          routeRevision: 'loan:33333333-3333-4333-8333-333333333333:v2',
        ),
        CombinedPaymentLegDraft(
          routeEntryId: '44444444-4444-4444-8444-444444444444',
          loanId: '44444444-4444-4444-8444-444444444444',
          routeRevision: 'loan:44444444-4444-4444-8444-444444444444:v4',
        ),
      ],
    );
  }

  test(
    'combined draft sends one cash total and no client-computed leg amounts',
    () {
      final value = draft();

      expect(value.validate(), isNull);
      final payload = value.toJson();
      expect(payload['cash_received_amount'], 150);
      final legs = payload['legs']! as List<Object?>;
      expect(legs, hasLength(2));
      expect(
        (legs.first! as Map<String, Object?>).containsKey('amount'),
        isFalse,
      );
    },
  );

  test('combined draft rejects cash finer than one cent', () {
    expect(
      draft(cashReceivedAmount: 150.001).validate(),
      'Enter the cash received using pesos and cents only.',
    );
  });

  test(
    'combined draft preserves reviewed extra choice and Regular follow-up',
    () {
      final reviewedHash = List<String>.filled(64, 'a').join();
      final value = draft(
        cashReceivedAmount: 170,
        extraChoice: CombinedExtraAllocationChoice.regularPrincipalReduction,
        reviewedAllocationHash: reviewedHash,
        regularPastDueFollowup: const PastDueFollowupDraft(
          reasonCode: PastDueReasonCode.businessSlow,
          note: 'Partial Regular amount after the 7x7 obligation.',
        ),
      );

      final payload = value.toJson();
      expect(payload['extra_allocation_choice'], 'regular_principal_reduction');
      expect(payload['reviewed_allocation_hash'], reviewedHash);
      expect(
        (payload['regular_past_due_followup']!
            as Map<String, Object?>)['reason_code'],
        'business_slow',
      );
    },
  );

  test('allocation preview parses the server split and review gates', () {
    final allocationHash = List<String>.filled(64, 'b').join();
    final preview = CombinedPaymentAllocationPreview.fromPayload(
      <String, Object?>{
        'status': 'short',
        'requires_review': true,
        'allocation_hash': allocationHash,
        'cash_received_amount': '80.00',
        'expected_total_amount': '150.00',
        'short_amount': '70.00',
        'extra_amount': '0.00',
        'extra_choice_required': false,
        'regular_past_due_followup_required': true,
        'message': 'Review the server split.',
        'legs': <Object?>[
          <String, Object?>{
            'loan_id': 'seven',
            'loan_type': 'seven_by_seven',
            'scheduled_amount': '50.00',
            'extra_amount': '0.00',
            'total_amount': '50.00',
            'projected_covered_dates': <String>['2026-08-24', '2026-08-25'],
          },
          <String, Object?>{
            'loan_id': 'regular',
            'loan_type': 'regular',
            'scheduled_amount': '30.00',
            'extra_amount': '0.00',
            'total_amount': '30.00',
          },
        ],
      },
    );

    expect(preview.status, 'short');
    expect(preview.requiresReview, isTrue);
    expect(preview.regularPastDueFollowupRequired, isTrue);
    expect(preview.sevenBySevenLeg.scheduledAmount, 50);
    expect(preview.sevenBySevenLeg.projectedCoveredDates, <String>[
      '2026-08-24',
      '2026-08-25',
    ]);
    expect(preview.regularLeg.scheduledAmount, 30);
  });

  test('repository requests server preview before submission', () async {
    late http.Request captured;
    final repository = SpinaCombinedPaymentSubmissionRepository(
      previewUri: Uri.parse('https://api.example.test/combined/preview'),
      submissionUri: Uri.parse('https://api.example.test/combined'),
      client: MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode(<String, Object?>{
            'success': true,
            'data': <String, Object?>{
              'status': 'exact',
              'requires_review': false,
              'allocation_hash': List<String>.filled(64, 'c').join(),
              'cash_received_amount': '150.00',
              'expected_total_amount': '150.00',
              'short_amount': '0.00',
              'extra_amount': '0.00',
              'extra_choice_required': false,
              'regular_past_due_followup_required': false,
              'message': 'Exact.',
              'legs': <Object?>[
                <String, Object?>{
                  'loan_id': 'seven',
                  'loan_type': 'seven_by_seven',
                  'scheduled_amount': '50.00',
                  'extra_amount': '0.00',
                  'total_amount': '50.00',
                },
                <String, Object?>{
                  'loan_id': 'regular',
                  'loan_type': 'regular',
                  'scheduled_amount': '100.00',
                  'extra_amount': '0.00',
                  'total_amount': '100.00',
                },
              ],
            },
          }),
          200,
        );
      }),
    );

    final preview = await repository.preview(_session, draft());

    expect(captured.url.path, '/combined/preview');
    expect(captured.headers['idempotency-key'], draft().idempotencyKey);
    expect(
      (jsonDecode(captured.body)
          as Map<String, dynamic>)['cash_received_amount'],
      150,
    );
    expect(preview.status, 'exact');
  });

  test('submission result preserves unallocated cash custody evidence', () {
    final result = CombinedPaymentSubmissionResult.fromPayload(
      <String, Object?>{
        'status': 'accepted',
        'duplicate': false,
        'client_transaction_id': 'combined-1',
        'client_id': 'client-1',
        'total_amount': '150.00',
        'applied_total_amount': '140.00',
        'unallocated_total_amount': '10.00',
        'cash_allocation_state': 'needs_review',
        'message': '10.00 remains unallocated and needs custody review.',
        'legs': <Object?>[
          <String, Object?>{
            'loan_id': 'regular',
            'transaction_id': 'tx-1',
            'receipt_number': 'R-1',
            'official_balance': '0.00',
            'amount': '150.00',
            'applied_amount': '140.00',
            'unallocated_amount': '10.00',
            'allocation_state': 'partially_allocated',
            'result': <String, Object?>{'adjustment_id': 'adjustment-1'},
          },
        ],
      },
    );

    expect(result.requiresCashCustodyReview, isTrue);
    expect(result.appliedTotalAmount, 140);
    expect(result.unallocatedTotalAmount, 10);
    expect(result.legs.single.unallocatedAmount, 10);
    expect(result.legs.single.protectedResult['adjustment_id'], 'adjustment-1');
  });

  test('submission result rejects contradictory cash allocation evidence', () {
    expect(
      () => CombinedPaymentSubmissionResult.fromPayload(<String, Object?>{
        'status': 'accepted',
        'duplicate': false,
        'client_transaction_id': 'combined-1',
        'client_id': 'client-1',
        'total_amount': '150.00',
        'applied_total_amount': '140.00',
        'unallocated_total_amount': '10.00',
        'cash_allocation_state': 'fully_allocated',
        'legs': <Object?>[],
      }),
      throwsA(isA<SpinaApiException>()),
    );
  });
}

const UserSession _session = UserSession(
  userId: 'collector-1',
  username: 'collector.one',
  displayName: 'Collector One',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'session-token',
  permissions: <String>['collection.create'],
);
