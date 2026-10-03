import 'package:gilbic_mobile/src/core/treasury/treasury_models.dart';

Map<String, dynamic> validateLoanPayoutRow(Object? raw, {bool own = false}) {
  final row = treasuryObject(raw);
  requireTreasuryId(row['id']);
  TreasuryMoney(row['amount'], positive: true);
  if (row['version'] is! int ||
      (row['version'] as int) < 1 ||
      !['first_loan', 'renewal'].contains(row['source_kind']) ||
      !['collector', 'borrower'].contains(row['destination']) ||
      ![
        'prepared',
        'debited',
        'recipient_confirmed',
        'completed',
        'cancelled',
      ].contains(row['status'])) {
    throw const FormatException('The payout record is incomplete.');
  }
  if (own) {
    const allowed = {
      'id',
      'version',
      'source_kind',
      'status',
      'amount',
      'destination',
      'label',
      'acknowledgments',
      'borrower_handover_status',
      'account_id',
      'ledger_context_id',
      'blocker',
      'stages',
      'funding_method',
    };
    if (row.keys.any((k) => !allowed.contains(k))) {
      throw const FormatException(
        'Private metadata is unavailable for this recipient.',
      );
    }
    if (row['acknowledgments'] != null) {
      final acknowledgments = treasuryObject(row['acknowledgments']);
      for (final entry in acknowledgments.entries) {
        final ack = treasuryObject(entry.value);
        if (![
              'recipient',
              'borrower_handover',
              'borrower',
            ].contains(entry.key) ||
            ack.keys.any(
              (k) => ![
                'received',
                'reviewed_amount',
                'receipt_method',
                'acknowledged_at',
              ].contains(k),
            ) ||
            ack['received'] is! bool ||
            !['cash', 'gcash', 'bank'].contains(ack['receipt_method']) ||
            DateTime.tryParse(ack['acknowledged_at']?.toString() ?? '') == null) {
          throw const FormatException('The receipt projection is incomplete.');
        }
        TreasuryMoney(ack['reviewed_amount'], positive: true);
      }
    }
  }
  return row;
}

Map<String, dynamic> loanPayoutPreparation(
  TreasuryAccount account,
  Map<String, dynamic> source,
  String recipient, {
  String destination = 'collector',
}) {
  if (!['collector', 'borrower'].contains(destination) ||
      recipient.trim().isEmpty ||
      !['first_loan', 'renewal'].contains(source['source_kind'])) {
    throw const FormatException('Select the exact loan and recipient.');
  }
  if (source['source_kind'] == 'first_loan' &&
      (!treasuryUuid(source['authorization_id']) ||
          !RegExp(
            r'^[a-f0-9]{64}$',
          ).hasMatch(source['packet_hash']?.toString() ?? '') ||
          !RegExp(
            r'^office-evidence:[a-f0-9-]+$',
            caseSensitive: false,
          ).hasMatch(source['contract_evidence_reference']?.toString() ?? ''))) {
    throw const FormatException(
      'The protected first-loan authority is incomplete.',
    );
  }
  return {
    'account_id': account.id,
    'expected_version': account.version,
    'source_kind': source['source_kind'],
    'source_id': requireTreasuryId(source['source_id']),
    'destination': destination,
    'recipient_reference': recipient.trim(),
    if (source['source_kind'] == 'first_loan') ...{
      'authorization_id': source['authorization_id'],
      'packet_hash': source['packet_hash'],
      'contract_evidence_reference': source['contract_evidence_reference'],
    },
  };
}

