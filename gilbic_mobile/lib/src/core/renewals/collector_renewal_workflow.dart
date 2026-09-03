import 'dart:typed_data';

import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class CollectorRenewalSigner {
  const CollectorRenewalSigner({
    required this.signerId,
    required this.partyRole,
    required this.fullName,
    required this.hasApp,
    required this.governmentIdVerified,
    required this.selfieVerified,
    required this.signed,
    required this.ready,
  });

  final String signerId;
  final String partyRole;
  final String fullName;
  final bool hasApp;
  final bool governmentIdVerified;
  final bool selfieVerified;
  final bool signed;
  final bool ready;

  factory CollectorRenewalSigner.fromPayload(Map<String, dynamic> payload) {
    return CollectorRenewalSigner(
      signerId: _requiredString(payload, 'signer_id'),
      partyRole: _requiredString(payload, 'party_role'),
      fullName: _requiredString(payload, 'full_name'),
      hasApp: payload['has_app'] == true,
      governmentIdVerified: payload['government_id_verified'] == true,
      selfieVerified: payload['selfie_verified'] == true,
      signed: payload['signed'] == true,
      ready: payload['ready'] == true,
    );
  }
}

class CollectorRenewalRequest {
  const CollectorRenewalRequest({
    required this.requestId,
    required this.clientId,
    required this.clientCode,
    required this.clientName,
    required this.area,
    required this.loanId,
    required this.loanNumber,
    required this.loanTypeName,
    required this.isSevenBySeven,
    required this.currentPrincipal,
    required this.remainingBalance,
    required this.contractualTotal,
    required this.paidCash,
    required this.paidPercent,
    required this.regular50PercentEligible,
    required this.requestedAmount,
    required this.clientMessage,
    required this.status,
    required this.submittedAt,
    required this.collectorReasonCode,
    required this.collectorComment,
    required this.reviewNote,
    required this.managementOverrideReason,
    required this.signerReadinessStatus,
    required this.officeProcessingRequired,
    required this.signers,
    required this.handoverProofStatus,
    required this.activationStatus,
    required this.readyForActivation,
    this.collectorRecommendation,
    this.recommendedAt,
    this.approvedPrincipal,
    this.reviewedAt,
    this.clientDecision,
    this.clientDecidedAt,
    this.renewalOffsetAmount,
    this.netReleaseAmount,
    this.amountLockedAt,
    this.cashReleasedToCollectorAt,
    this.collectorCashReceivedAt,
    this.cashGivenToClientAt,
    this.clientCashConfirmedAt,
    this.newLoanId,
  });

  final String requestId;
  final String clientId;
  final String clientCode;
  final String clientName;
  final String area;
  final String loanId;
  final String loanNumber;
  final String loanTypeName;
  final bool isSevenBySeven;
  final double currentPrincipal;
  final double remainingBalance;
  final double contractualTotal;
  final double paidCash;
  final double paidPercent;
  final bool regular50PercentEligible;
  final double requestedAmount;
  final String clientMessage;
  final String status;
  final DateTime submittedAt;
  final String? collectorRecommendation;
  final String collectorReasonCode;
  final String collectorComment;
  final DateTime? recommendedAt;
  final double? approvedPrincipal;
  final String reviewNote;
  final String managementOverrideReason;
  final DateTime? reviewedAt;
  final String? clientDecision;
  final DateTime? clientDecidedAt;
  final String signerReadinessStatus;
  final bool officeProcessingRequired;
  final List<CollectorRenewalSigner> signers;
  final double? renewalOffsetAmount;
  final double? netReleaseAmount;
  final DateTime? amountLockedAt;
  final DateTime? cashReleasedToCollectorAt;
  final DateTime? collectorCashReceivedAt;
  final DateTime? cashGivenToClientAt;
  final DateTime? clientCashConfirmedAt;
  final String handoverProofStatus;
  final String activationStatus;
  final String? newLoanId;
  final bool readyForActivation;

  bool get needsCollectorRecommendation =>
      status.toLowerCase() == 'pending' && collectorRecommendation == null;

  bool get awaitingManagement =>
      status.toLowerCase() == 'pending' && collectorRecommendation != null;

  bool get approved => status.toLowerCase() == 'approved';

  bool get canConfirmCashReceived =>
      approved &&
      cashReleasedToCollectorAt != null &&
      collectorCashReceivedAt == null;

  bool get canConfirmCashGiven =>
      approved &&
      collectorCashReceivedAt != null &&
      cashGivenToClientAt == null;

  bool get needsPhoto =>
      cashGivenToClientAt != null &&
      handoverProofStatus != 'approved' &&
      handoverProofStatus != 'under_review';

  String get displayStatus {
    if (status == 'rejected') return 'Rejected';
    if (clientDecision == 'declined') return 'Client declined';
    if (activationStatus == 'active') return 'Active';
    if (handoverProofStatus == 'correction_required') {
      return 'Proof Correction Required';
    }
    if (handoverProofStatus == 'under_review') return 'Proof Under Review';
    if (clientCashConfirmedAt == null && cashGivenToClientAt != null) {
      return 'Awaiting Client Confirmation';
    }
    if (cashReleasedToCollectorAt != null && collectorCashReceivedAt == null) {
      return 'Cash Ready for Collector';
    }
    if (collectorCashReceivedAt != null && cashGivenToClientAt == null) {
      return 'Cash With Collector';
    }
    if (officeProcessingRequired) return 'Office Processing Required';
    if (approved && clientDecision == null) return 'Awaiting Client Acceptance';
    if (approved) return 'Approved';
    if (awaitingManagement) return 'Awaiting Management';
    return 'Renewal Requested';
  }

