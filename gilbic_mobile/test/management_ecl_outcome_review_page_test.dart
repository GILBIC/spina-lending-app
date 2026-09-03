import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/ecl_outcome_review.dart';
import 'package:gilbic_mobile/src/core/management/ecl_outcome_review_repository.dart';
import 'package:gilbic_mobile/src/features/management/management_ecl_outcome_review_page.dart';

void main() {
  testWidgets('Management reviews an outcome only with explicit evidence', (
    tester,
  ) async {
    final repository = _FakeRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementEclOutcomeReviewPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Historical Outcome Review'), findsOneWidget);
    expect(find.byKey(const Key('ecl-outcome-review-summary')), findsOneWidget);
    expect(
      find.text('Historical credit-outcome review progress'),
      findsOneWidget,
    );
    expect(find.text('Ready for evidence review'), findsOneWidget);
    expect(find.textContaining('Stage 5E.4'), findsNothing);
    expect(find.text('Ready to post'), findsNothing);
    expect(find.text('992'), findsOneWidget);
    expect(find.text('919'), findsWidgets);
    expect(find.text('73'), findsOneWidget);
    expect(find.text('Not calculated'), findsOneWidget);
    expect(repository.deviceId, 'management-device');

    final pendingCard = find.byKey(const Key('ecl-outcome-review-101'));
    await tester.scrollUntilVisible(pendingCard, 250);
    await tester.tap(pendingCard);
    await tester.pumpAndSettle();

    final reviewButton = find.byKey(const Key('review-outcome-101'));
    await tester.ensureVisible(reviewButton);
    await tester.pumpAndSettle();
    await tester.tap(reviewButton);
    await tester.pumpAndSettle();

    final save = find.byKey(const Key('save-ecl-outcome-review'));
    expect(tester.widget<FilledButton>(save).onPressed, isNull);

    await tester.tap(find.text('Non-default'));
    await tester.enterText(
      find.byKey(const Key('ecl-evidence-reference')),
      'Collection ledger Jan-Apr 2025',
    );
    await tester.enterText(
      find.byKey(const Key('ecl-review-note')),
      'Reviewed collections show the historical obligation was fully settled.',
    );
    await tester.pump();
    expect(tester.widget<FilledButton>(save).onPressed, isNotNull);

    await tester.tap(save);
    await tester.pumpAndSettle();

    expect(
      find.byKey(const Key('management-review-ecl-outcome-review')),
      findsOneWidget,
    );
    expect(
      find.text(
        'A new immutable historical outcome-review version will be saved. '
        'This does not calculate loss, recovery, PD, LGD or ECL and does not '
        'post to the General Ledger.',
      ),
      findsOneWidget,
    );
    expect(repository.reviewedEpisodeId, isNull);

    await tester.tap(find.byKey(const Key('cancel-ecl-outcome-review')));
    await tester.pumpAndSettle();
    expect(repository.reviewedEpisodeId, isNull);

    await tester.tap(reviewButton);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Non-default'));
    await tester.enterText(
      find.byKey(const Key('ecl-evidence-reference')),
      'Collection ledger Jan-Apr 2025',
    );
    await tester.enterText(
      find.byKey(const Key('ecl-review-note')),
      'Reviewed collections show the historical obligation was fully settled.',
    );
    await tester.pump();
    final secondSave = find.byKey(const Key('save-ecl-outcome-review'));
    expect(tester.widget<FilledButton>(secondSave).onPressed, isNotNull);
    await tester.tap(secondSave);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('confirm-ecl-outcome-review')));
    await tester.pumpAndSettle();

    expect(repository.reviewedEpisodeId, 101);
    expect(repository.defaultLabel, isFalse);
    expect(repository.evidenceBasis, 'source_document');
    expect(repository.evidenceReference, 'Collection ledger Jan-Apr 2025');
    expect(
      repository.reviewNote,
      'Reviewed collections show the historical obligation was fully settled.',
    );
  });

  testWidgets('source-review episodes cannot be labeled', (tester) async {
    final repository = _FakeRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementEclOutcomeReviewPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('ecl-filter-source_review')));
    await tester.pumpAndSettle();
    expect(repository.lastStatus, 'source_review');

    final blockedCard = find.byKey(const Key('ecl-outcome-review-202'));
    await tester.scrollUntilVisible(blockedCard, 250);
    await tester.tap(blockedCard);
    await tester.pumpAndSettle();

    expect(
      find.byKey(const Key('management-review-ecl-outcome-review')),
      findsOneWidget,
    );
    expect(
      find.bySemanticsLabel(
        'Blocker: This reconstructed episode requires source review before outcome labeling.',
      ),
      findsOneWidget,
    );
    expect(find.textContaining('requires source review'), findsOneWidget);
    expect(find.byKey(const Key('review-outcome-202')), findsNothing);
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

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'management-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

