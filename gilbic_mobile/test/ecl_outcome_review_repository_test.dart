import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/ecl_outcome_review_repository.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('loads the controlled historical outcome-review queue', () async {
    late http.Request captured;
    final repository = SpinaEclOutcomeReviewRepository(
      client: MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode(<String, Object?>{
            'success': true,
            'data': <String, Object?>{
              'summary': _summary,
              'episodes': <Object?>[_episode],
              'filter': 'pending',
              'limit': 50,
              'offset': 0,
              'review_permission': true,
              'notice': 'Explicit evidence-backed review only.',
            },
          }),
          200,
          headers: const {'content-type': 'application/json'},
        );
      }),
    );

    final data = await repository.loadQueue(
      _session,
      deviceId: 'management-device',
      status: 'pending',
      limit: 50,
      offset: 0,
    );

    expect(captured.method, 'GET');
    expect(
      captured.url.path,
      '/api/mobile/v1/management/financial-accounting/ecl-outcome-review',
    );
    expect(captured.url.queryParameters['review_status'], 'pending');
    expect(captured.url.queryParameters['limit'], '50');
    expect(captured.headers['authorization'], 'Bearer management-token');
    expect(captured.headers['x-device-id'], 'management-device');
    expect(data.summary.episodeCount, 992);
    expect(data.summary.structurallyUsableCount, 919);
    expect(data.summary.eclIncluded, isFalse);
    expect(data.summary.eclAmount, isNull);
    expect(data.summary.readyToPost, isFalse);
    expect(data.episodes.single.historicalEpisodeId, 101);
    expect(data.reviewPermission, isTrue);
  });

  test('posts only an explicit evidence-backed reviewed outcome', () async {
    late http.Request captured;
    final repository = SpinaEclOutcomeReviewRepository(
      client: MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode(<String, Object?>{
            'success': true,
            'data': <String, Object?>{
              ..._episode,
              'explicit_default_label': false,
              'review_id': 7,
              'review_version': 1,
              'evidence_basis': 'collection_history',
              'evidence_reference': 'Ledger Jan-Apr 2025',
              'review_note': 'Evidence reviewed by Management.',
              'reviewer_name': 'Management',
              'reviewed_at': '2026-08-08T11:30:00+00:00',
              'review_status': 'outcome_reviewed',
            },
          }),
          200,
          headers: const {'content-type': 'application/json'},
        );
      }),
    );

    final reviewed = await repository.reviewOutcome(
      _session,
      deviceId: 'management-device',
      historicalEpisodeId: 101,
      defaultLabel: false,
      evidenceBasis: 'collection_history',
      evidenceReference: ' Ledger Jan-Apr 2025 ',
      reviewNote: ' Evidence reviewed by Management. ',
    );

    expect(captured.method, 'POST');
    expect(
      captured.url.path,
      '/api/mobile/v1/management/financial-accounting/ecl-outcome-review/101',
    );
    final body = jsonDecode(captured.body) as Map<String, dynamic>;
    expect(body, <String, Object>{
      'default_label': false,
      'evidence_basis': 'collection_history',
      'evidence_reference': 'Ledger Jan-Apr 2025',
      'review_note': 'Evidence reviewed by Management.',
    });
    expect(body.containsKey('loss_amount'), isFalse);
    expect(body.containsKey('recovery_amount'), isFalse);
    expect(body.containsKey('pd'), isFalse);
    expect(body.containsKey('lgd'), isFalse);
    expect(body.containsKey('ecl_amount'), isFalse);
    expect(reviewed.explicitDefaultLabel, isFalse);
    expect(reviewed.reviewVersion, 1);
  });
}

const _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>['accounting.ecl.review'],
);

const _summary = <String, Object?>{
  'episode_count': 992,
  'structurally_usable_count': 919,
  'source_review_required_count': 73,
  'pending_outcome_review_count': 919,
  'reviewed_outcome_count': 0,
  'reviewed_default_count': 0,
  'reviewed_non_default_count': 0,
  'review_status': 'outcome_labeling_required',
  'ecl_included': false,
  'ecl_amount': null,
  'ready_to_post': false,
};

const _episode = <String, Object?>{
  'historical_episode_id': 101,
  'episode_key': 'episode-regular-101',
  'borrower_key': 'abcdef0123456789abcdef0123456789',
  'episode_sequence': 1,
  'loan_type': 'regular',
  'source_event': 'snapshot',
  'release_date': '2025-01-01',
  'due_date': '2025-05-01',
  'principal': '5000.00',
  'contractual_total': '6000.00',
  'interest_rate': '20.00',
  'outcome_evidence': 'renewed',
  'outcome_date': '2025-05-02',
  'renewal_rollover_amount': '1000.00',
  'cash_collected': '6000.00',
  'positive_payment_count': 100,
  'zero_payment_observation_count': 5,
  'observed_collection_days': 105,
  'source_quality_status': 'ready_for_outcome_labeling',
  'source_quality_note': null,
  'explicit_default_label': null,
  'review_id': null,
  'review_version': null,
  'evidence_basis': null,
  'evidence_reference': null,
  'review_note': null,
  'reviewer_name': null,
  'reviewed_at': null,
  'review_status': 'outcome_review_required',
};
