import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission.dart';

enum CombinedExtraAllocationChoice {
  sevenBySevenAdvance('seven_by_seven_advance', '7x7 Advance'),
  sevenBySevenExtraPrincipal(
    'seven_by_seven_extra_principal',
    '7x7 Extra Principal',
  ),
  regularAdvance('regular_advance', 'Regular Advance'),
  regularPrincipalReduction(
    'regular_principal_reduction',
    'Regular Principal Reduction',
  );

  const CombinedExtraAllocationChoice(this.apiValue, this.label);

  final String apiValue;
  final String label;
}

class CombinedPaymentLegDraft {
  const CombinedPaymentLegDraft({
    required this.routeEntryId,
    required this.loanId,
    required this.routeRevision,
  });

  final String routeEntryId;
  final String loanId;
  final String routeRevision;

  Map<String, Object?> toJson() => <String, Object?>{
    'route_entry_id': routeEntryId,
    'loan_id': loanId,
    'route_revision': routeRevision,
  };
}

class CombinedPaymentSubmissionDraft {
  const CombinedPaymentSubmissionDraft({
    required this.idempotencyKey,
    required this.clientId,
    required this.collectionDate,
    required this.recordedAt,
    required this.deviceId,
    required this.deviceSequence,
    required this.cashReceivedAmount,
    required this.legs,
    this.extraAllocationChoice,
    this.reviewedAllocationHash,
    this.regularPastDueFollowup,
  });

  final String idempotencyKey;
  final String clientId;
  final DateTime collectionDate;
  final DateTime recordedAt;
  final String deviceId;
  final int deviceSequence;
  final double cashReceivedAmount;
  final List<CombinedPaymentLegDraft> legs;
  final CombinedExtraAllocationChoice? extraAllocationChoice;
  final String? reviewedAllocationHash;
  final PastDueFollowupDraft? regularPastDueFollowup;

  CombinedPaymentSubmissionDraft withAllocationReview({
    required double cashReceivedAmount,
    CombinedExtraAllocationChoice? extraAllocationChoice,
    String? reviewedAllocationHash,
    PastDueFollowupDraft? regularPastDueFollowup,
  }) {
    return CombinedPaymentSubmissionDraft(
      idempotencyKey: idempotencyKey,
      clientId: clientId,
      collectionDate: collectionDate,
      recordedAt: recordedAt,
      deviceId: deviceId,
      deviceSequence: deviceSequence,
      cashReceivedAmount: cashReceivedAmount,
      legs: legs,
      extraAllocationChoice: extraAllocationChoice,
      reviewedAllocationHash: reviewedAllocationHash,
      regularPastDueFollowup: regularPastDueFollowup,
    );
  }

  String? validate() {
    if (idempotencyKey.trim().isEmpty || clientId.trim().isEmpty) {
      return 'A combined payment identifier and client are required.';
    }
    if (deviceId.trim().isEmpty || deviceSequence < 1) {
      return 'A valid device identity and sequence are required.';
    }
    if (!cashReceivedAmount.isFinite || cashReceivedAmount <= 0) {
      return 'Enter the total cash received from the client.';
    }
    final cashInCents = cashReceivedAmount * 100;
    if ((cashInCents - cashInCents.roundToDouble()).abs() > 0.000001) {
      return 'Enter the cash received using pesos and cents only.';
    }
    final reviewedHash = reviewedAllocationHash?.trim();
    if (reviewedHash != null &&
        (reviewedHash.length != 64 ||
            !RegExp(r'^[0-9a-f]{64}$').hasMatch(reviewedHash))) {
      return 'The reviewed server allocation is invalid. Preview the payment again.';
    }
    if (regularPastDueFollowup != null) {
      final followupError = regularPastDueFollowup!.validate(
        collectionDate: collectionDate,
      );
      if (followupError != null) {
        return followupError;
      }
    }
    if (legs.length != 2) {
      return 'Combined Pay requires exactly one Regular loan and one 7x7 loan.';
    }
    final ids = <String>{};
    for (final leg in legs) {
      if (leg.routeEntryId.trim().isEmpty ||
          leg.loanId.trim().isEmpty ||
          leg.routeRevision.trim().isEmpty) {
        return 'Every combined payment loan needs a valid route and revision.';
      }
      if (!ids.add(leg.loanId)) {
        return 'Combined payment loans must be different.';
      }
    }
    return null;
  }

  Map<String, Object?> toJson() => <String, Object?>{
    'client_transaction_id': idempotencyKey,
    'client_id': clientId,
    'collection_date': _date(collectionDate),
    'recorded_at': recordedAt.toUtc().toIso8601String(),
    'device_id': deviceId,
    'device_sequence': deviceSequence,
    'cash_received_amount': cashReceivedAmount,
    if (extraAllocationChoice != null)
      'extra_allocation_choice': extraAllocationChoice!.apiValue,
    if (reviewedAllocationHash != null)
      'reviewed_allocation_hash': reviewedAllocationHash!.trim(),
    if (regularPastDueFollowup != null)
      'regular_past_due_followup': regularPastDueFollowup!.toJson(),
    'legs': legs.map((leg) => leg.toJson()).toList(growable: false),
  };
}

