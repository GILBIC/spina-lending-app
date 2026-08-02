import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class RemittanceNotification {
  const RemittanceNotification({
    required this.notificationId,
    required this.remittanceId,
    required this.remittanceNumber,
    required this.title,
    required this.message,
    required this.status,
    required this.collectorName,
    required this.totalAmount,
    required this.clientCount,
    required this.transactionCount,
    required this.collectionDate,
    required this.createdAt,
    required this.custodyMessage,
    this.readAt,
    this.acceptedAt,
  });

  final String notificationId;
  final String remittanceId;
  final String remittanceNumber;
  final String title;
  final String message;
  final String status;
  final String collectorName;
  final double totalAmount;
  final int clientCount;
  final int transactionCount;
  final DateTime? collectionDate;
  final DateTime? createdAt;
  final DateTime? readAt;
  final DateTime? acceptedAt;
  final String custodyMessage;

  bool get isPending => status.trim().toLowerCase() == 'pending';

  static RemittanceNotification? fromPayload(Object? value) {
    final data = stringMap(value);
    final notificationId = firstNonEmptyString(<Object?>[
      data['notification_id'],
      data['id'],
    ]);
    final remittanceId = firstNonEmptyString(<Object?>[
      data['remittance_id'],
    ]);
    final remittanceNumber = firstNonEmptyString(<Object?>[
      data['remittance_number'],
    ]);
    if (notificationId == null ||
        remittanceId == null ||
        remittanceNumber == null) {
      return null;
    }
    return RemittanceNotification(
      notificationId: notificationId,
      remittanceId: remittanceId,
      remittanceNumber: remittanceNumber,
      title: firstNonEmptyString(<Object?>[data['title']]) ??
          'Remittance awaiting acceptance',
      message: firstNonEmptyString(<Object?>[data['message']]) ?? '',
      status: firstNonEmptyString(<Object?>[data['status']]) ?? 'pending',
      collectorName:
          firstNonEmptyString(<Object?>[data['collector_name']]) ?? 'Collector',
      totalAmount: firstNumber(<Object?>[data['total_amount']])?.toDouble() ?? 0,
      clientCount: firstNumber(<Object?>[data['client_count']])?.toInt() ?? 0,
      transactionCount:
          firstNumber(<Object?>[data['transaction_count']])?.toInt() ?? 0,
      collectionDate: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['collection_date']]) ?? '',
      ),
      createdAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['created_at']]) ?? '',
      ),
      readAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['read_at']]) ?? '',
      ),
      acceptedAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['accepted_at']]) ?? '',
      ),
      custodyMessage: firstNonEmptyString(<Object?>[
            data['custody_message'],
          ]) ??
          'Accept only after you physically receive the cash.',
    );
  }
}

class RemittanceAcceptanceResult {
  const RemittanceAcceptanceResult({
    required this.notification,
    required this.remittanceId,
    required this.remittanceNumber,
    required this.status,
    required this.custodyUserId,
    required this.custodyMessage,
    this.receivedAt,
  });

  final RemittanceNotification notification;
  final String remittanceId;
  final String remittanceNumber;
  final String status;
  final String custodyUserId;
  final String custodyMessage;
  final DateTime? receivedAt;

  static RemittanceAcceptanceResult fromPayload(Object? value) {
    final data = stringMap(value);
    final notification = RemittanceNotification.fromPayload(data['notification']);
    final remittanceId = firstNonEmptyString(<Object?>[data['remittance_id']]);
    final remittanceNumber =
        firstNonEmptyString(<Object?>[data['remittance_number']]);
    if (notification == null ||
        remittanceId == null ||
        remittanceNumber == null) {
      throw const SpinaApiException(
        'The SPINA server returned an incomplete remittance acceptance.',
        code: 'invalid_notification_response',
      );
    }
    return RemittanceAcceptanceResult(
      notification: notification,
      remittanceId: remittanceId,
      remittanceNumber: remittanceNumber,
      status: firstNonEmptyString(<Object?>[data['status']]) ?? 'received',
      custodyUserId:
          firstNonEmptyString(<Object?>[data['custody_user_id']]) ?? '',
      custodyMessage: firstNonEmptyString(<Object?>[
            data['custody_message'],
          ]) ??
          'Money is now under your custody.',
      receivedAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['received_at']]) ?? '',
      ),
    );
  }
}
