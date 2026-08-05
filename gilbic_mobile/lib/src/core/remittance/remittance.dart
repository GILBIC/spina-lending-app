import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class RemittanceRecipient {
  const RemittanceRecipient({
    required this.userId,
    required this.fullName,
    required this.roleName,
  });

  final String userId;
  final String fullName;
  final String roleName;

  static RemittanceRecipient? fromPayload(Object? value) {
    final data = stringMap(value);
    final userId = firstNonEmptyString(<Object?>[data['user_id'], data['id']]);
    final fullName =
        firstNonEmptyString(<Object?>[data['full_name'], data['name']]);
    if (userId == null || fullName == null) {
      return null;
    }
    return RemittanceRecipient(
      userId: userId,
      fullName: fullName,
      roleName:
          firstNonEmptyString(<Object?>[data['role_name'], data['role']]) ??
              'Recipient',
    );
  }
}

class RemittanceItem {
  const RemittanceItem({
    required this.transactionId,
    required this.clientName,
    required this.loanType,
    required this.entryType,
    required this.amount,
    required this.receiptNumber,
    required this.coveredDates,
    required this.note,
  });

  final String transactionId;
  final String clientName;
  final String loanType;
  final String entryType;
  final double amount;
  final String receiptNumber;
  final List<DateTime> coveredDates;
  final String note;

  static RemittanceItem? fromPayload(Object? value) {
    final data = stringMap(value);
    final transactionId = firstNonEmptyString(<Object?>[
      data['transaction_id'],
      data['id'],
    ]);
    final clientName = firstNonEmptyString(<Object?>[
      data['client_name'],
      data['full_name'],
    ]);
    if (transactionId == null || clientName == null) {
      return null;
    }
    return RemittanceItem(
      transactionId: transactionId,
      clientName: clientName,
      loanType: firstNonEmptyString(<Object?>[data['loan_type']]) ?? 'Loan',
      entryType:
          firstNonEmptyString(<Object?>[data['entry_type']]) ?? 'payment',
      amount: firstNumber(<Object?>[data['amount']])?.toDouble() ?? 0,
      receiptNumber:
          firstNonEmptyString(<Object?>[data['receipt_number']]) ?? '',
      coveredDates: _dateList(data['covered_dates']),
      note: firstNonEmptyString(<Object?>[data['note']]) ?? '',
    );
  }
}

class RemittanceSummary {
  const RemittanceSummary({
    required this.collectionDate,
    required this.collectorName,
    required this.transactionCount,
    required this.paymentCount,
    required this.unableToPayCount,
    required this.coveredPaymentCount,
    required this.clientCount,
    required this.totalAmount,
    required this.items,
  });

  final DateTime? collectionDate;
  final String collectorName;
  final int transactionCount;
  final int paymentCount;
  final int unableToPayCount;
  final int coveredPaymentCount;
  final int clientCount;
  final double totalAmount;
  final List<RemittanceItem> items;

  static RemittanceSummary fromPayload(Object? value) {
    final data = stringMap(value);
    final rawItems = data['items'];
    final items = rawItems is Iterable
        ? rawItems
            .map(RemittanceItem.fromPayload)
            .whereType<RemittanceItem>()
            .toList(growable: false)
        : const <RemittanceItem>[];
    final exactCoveredDateCount = items.fold<int>(
      0,
      (total, item) => total + item.coveredDates.length,
    );
    final serverCoveredCount =
        firstNumber(<Object?>[data['covered_payment_count']])?.toInt() ?? 0;

    return RemittanceSummary(
      collectionDate: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['collection_date']]) ?? '',
      ),
      collectorName:
          firstNonEmptyString(<Object?>[data['collector_name']]) ?? 'Collector',
      transactionCount:
          firstNumber(<Object?>[data['transaction_count']])?.toInt() ?? 0,
      paymentCount: firstNumber(<Object?>[data['payment_count']])?.toInt() ?? 0,
      unableToPayCount:
          firstNumber(<Object?>[data['unable_to_pay_count']])?.toInt() ?? 0,
      coveredPaymentCount:
          exactCoveredDateCount > 0 ? exactCoveredDateCount : serverCoveredCount,
      clientCount: firstNumber(<Object?>[data['client_count']])?.toInt() ?? 0,
      totalAmount: firstNumber(<Object?>[data['total_amount']])?.toDouble() ?? 0,
      items: items,
    );
  }
}

class RemittanceRecord {
  const RemittanceRecord({
    required this.remittanceId,
    required this.remittanceNumber,
    required this.collectorUserId,
    required this.collectorName,
    required this.recipientUserId,
    required this.recipientName,
    required this.status,
    required this.summary,
    required this.note,
    required this.submittedAt,
    required this.receivedAt,
  });

  final String remittanceId;
  final String remittanceNumber;
  final String collectorUserId;
  final String collectorName;
  final String recipientUserId;
  final String recipientName;
  final String status;
  final RemittanceSummary summary;
  final String note;
  final DateTime? submittedAt;
  final DateTime? receivedAt;

  bool get isReceived => status.trim().toLowerCase() == 'received';

  static RemittanceRecord? fromPayload(Object? value) {
    final data = stringMap(value);
    final id = firstNonEmptyString(<Object?>[
      data['remittance_id'],
      data['id'],
    ]);
    final number = firstNonEmptyString(<Object?>[
      data['remittance_number'],
      data['number'],
    ]);
    if (id == null || number == null) {
      return null;
    }
    return RemittanceRecord(
      remittanceId: id,
      remittanceNumber: number,
      collectorUserId:
          firstNonEmptyString(<Object?>[data['collector_user_id']]) ?? '',
      collectorName:
          firstNonEmptyString(<Object?>[data['collector_name']]) ?? 'Collector',
      recipientUserId:
          firstNonEmptyString(<Object?>[data['recipient_user_id']]) ?? '',
      recipientName:
          firstNonEmptyString(<Object?>[data['recipient_name']]) ?? 'Recipient',
      status: firstNonEmptyString(<Object?>[data['status']]) ?? 'submitted',
      summary: RemittanceSummary.fromPayload(data),
      note: firstNonEmptyString(<Object?>[data['note']]) ?? '',
      submittedAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['submitted_at']]) ?? '',
      ),
      receivedAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['received_at']]) ?? '',
      ),
    );
  }
}

List<DateTime> _dateList(Object? value) {
  if (value is! Iterable) {
    return const <DateTime>[];
  }
  final dates = value
      .map((item) => DateTime.tryParse(item.toString()))
      .whereType<DateTime>()
      .toSet()
      .toList(growable: false)
    ..sort((left, right) => left.compareTo(right));
  return dates;
}