class _FakeRepository implements EclOutcomeReviewRepository {
  String? deviceId;
  String? lastStatus;
  int? reviewedEpisodeId;
  bool? defaultLabel;
  String? evidenceBasis;
  String? evidenceReference;
  String? reviewNote;

  @override
  Future<EclOutcomeReviewQueueData> loadQueue(
    UserSession session, {
    required String deviceId,
    String status = 'pending',
    int limit = 100,
    int offset = 0,
  }) async {
    this.deviceId = deviceId;
    lastStatus = status;
    return EclOutcomeReviewQueueData(
      summary: const EclOutcomeReviewSummary(
        episodeCount: 992,
        structurallyUsableCount: 919,
        sourceReviewRequiredCount: 73,
        pendingOutcomeReviewCount: 919,
        reviewedOutcomeCount: 0,
        reviewedDefaultCount: 0,
        reviewedNonDefaultCount: 0,
        reviewStatus: 'outcome_labeling_required',
        eclIncluded: false,
        eclAmount: null,
        readyToPost: false,
      ),
      episodes: status == 'source_review'
          ? <EclOutcomeReviewEpisode>[_sourceBlocked]
          : <EclOutcomeReviewEpisode>[_pending],
      filter: status,
      limit: limit,
      offset: offset,
      reviewPermission: true,
      notice:
          'Historical outcomes require explicit evidence-backed review. Renewal, archive, deletion, cash totals and arrears are not automatic labels.',
    );
  }

  @override
  Future<EclOutcomeReviewEpisode> reviewOutcome(
    UserSession session, {
    required String deviceId,
    required int historicalEpisodeId,
    required bool defaultLabel,
    required String evidenceBasis,
    required String evidenceReference,
    required String reviewNote,
  }) async {
    this.deviceId = deviceId;
    reviewedEpisodeId = historicalEpisodeId;
    this.defaultLabel = defaultLabel;
    this.evidenceBasis = evidenceBasis;
    this.evidenceReference = evidenceReference;
    this.reviewNote = reviewNote;
    return _pending;
  }
}

final _pending = EclOutcomeReviewEpisode(
  historicalEpisodeId: 101,
  episodeKey: 'episode-regular-101',
  borrowerKey: 'abcdef0123456789abcdef0123456789',
  episodeSequence: 1,
  loanType: 'regular',
  sourceEvent: 'snapshot',
  releaseDate: DateTime(2025, 1, 1),
  dueDate: DateTime(2025, 5, 1),
  principal: 5000,
  contractualTotal: 6000,
  interestRate: 20,
  outcomeEvidence: 'renewed',
  outcomeDate: DateTime(2025, 5, 2),
  renewalRolloverAmount: 1000,
  cashCollected: 6000,
  positivePaymentCount: 100,
  zeroPaymentObservationCount: 5,
  observedCollectionDays: 105,
  sourceQualityStatus: 'ready_for_outcome_labeling',
  sourceQualityNote: null,
  explicitDefaultLabel: null,
  reviewId: null,
  reviewVersion: null,
  evidenceBasis: null,
  evidenceReference: null,
  reviewNote: null,
  reviewerName: null,
  reviewedAt: null,
  reviewStatus: 'outcome_review_required',
);

final _sourceBlocked = EclOutcomeReviewEpisode(
  historicalEpisodeId: 202,
  episodeKey: 'episode-7x7-202',
  borrowerKey: '1234567890abcdef1234567890abcdef',
  episodeSequence: 2,
  loanType: '7x7',
  sourceEvent: 'renew',
  releaseDate: DateTime(2025, 2, 1),
  dueDate: DateTime(2025, 6, 1),
  principal: 7000,
  contractualTotal: null,
  interestRate: null,
  outcomeEvidence: 'archived',
  outcomeDate: null,
  renewalRolloverAmount: null,
  cashCollected: 4200,
  positivePaymentCount: 20,
  zeroPaymentObservationCount: 8,
  observedCollectionDays: 28,
  sourceQualityStatus: 'source_review_required',
  sourceQualityNote:
      'This reconstructed episode requires source review before outcome labeling.',
  explicitDefaultLabel: null,
  reviewId: null,
  reviewVersion: null,
  evidenceBasis: null,
  evidenceReference: null,
  reviewNote: null,
  reviewerName: null,
  reviewedAt: null,
  reviewStatus: 'source_review_required',
);
