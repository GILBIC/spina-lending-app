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
    this.rejectedAt,
    this.rejectionReason = '',
    this.hasHandoverPhoto = false,
    this.handoverPhotoVersion = 0,
    this.handoverPhotoContentType = '',
    this.handoverPhotoUploadedAt,
    this.handoverPhotoUrl = '',
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
  final DateTime? rejectedAt;
  final String rejectionReason;
  final String custodyMessage;
  final bool hasHandoverPhoto;
  final int handoverPhotoVersion;
  final String handoverPhotoContentType;
  final DateTime? handoverPhotoUploadedAt;
  final String handoverPhotoUrl;

  String get normalizedStatus => status.trim().toLowerCase();
  bool get isPending => normalizedStatus == 'pending';
  bool get isRejected => normalizedStatus == 'rejected';

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
      rejectedAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['rejected_at']]) ?? '',
      ),
      rejectionReason:
          firstNonEmptyString(<Object?>[data['rejection_reason']]) ?? '',
      custodyMessage: firstNonEmptyString(<Object?>[
            data['custody_message'],
          ]) ??
          'Review all payments before taking action on this remittance.',
      hasHandoverPhoto: _boolValue(data['has_handover_photo']),
      handoverPhotoVersion:
          firstNumber(<Object?>[data['handover_photo_version']])?.toInt() ?? 0,
      handoverPhotoContentType: firstNonEmptyString(<Object?>[
            data['handover_photo_content_type'],
          ]) ??
          '',
      handoverPhotoUploadedAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['handover_photo_uploaded_at']]) ?? '',
      ),
      handoverPhotoUrl: firstNonEmptyString(<Object?>[
            data['handover_photo_url'],
          ]) ??
          '',
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
        'The Gilbic server returned an incomplete remittance acceptance.',
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

bool _boolValue(Object? value) {
  if (value is bool) {
    return value;
  }
  final normalized = value?.toString().trim().toLowerCase();
  return normalized == 'true' || normalized == '1' || normalized == 'yes';
}