class CombinedPaymentAllocationLeg {
  const CombinedPaymentAllocationLeg({
    required this.loanId,
    required this.loanType,
    required this.scheduledAmount,
    required this.extraAmount,
    required this.totalAmount,
    this.projectedCoveredDates = const <String>[],
  });

  final String loanId;
  final String loanType;
  final double scheduledAmount;
  final double extraAmount;
  final double totalAmount;
  final List<String> projectedCoveredDates;

  factory CombinedPaymentAllocationLeg.fromPayload(
    Map<String, dynamic> payload,
  ) {
    final rawDates = payload['projected_covered_dates'];
    final projectedDates = rawDates is List
        ? rawDates
              .map((value) => value.toString().trim())
              .where((value) => value.isNotEmpty)
              .toList(growable: false)
        : const <String>[];
    return CombinedPaymentAllocationLeg(
      loanId: _requiredString(payload, 'loan_id'),
      loanType: _requiredString(payload, 'loan_type').toLowerCase(),
      scheduledAmount: _requiredDouble(payload, 'scheduled_amount'),
      extraAmount: _requiredDouble(payload, 'extra_amount'),
      totalAmount: _requiredDouble(payload, 'total_amount'),
      projectedCoveredDates: projectedDates,
    );
  }
}

class CombinedPaymentAllocationPreview {
  const CombinedPaymentAllocationPreview({
    required this.status,
    required this.requiresReview,
    required this.allocationHash,
    required this.cashReceivedAmount,
    required this.expectedTotalAmount,
    required this.shortAmount,
    required this.extraAmount,
    required this.extraChoiceRequired,
    required this.regularPastDueFollowupRequired,
    required this.legs,
    required this.message,
  });

  final String status;
  final bool requiresReview;
  final String allocationHash;
  final double cashReceivedAmount;
  final double expectedTotalAmount;
  final double shortAmount;
  final double extraAmount;
  final bool extraChoiceRequired;
  final bool regularPastDueFollowupRequired;
  final List<CombinedPaymentAllocationLeg> legs;
  final String message;

  CombinedPaymentAllocationLeg get sevenBySevenLeg =>
      legs.firstWhere((leg) => leg.loanType == 'seven_by_seven');

  CombinedPaymentAllocationLeg get regularLeg =>
      legs.firstWhere((leg) => leg.loanType == 'regular');

  factory CombinedPaymentAllocationPreview.fromPayload(Object? value) {
    final payload = stringMap(value);
    final rawLegs = payload['legs'];
    if (rawLegs is! List) {
      throw const SpinaApiException(
        'The SPINA server returned an incomplete combined allocation preview.',
        code: 'invalid_combined_payment_preview',
      );
    }
    final legs = rawLegs
        .map(
          (item) => CombinedPaymentAllocationLeg.fromPayload(stringMap(item)),
        )
        .toList(growable: false);
    if (legs.length != 2 ||
        legs.where((leg) => leg.loanType == 'seven_by_seven').length != 1 ||
        legs.where((leg) => leg.loanType == 'regular').length != 1) {
      throw const SpinaApiException(
        'The SPINA server returned an invalid Regular + 7x7 preview.',
        code: 'invalid_combined_payment_preview',
      );
    }
    return CombinedPaymentAllocationPreview(
      status: _requiredString(payload, 'status').toLowerCase(),
      requiresReview: payload['requires_review'] == true,
      allocationHash: _requiredString(payload, 'allocation_hash'),
      cashReceivedAmount: _requiredDouble(payload, 'cash_received_amount'),
      expectedTotalAmount: _requiredDouble(payload, 'expected_total_amount'),
      shortAmount: _requiredDouble(payload, 'short_amount'),
      extraAmount: _requiredDouble(payload, 'extra_amount'),
      extraChoiceRequired: payload['extra_choice_required'] == true,
      regularPastDueFollowupRequired:
          payload['regular_past_due_followup_required'] == true,
      legs: legs,
      message:
          firstNonEmptyString(<Object?>[payload['message']]) ??
          'Review the server allocation before saving.',
    );
  }
}

class CombinedPaymentLegResult {
  const CombinedPaymentLegResult({
    required this.loanId,
    required this.transactionId,
    required this.receiptNumber,
    required this.officialBalance,
    required this.appliedAmount,
    required this.unallocatedAmount,
    required this.allocationState,
    required this.protectedResult,
    this.routeRevision,
  });

