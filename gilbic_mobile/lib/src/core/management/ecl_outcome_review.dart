class EclOutcomeReviewQueueData {
  const EclOutcomeReviewQueueData({
    required this.summary,
    required this.episodes,
    required this.filter,
    required this.limit,
    required this.offset,
    required this.reviewPermission,
    required this.notice,
  });

  final EclOutcomeReviewSummary summary;
  final List<EclOutcomeReviewEpisode> episodes;
  final String filter;
  final int limit;
  final int offset;
  final bool reviewPermission;
  final String notice;

  factory EclOutcomeReviewQueueData.fromPayload(Map<String, dynamic> payload) {
    return EclOutcomeReviewQueueData(
      summary: EclOutcomeReviewSummary.fromPayload(_map(payload['summary'])),
      episodes: _list(payload['episodes'])
          .map((item) => EclOutcomeReviewEpisode.fromPayload(_map(item)))
          .toList(growable: false),
      filter: _text(payload['filter']) ?? 'pending',
      limit: _integer(payload['limit']) ?? 100,
      offset: _integer(payload['offset']) ?? 0,
      reviewPermission: payload['review_permission'] == true,
      notice: _text(payload['notice']) ??
          'Historical outcomes require explicit evidence-backed review.',
    );
  }
}

class EclOutcomeReviewSummary {
  const EclOutcomeReviewSummary({
    required this.episodeCount,
    required this.structurallyUsableCount,
    required this.sourceReviewRequiredCount,
    required this.pendingOutcomeReviewCount,
    required this.reviewedOutcomeCount,
    required this.reviewedDefaultCount,
    required this.reviewedNonDefaultCount,
    required this.reviewStatus,
    required this.eclIncluded,
    required this.eclAmount,
    required this.readyToPost,
  });

  final int episodeCount;
  final int structurallyUsableCount;
  final int sourceReviewRequiredCount;
  final int pendingOutcomeReviewCount;
  final int reviewedOutcomeCount;
  final int reviewedDefaultCount;
  final int reviewedNonDefaultCount;
  final String reviewStatus;
  final bool eclIncluded;
  final double? eclAmount;
  final bool readyToPost;

  factory EclOutcomeReviewSummary.fromPayload(Map<String, dynamic> payload) {
    return EclOutcomeReviewSummary(
      episodeCount: _integer(payload['episode_count']) ?? 0,
      structurallyUsableCount:
          _integer(payload['structurally_usable_count']) ?? 0,
      sourceReviewRequiredCount:
          _integer(payload['source_review_required_count']) ?? 0,
      pendingOutcomeReviewCount:
          _integer(payload['pending_outcome_review_count']) ?? 0,
      reviewedOutcomeCount: _integer(payload['reviewed_outcome_count']) ?? 0,
      reviewedDefaultCount: _integer(payload['reviewed_default_count']) ?? 0,
      reviewedNonDefaultCount:
          _integer(payload['reviewed_non_default_count']) ?? 0,
      reviewStatus: _text(payload['review_status']) ?? 'outcome_labeling_required',
      eclIncluded: payload['ecl_included'] == true,
      eclAmount: _number(payload['ecl_amount']),
      readyToPost: payload['ready_to_post'] == true,
    );
  }
}

class EclOutcomeReviewEpisode {
  const EclOutcomeReviewEpisode({
    required this.historicalEpisodeId,
    required this.episodeKey,
    required this.borrowerKey,
    required this.episodeSequence,
    required this.loanType,
    required this.sourceEvent,
    required this.releaseDate,
    required this.dueDate,
    required this.principal,
    required this.contractualTotal,
    required this.interestRate,
    required this.outcomeEvidence,
    required this.outcomeDate,
    required this.renewalRolloverAmount,
    required this.cashCollected,
    required this.positivePaymentCount,
    required this.zeroPaymentObservationCount,
    required this.observedCollectionDays,
    required this.sourceQualityStatus,
    required this.sourceQualityNote,
    required this.explicitDefaultLabel,
    required this.reviewId,
    required this.reviewVersion,
    required this.evidenceBasis,
    required this.evidenceReference,
    required this.reviewNote,
    required this.reviewerName,
    required this.reviewedAt,
    required this.reviewStatus,
  });

