import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ManagementCollectionVoidCandidate {
  const ManagementCollectionVoidCandidate({
    required this.transactionId,
    required this.receiptNumber,
    required this.clientCode,
    required this.clientName,
    required this.loanType,
    required this.collectorName,
    required this.collectionDate,
    required this.entryType,
    required this.amount,
    required this.coveredDates,
    required this.previousBalance,
    required this.officialBalance,
  });

  final String transactionId;
  final String receiptNumber;
  final String clientCode;
  final String clientName;
  final String loanType;
  final String collectorName;
  final DateTime? collectionDate;
  final String entryType;
  final double amount;
  final List<String> coveredDates;
  final double previousBalance;
  final double officialBalance;

  static ManagementCollectionVoidCandidate fromPayload(Object? value) {
    final data = stringMap(value);
    final transactionId = firstNonEmptyString(<Object?>[
      data['transaction_id'],
    ]);
    final receiptNumber = firstNonEmptyString(<Object?>[
      data['receipt_number'],
    ]);
    if (transactionId == null || receiptNumber == null) {
      throw const SpinaApiException(
        'The SPINA server returned an incomplete collection record.',
        code: 'invalid_collection_void_candidate',
      );
    }
    return ManagementCollectionVoidCandidate(
      transactionId: transactionId,
      receiptNumber: receiptNumber,
      clientCode:
          firstNonEmptyString(<Object?>[data['client_code']]) ?? '',
      clientName:
          firstNonEmptyString(<Object?>[data['client_name']]) ?? 'Client',
      loanType: firstNonEmptyString(<Object?>[data['loan_type']]) ?? '',
      collectorName:
          firstNonEmptyString(<Object?>[data['collector_name']]) ?? 'Collector',
      collectionDate: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['collection_date']]) ?? '',
      ),
      entryType:
          firstNonEmptyString(<Object?>[data['entry_type']]) ?? 'payment',
      amount: firstNumber(<Object?>[data['amount']])?.toDouble() ?? 0,
      coveredDates: stringList(data['covered_dates']),
      previousBalance:
          firstNumber(<Object?>[data['previous_balance']])?.toDouble() ?? 0,
      officialBalance:
          firstNumber(<Object?>[data['official_balance']])?.toDouble() ?? 0,
    );
  }
}

class ManagementCollectionVoidResult {
  const ManagementCollectionVoidResult({
    required this.transactionId,
    required this.receiptNumber,
    required this.clientName,
    required this.restoredBalance,
    required this.stateVersion,
    required this.reason,
    required this.voidedAt,
  });

  final String transactionId;
  final String receiptNumber;
  final String clientName;
  final double restoredBalance;
  final int stateVersion;
  final String reason;
  final DateTime? voidedAt;

  static ManagementCollectionVoidResult fromPayload(Object? value) {
    final data = stringMap(value);
    final transactionId = firstNonEmptyString(<Object?>[
      data['transaction_id'],
    ]);
    final receiptNumber = firstNonEmptyString(<Object?>[
      data['receipt_number'],
    ]);
    if (transactionId == null || receiptNumber == null) {
      throw const SpinaApiException(
        'The SPINA server returned an incomplete void result.',
        code: 'invalid_collection_void_result',
      );
    }
    return ManagementCollectionVoidResult(
      transactionId: transactionId,
      receiptNumber: receiptNumber,
      clientName:
          firstNonEmptyString(<Object?>[data['client_name']]) ?? 'Client',
      restoredBalance:
          firstNumber(<Object?>[data['restored_balance']])?.toDouble() ?? 0,
      stateVersion:
          firstNumber(<Object?>[data['state_version']])?.toInt() ?? 0,
      reason: firstNonEmptyString(<Object?>[data['reason']]) ?? '',
      voidedAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['voided_at']]) ?? '',
      ),
    );
  }
}