  final String loanId;
  final String transactionId;
  final String receiptNumber;
  final double officialBalance;
  final double appliedAmount;
  final double unallocatedAmount;
  final String allocationState;
  final Map<String, dynamic> protectedResult;
  final String? routeRevision;

  factory CombinedPaymentLegResult.fromPayload(Map<String, dynamic> payload) {
    return CombinedPaymentLegResult(
      loanId: _requiredString(payload, 'loan_id'),
      transactionId: _requiredString(payload, 'transaction_id'),
      receiptNumber: _requiredString(payload, 'receipt_number'),
      officialBalance: _requiredDouble(payload, 'official_balance'),
      appliedAmount:
          _optionalDouble(payload, 'applied_amount') ??
          _optionalDouble(payload, 'amount') ??
          0,
      unallocatedAmount: _optionalDouble(payload, 'unallocated_amount') ?? 0,
      allocationState:
          firstNonEmptyString(<Object?>[payload['allocation_state']]) ??
          'fully_allocated',
      protectedResult: stringMap(payload['result']),
      routeRevision: firstNonEmptyString(<Object?>[payload['route_revision']]),
    );
  }
}

class CombinedPaymentSubmissionResult {
  const CombinedPaymentSubmissionResult({
    required this.status,
    required this.duplicate,
    required this.idempotencyKey,
    required this.clientId,
    required this.totalAmount,
    required this.appliedTotalAmount,
    required this.unallocatedTotalAmount,
    required this.cashAllocationState,
    required this.legs,
    required this.message,
  });

  final String status;
  final bool duplicate;
  final String idempotencyKey;
  final String clientId;
  final double totalAmount;
  final double appliedTotalAmount;
  final double unallocatedTotalAmount;
  final String cashAllocationState;
  final List<CombinedPaymentLegResult> legs;
  final String message;

  bool get isFinalSuccess => status == 'accepted' || status == 'duplicate';

  bool get requiresCashCustodyReview =>
      cashAllocationState == 'needs_review' || unallocatedTotalAmount > 0;

  List<String> get receiptNumbers =>
      legs.map((leg) => leg.receiptNumber).toList(growable: false);

  factory CombinedPaymentSubmissionResult.fromPayload(Object? value) {
    final payload = stringMap(value);
    final rawLegs = payload['legs'];
    if (rawLegs is! List) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete combined payment data.',
        code: 'invalid_combined_payment_payload',
      );
    }
    final totalAmount = _requiredDouble(payload, 'total_amount');
    final unallocatedTotal =
        _optionalDouble(payload, 'unallocated_total_amount') ?? 0;
    final appliedTotal =
        _optionalDouble(payload, 'applied_total_amount') ??
        (totalAmount - unallocatedTotal);
    final allocationState =
        firstNonEmptyString(<Object?>[payload['cash_allocation_state']]) ??
        (unallocatedTotal > 0 ? 'needs_review' : 'fully_allocated');
    if (totalAmount < 0 ||
        appliedTotal < 0 ||
        unallocatedTotal < 0 ||
        (appliedTotal + unallocatedTotal - totalAmount).abs() > 0.001 ||
        (allocationState == 'fully_allocated' && unallocatedTotal > 0) ||
        (allocationState == 'needs_review' && unallocatedTotal <= 0)) {
      throw const SpinaApiException(
        'The SPINA server returned inconsistent combined cash-allocation evidence.',
        code: 'invalid_combined_payment_payload',
      );
    }
    return CombinedPaymentSubmissionResult(
      status: _requiredString(payload, 'status').toLowerCase(),
      duplicate: payload['duplicate'] == true,
      idempotencyKey: _requiredString(payload, 'client_transaction_id'),
      clientId: _requiredString(payload, 'client_id'),
      totalAmount: totalAmount,
      appliedTotalAmount: appliedTotal,
      unallocatedTotalAmount: unallocatedTotal,
      cashAllocationState: allocationState,
      legs: rawLegs
          .map((item) => CombinedPaymentLegResult.fromPayload(stringMap(item)))
          .toList(growable: false),
      message:
          firstNonEmptyString(<Object?>[payload['message']]) ??
          'Regular + 7x7 payments saved.',
    );
  }
}

String _requiredString(Map<String, dynamic> payload, String key) {
  final value = firstNonEmptyString(<Object?>[payload[key]]);
  if (value == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_combined_payment_payload',
    );
  }
  return value;
}

double _requiredDouble(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value is num) {
    return value.toDouble();
  }
  final parsed = double.tryParse(value?.toString() ?? '');
  if (parsed == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_combined_payment_payload',
    );
  }
  return parsed;
}

double? _optionalDouble(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value == null) {
    return null;
  }
  if (value is num) {
    return value.toDouble();
  }
  return double.tryParse(value.toString());
}

String _date(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}