void validateLoanPayoutOutcome(
  TreasuryResult value,
  Map<String, dynamic> held,
) {
  final body = treasuryObject(held['body']),
      row = validateLoanPayoutRow(
        value.result['payout'],
        own: held['action'] == 'loan_payout_acknowledge',
      );
  if (row['id'] != value.targetId || row['version'] != value.version) {
    throw const FormatException('Payout identity changed.');
  }
  if (held['action'] == 'loan_payout_prepare') {
    final preview = treasuryObject(held['payout_preview']);
    if (row['status'] != 'prepared' ||
        row['version'] != 1 ||
        row['source_id'] != body['source_id'] ||
        row['source_kind'] != body['source_kind'] ||
        row['destination'] != body['destination'] ||
        row['amount'] != preview['amount'] ||
        row['source_digest'] != body['source_digest'] ||
        row['recipient_reference'] != body['recipient_reference']) {
      throw const FormatException(
        'The prepared payout does not match the review.',
      );
    }
  } else {
    final prior = treasuryObject(held['payout_reference']);
    if (row['id'] != prior['id'] ||
        row['version'] != (body['payout_version'] as int) + 1 ||
        row['amount'] != prior['amount'] ||
        row['destination'] != prior['destination'] ||
        row['source_kind'] != prior['source_kind']) {
      throw const FormatException('The payout changed after review.');
    }
    final action = held['action'] as String;
    final status = action == 'loan_payout_cancel'
        ? 'cancelled'
        : action.endsWith('_complete')
        ? 'completed'
        : action == 'loan_payout_recipient_confirm'
        ? (body['received'] == true ? 'recipient_confirmed' : 'debited')
        : prior['status'];
    if (row['status'] != status ||
        action == 'loan_payout_acknowledge' &&
            value.result['stage'] != body['stage']) {
      throw const FormatException('The receipt stage was not confirmed.');
    }
    bool sameTime(Object? a, Object? b) {
      final first = DateTime.tryParse(a?.toString() ?? ''),
          second = DateTime.tryParse(b?.toString() ?? '');
      return first != null && second != null && first.isAtSameMomentAs(second);
    }

    const mismatch = FormatException(
      'The saved receipt differs from the reviewed stage.',
    );
    if (action == 'loan_payout_acknowledge') {
      final ack = treasuryObject(
        treasuryObject(row['acknowledgments'])[body['stage']],
      );
      if (ack['received'] != body['received'] ||
          ack['reviewed_amount'] != body['reviewed_amount'] ||
          ack['receipt_method'] != body['receipt_method'] ||
          !sameTime(ack['acknowledged_at'], body['acknowledged_at'])) {
        throw mismatch;
      }
    } else {
      if ([
        'source_id',
        'client_id',
        'account_id',
        'ledger_context_id',
        'source_digest',
        'recipient_reference',
      ].any((k) => prior[k] != null && row[k] != prior[k])) {
        throw mismatch;
      }
      final payload = treasuryObject(row['payload']);
      if (action == 'loan_payout_cancel' && payload['reason'] != body['reason']) {
        throw mismatch;
      }
      if (action == 'loan_payout_recipient_confirm') {
        final ack = treasuryObject(payload['recipient_confirmation']);
        if (ack['evidence_id'] != body['evidence_id'] ||
            ack['received'] != body['received'] ||
            ack['reviewed_amount'] != body['reviewed_amount'] ||
            ack['attestation'] != body['recipient_attestation'] ||
            !sameTime(ack['acknowledged_at'], body['acknowledged_at'])) {
          throw mismatch;
        }
      }
      if (action == 'loan_payout_first_loan_complete') {
        final receipt = treasuryObject(payload['borrower_receipt']),
            ack = treasuryObject(receipt['snapshot']);
        if (receipt['evidence_id'] != body['evidence_id'] ||
            ack['amount'] != body['reviewed_amount'] ||
            ack['receipt_method'] != body['receipt_method'] ||
            ack['attestation'] != body['borrower_attestation'] ||
            !sameTime(ack['acknowledged_at'], body['acknowledged_at'])) {
          throw mismatch;
        }
      }
      if (action == 'loan_payout_renewal_complete') {
        final proof = treasuryObject(payload['proof_review']);
        if (proof['evidence_id'] != body['evidence_id'] ||
            proof['reason'] != body['reason']) {
          throw mismatch;
        }
      }
    }
  }
}
