import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class CrossRemittanceTarget {
  const CrossRemittanceTarget({
    required this.recipientUserId,
    required this.recipientName,
    required this.transactionCount,
    required this.clientCount,
    required this.totalAmount,
  });

  final String recipientUserId;
  final String recipientName;
  final int transactionCount;
  final int clientCount;
  final double totalAmount;

  static CrossRemittanceTarget? fromPayload(Object? value) {
    final data = stringMap(value);
    final recipientUserId = firstNonEmptyString(<Object?>[
      data['recipient_user_id'],
      data['user_id'],
    ]);
    final recipientName = firstNonEmptyString(<Object?>[
      data['recipient_name'],
      data['full_name'],
    ]);
    if (recipientUserId == null || recipientName == null) {
      return null;
    }
    return CrossRemittanceTarget(
      recipientUserId: recipientUserId,
      recipientName: recipientName,
      transactionCount:
          firstNumber(<Object?>[data['transaction_count']])?.toInt() ?? 0,
      clientCount: firstNumber(<Object?>[data['client_count']])?.toInt() ?? 0,
      totalAmount: firstNumber(<Object?>[data['total_amount']])?.toDouble() ?? 0,
    );
  }
}

enum CrossCollectionCustodyStatus {
  notRemitted,
  awaitingAcceptance,
  accepted;

  static CrossCollectionCustodyStatus fromValue(Object? value) {
    return switch (value?.toString().trim().toLowerCase()) {
      'accepted' => CrossCollectionCustodyStatus.accepted,
      'awaiting_acceptance' => CrossCollectionCustodyStatus.awaitingAcceptance,
      _ => CrossCollectionCustodyStatus.notRemitted,
    };
  }

  String get label => switch (this) {
        CrossCollectionCustodyStatus.notRemitted => 'Not yet remitted',
        CrossCollectionCustodyStatus.awaitingAcceptance => 'Awaiting acceptance',
        CrossCollectionCustodyStatus.accepted => 'Accepted',
      };
}

class CrossCollectionStatus {
  const CrossCollectionStatus({
    required this.transactionId,
    required this.receiptNumber,
    required this.clientId,
    required this.clientName,
    required this.loanId,
    required this.loanType,
    required this.area,
    required this.assignedCollectorUserId,
    required this.assignedCollectorName,
    required this.collectionDate,
    required this.entryType,
    required this.amount,
    required this.acceptedAt,
    required this.isLocked,
    required this.remittanceId,
    required this.remittanceNumber,
    required this.custodyStatus,
    required this.remittanceRecipientUserId,
    required this.remittanceRecipientName,
    required this.submittedAt,
    required this.receivedAt,
  });

  final String transactionId;
  final String receiptNumber;
  final String clientId;
  final String clientName;
  final String loanId;
  final String loanType;
  final String area;
  final String? assignedCollectorUserId;
  final String assignedCollectorName;
  final DateTime? collectionDate;
  final String entryType;
  final double amount;
  final DateTime? acceptedAt;
  final bool isLocked;
  final String? remittanceId;
  final String remittanceNumber;
  final CrossCollectionCustodyStatus custodyStatus;
  final String? remittanceRecipientUserId;
  final String remittanceRecipientName;
  final DateTime? submittedAt;
  final DateTime? receivedAt;

  static CrossCollectionStatus? fromPayload(Object? value) {
    final data = stringMap(value);
    final transactionId = firstNonEmptyString(<Object?>[data['transaction_id']]);
    final receiptNumber = firstNonEmptyString(<Object?>[data['receipt_number']]);
    final clientId = firstNonEmptyString(<Object?>[data['client_id']]);
    final clientName = firstNonEmptyString(<Object?>[data['client_name']]);
    final loanId = firstNonEmptyString(<Object?>[data['loan_id']]);
    if (transactionId == null ||
        receiptNumber == null ||
        clientId == null ||
        clientName == null ||
        loanId == null) {
      return null;
    }
    return CrossCollectionStatus(
      transactionId: transactionId,
      receiptNumber: receiptNumber,
      clientId: clientId,
      clientName: clientName,
      loanId: loanId,
      loanType: firstNonEmptyString(<Object?>[data['loan_type']]) ?? '',
      area: firstNonEmptyString(<Object?>[data['area']]) ?? '',
      assignedCollectorUserId: firstNonEmptyString(<Object?>[
        data['assigned_collector_user_id'],
      ]),
      assignedCollectorName: firstNonEmptyString(<Object?>[
            data['assigned_collector_name'],
          ]) ??
          'Unassigned',
      collectionDate: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['collection_date']]) ?? '',
      ),
      entryType:
          firstNonEmptyString(<Object?>[data['entry_type']]) ?? 'payment',
      amount: firstNumber(<Object?>[data['amount']])?.toDouble() ?? 0,
      acceptedAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['accepted_at']]) ?? '',
      ),
      isLocked: _boolValue(data['is_locked']),
      remittanceId:
          firstNonEmptyString(<Object?>[data['remittance_id']]),
      remittanceNumber:
          firstNonEmptyString(<Object?>[data['remittance_number']]) ?? '',
      custodyStatus:
          CrossCollectionCustodyStatus.fromValue(data['custody_status']),
      remittanceRecipientUserId: firstNonEmptyString(<Object?>[
        data['remittance_recipient_user_id'],
      ]),
      remittanceRecipientName: firstNonEmptyString(<Object?>[
            data['remittance_recipient_name'],
          ]) ??
          '',
      submittedAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['submitted_at']]) ?? '',
      ),
      receivedAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['received_at']]) ?? '',
      ),
    );
  }
}

bool _boolValue(Object? value) {
  if (value is bool) {
    return value;
  }
  return switch (value?.toString().trim().toLowerCase()) {
    'true' || '1' || 'yes' || 'on' => true,
    _ => false,
  };
}