  final int historicalEpisodeId;
  final String episodeKey;
  final String borrowerKey;
  final int episodeSequence;
  final String loanType;
  final String sourceEvent;
  final DateTime? releaseDate;
  final DateTime? dueDate;
  final double principal;
  final double? contractualTotal;
  final double? interestRate;
  final String? outcomeEvidence;
  final DateTime? outcomeDate;
  final double? renewalRolloverAmount;
  final double cashCollected;
  final int positivePaymentCount;
  final int zeroPaymentObservationCount;
  final int observedCollectionDays;
  final String sourceQualityStatus;
  final String? sourceQualityNote;
  final bool? explicitDefaultLabel;
  final int? reviewId;
  final int? reviewVersion;
  final String? evidenceBasis;
  final String? evidenceReference;
  final String? reviewNote;
  final String? reviewerName;
  final DateTime? reviewedAt;
  final String reviewStatus;

  bool get sourceBlocked => sourceQualityStatus == 'source_review_required';
  bool get reviewed => explicitDefaultLabel != null;

  factory EclOutcomeReviewEpisode.fromPayload(Map<String, dynamic> payload) {
    return EclOutcomeReviewEpisode(
      historicalEpisodeId: _integer(payload['historical_episode_id']) ?? 0,
      episodeKey: _text(payload['episode_key']) ?? '',
      borrowerKey: _text(payload['borrower_key']) ?? '',
      episodeSequence: _integer(payload['episode_sequence']) ?? 0,
      loanType: _text(payload['loan_type']) ?? '',
      sourceEvent: _text(payload['source_event']) ?? '',
      releaseDate: _date(payload['release_date']),
      dueDate: _date(payload['due_date']),
      principal: _number(payload['principal']) ?? 0,
      contractualTotal: _number(payload['contractual_total']),
      interestRate: _number(payload['interest_rate']),
      outcomeEvidence: _text(payload['outcome_evidence']),
      outcomeDate: _date(payload['outcome_date']),
      renewalRolloverAmount: _number(payload['renewal_rollover_amount']),
      cashCollected: _number(payload['cash_collected']) ?? 0,
      positivePaymentCount: _integer(payload['positive_payment_count']) ?? 0,
      zeroPaymentObservationCount:
          _integer(payload['zero_payment_observation_count']) ?? 0,
      observedCollectionDays: _integer(payload['observed_collection_days']) ?? 0,
      sourceQualityStatus: _text(payload['source_quality_status']) ?? '',
      sourceQualityNote: _text(payload['source_quality_note']),
      explicitDefaultLabel: payload['explicit_default_label'] is bool
          ? payload['explicit_default_label'] as bool
          : null,
      reviewId: _integer(payload['review_id']),
      reviewVersion: _integer(payload['review_version']),
      evidenceBasis: _text(payload['evidence_basis']),
      evidenceReference: _text(payload['evidence_reference']),
      reviewNote: _text(payload['review_note']),
      reviewerName: _text(payload['reviewer_name']),
      reviewedAt: _date(payload['reviewed_at']),
      reviewStatus: _text(payload['review_status']) ?? 'outcome_review_required',
    );
  }
}

Map<String, dynamic> _map(Object? value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) {
    return value.map((key, item) => MapEntry(key.toString(), item));
  }
  return <String, dynamic>{};
}

List<Object?> _list(Object? value) => value is List ? value.cast<Object?>() : const [];

String? _text(Object? value) {
  if (value == null) return null;
  final text = value.toString().trim();
  return text.isEmpty ? null : text;
}

int? _integer(Object? value) {
  if (value is int) return value;
  return int.tryParse(value?.toString() ?? '');
}

double? _number(Object? value) {
  if (value is num) return value.toDouble();
  return double.tryParse(value?.toString() ?? '');
}

DateTime? _date(Object? value) {
  final text = _text(value);
  return text == null ? null : DateTime.tryParse(text);
}
