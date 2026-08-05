import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ActivityNotification {
  const ActivityNotification({
    required this.id,
    required this.type,
    required this.title,
    required this.message,
    required this.senderName,
    required this.metadata,
    required this.isRead,
    required this.createdAt,
    this.transactionId,
    this.remittanceId,
    this.clientId,
    this.readAt,
  });

  final String id;
  final String type;
  final String title;
  final String message;
  final String senderName;
  final Map<String, dynamic> metadata;
  final bool isRead;
  final DateTime? createdAt;
  final String? transactionId;
  final String? remittanceId;
  final String? clientId;
  final DateTime? readAt;

  String get receiptNumber =>
      firstNonEmptyString(<Object?>[metadata['receipt_number']]) ?? '';

  String get remittanceNumber =>
      firstNonEmptyString(<Object?>[metadata['remittance_number']]) ?? '';

  String get amount => firstNonEmptyString(<Object?>[metadata['amount']]) ?? '';

  String get custodyName =>
      firstNonEmptyString(<Object?>[metadata['custody_name']]) ?? '';

  static ActivityNotification? fromPayload(Object? value) {
    final data = stringMap(value);
    final id = firstNonEmptyString(<Object?>[
      data['notification_id'],
      data['id'],
    ]);
    final title = firstNonEmptyString(<Object?>[data['title']]);
    final message = firstNonEmptyString(<Object?>[data['message']]);
    if (id == null || title == null || message == null) {
      return null;
    }
    return ActivityNotification(
      id: id,
      type: firstNonEmptyString(<Object?>[
            data['notification_type'],
            data['type'],
          ]) ??
          'activity',
      title: title,
      message: message,
      senderName: firstNonEmptyString(<Object?>[
            data['sender_name'],
          ]) ??
          'SPINA',
      metadata: stringMap(data['metadata']),
      isRead: _boolValue(data['is_read']),
      createdAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['created_at']]) ?? '',
      ),
      readAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['read_at']]) ?? '',
      ),
      transactionId: firstNonEmptyString(<Object?>[data['transaction_id']]),
      remittanceId: firstNonEmptyString(<Object?>[data['remittance_id']]),
      clientId: firstNonEmptyString(<Object?>[data['client_id']]),
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