  factory CollectorRenewalRequest.fromPayload(Map<String, dynamic> payload) {
    final rawSigners = payload['signers'];
    return CollectorRenewalRequest(
      requestId: _requiredString(payload, 'request_id'),
      clientId: _requiredString(payload, 'client_id'),
      clientCode: _requiredString(payload, 'client_code'),
      clientName: _requiredString(payload, 'client_name'),
      area: _requiredString(payload, 'area'),
      loanId: _requiredString(payload, 'loan_id'),
      loanNumber: _requiredString(payload, 'loan_number'),
      loanTypeName: _requiredString(payload, 'loan_type_name'),
      isSevenBySeven: payload['is_7x7'] == true,
      currentPrincipal: _requiredDouble(payload, 'current_principal'),
      remainingBalance: _requiredDouble(payload, 'remaining_balance'),
      contractualTotal: _requiredDouble(payload, 'contractual_total'),
      paidCash: _requiredDouble(payload, 'paid_cash'),
      paidPercent: _requiredDouble(payload, 'paid_percent'),
      regular50PercentEligible: payload['regular_50_percent_eligible'] == true,
      requestedAmount: _requiredDouble(payload, 'requested_amount'),
      clientMessage: firstNonEmptyString(<Object?>[payload['client_message']]) ?? '',
      status: _requiredString(payload, 'status').toLowerCase(),
      submittedAt: _requiredDate(payload, 'submitted_at'),
      collectorRecommendation:
          firstNonEmptyString(<Object?>[payload['collector_recommendation']]),
      collectorReasonCode:
          firstNonEmptyString(<Object?>[payload['collector_reason_code']]) ?? '',
      collectorComment:
          firstNonEmptyString(<Object?>[payload['collector_comment']]) ?? '',
      recommendedAt: _optionalDate(payload['recommended_at']),
      approvedPrincipal: _optionalDouble(payload['approved_principal']),
      reviewNote: firstNonEmptyString(<Object?>[payload['review_note']]) ?? '',
      managementOverrideReason:
          firstNonEmptyString(<Object?>[payload['management_override_reason']]) ?? '',
      reviewedAt: _optionalDate(payload['reviewed_at']),
      clientDecision: firstNonEmptyString(<Object?>[payload['client_decision']]),
      clientDecidedAt: _optionalDate(payload['client_decided_at']),
      signerReadinessStatus:
          _requiredString(payload, 'signer_readiness_status'),
      officeProcessingRequired: payload['office_processing_required'] == true,
      signers: rawSigners is List
          ? rawSigners
              .map((item) => CollectorRenewalSigner.fromPayload(stringMap(item)))
              .toList(growable: false)
          : const <CollectorRenewalSigner>[],
      renewalOffsetAmount: _optionalDouble(payload['renewal_offset_amount']),
      netReleaseAmount: _optionalDouble(payload['net_release_amount']),
      amountLockedAt: _optionalDate(payload['amount_locked_at']),
      cashReleasedToCollectorAt:
          _optionalDate(payload['cash_released_to_collector_at']),
      collectorCashReceivedAt:
          _optionalDate(payload['collector_cash_received_at']),
      cashGivenToClientAt: _optionalDate(payload['cash_given_to_client_at']),
      clientCashConfirmedAt:
          _optionalDate(payload['client_cash_confirmed_at']),
      handoverProofStatus: _requiredString(payload, 'handover_proof_status'),
      activationStatus: _requiredString(payload, 'activation_status'),
      newLoanId: firstNonEmptyString(<Object?>[payload['new_loan_id']]),
      readyForActivation: payload['ready_for_activation'] == true,
    );
  }
}

class RenewalHandoverPhotoDraft {
  const RenewalHandoverPhotoDraft({
    required this.filename,
    required this.contentType,
    required this.bytes,
  });

  final String filename;
  final String contentType;
  final Uint8List bytes;

  String? validate() {
    if (bytes.isEmpty) return 'Choose a handover photo first.';
    if (bytes.length > 8 * 1024 * 1024) {
      return 'Renewal handover photo must be 8 MB or smaller.';
    }
    if (!const <String>{'image/jpeg', 'image/png', 'image/webp'}
        .contains(contentType)) {
      return 'Use a JPEG, PNG or WebP handover photo.';
    }
    return null;
  }

  factory RenewalHandoverPhotoDraft.fromBytes({
    required String filename,
    required Uint8List bytes,
    String? suggestedContentType,
  }) {
    final lower = filename.toLowerCase();
    final contentType = suggestedContentType?.split(';').first.trim().toLowerCase();
    final normalized = switch (contentType) {
      'image/jpeg' || 'image/png' || 'image/webp' => contentType!,
      _ when lower.endsWith('.png') => 'image/png',
      _ when lower.endsWith('.webp') => 'image/webp',
      _ => 'image/jpeg',
    };
    return RenewalHandoverPhotoDraft(
      filename: filename,
      contentType: normalized,
      bytes: bytes,
    );
  }
}

String _requiredString(Map<String, dynamic> payload, String key) {
  final value = firstNonEmptyString(<Object?>[payload[key]]);
  if (value == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_collector_renewal_payload',
    );
  }
  return value;
}

double _requiredDouble(Map<String, dynamic> payload, String key) {
  final value = _optionalDouble(payload[key]);
  if (value == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_collector_renewal_payload',
    );
  }
  return value;
}

double? _optionalDouble(Object? value) {
  if (value == null) return null;
  if (value is num) return value.toDouble();
  return double.tryParse(value.toString());
}

DateTime _requiredDate(Map<String, dynamic> payload, String key) {
  final value = _optionalDate(payload[key]);
  if (value == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_collector_renewal_payload',
    );
  }
  return value;
}

DateTime? _optionalDate(Object? value) {
  final text = firstNonEmptyString(<Object?>[value]);
  return text == null ? null : DateTime.tryParse(text);
}
