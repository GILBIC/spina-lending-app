import 'dart:convert';

import 'package:gilbic_mobile/src/core/media/image_recovery_controller.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow.dart';

ImagePickContext renewalHandoverImageContext(CollectorRenewalRequest request) =>
    ImagePickContext(
      purpose: 'renewal_handover',
      target: jsonEncode({
        'request_id': request.requestId,
        'client_id': request.clientId,
        'loan_id': request.loanId,
        'amount_locked_at': request.amountLockedAt?.toUtc().toIso8601String(),
        'net_release_amount': request.netReleaseAmount,
        'cash_given_to_client_at': request.cashGivenToClientAt
            ?.toUtc()
            .toIso8601String(),
      }),
      label: 'Renewal handover photo for ${request.loanNumber}',
    );

ImagePickContext remittanceHandoverImageContext(RemittanceRecord remittance) =>
    ImagePickContext(
      purpose: 'remittance_handover',
      target: jsonEncode({
        'remittance_id': remittance.remittanceId,
        'collector_user_id': remittance.collectorUserId,
        'recipient_user_id': remittance.recipientUserId,
        'submitted_at': remittance.submittedAt?.toUtc().toIso8601String(),
      }),
      label: 'Handover photo for ${remittance.remittanceNumber}',
    );
