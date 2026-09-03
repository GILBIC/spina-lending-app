import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow.dart';

class ManagementRenewalWorkflowItem {
  const ManagementRenewalWorkflowItem({
    required this.request,
    required this.borrowerUserId,
  });

  final CollectorRenewalRequest request;
  final String? borrowerUserId;

  factory ManagementRenewalWorkflowItem.fromPayload(
    Map<String, dynamic> payload,
  ) {
    return ManagementRenewalWorkflowItem(
      request: CollectorRenewalRequest.fromPayload(payload),
      borrowerUserId:
          firstNonEmptyString(<Object?>[payload['borrower_user_id']]),
    );
  }
}

class ManagementRenewalSignerDraft {
  const ManagementRenewalSignerDraft({
    required this.partyRole,
    required this.fullName,
    required this.userId,
    required this.governmentIdVerified,
    required this.selfieVerified,
  });

  final String partyRole;
  final String fullName;
  final String? userId;
  final bool governmentIdVerified;
  final bool selfieVerified;

  Map<String, Object?> toJson() => <String, Object?>{
        'party_role': partyRole,
        'full_name': fullName,
        'user_id': userId,
        'government_id_verified': governmentIdVerified,
        'selfie_verified': selfieVerified,
      };
}

class ManagementRenewalTermsDraft {
  const ManagementRenewalTermsDraft({
    required this.decision,
    required this.reviewNote,
    required this.overrideReason,
    required this.officeProcessingRequired,
    required this.signers,
    this.approvedPrincipal,
  });

  final String decision;
  final double? approvedPrincipal;
  final String reviewNote;
  final String overrideReason;
  final bool officeProcessingRequired;
  final List<ManagementRenewalSignerDraft> signers;

  Map<String, Object?> toJson() => <String, Object?>{
        'decision': decision,
        'approved_principal': approvedPrincipal,
        'review_note': reviewNote,
        'override_reason': overrideReason,
        'office_processing_required': officeProcessingRequired,
        'signers': signers.map((item) => item.toJson()).toList(growable: false),
      };
}
