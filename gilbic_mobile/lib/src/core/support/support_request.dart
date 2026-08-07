import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ClientSupportPortal {
  const ClientSupportPortal({
    required this.clientId,
    required this.clientCode,
    required this.clientName,
    required this.requests,
    required this.notice,
  });

  final String clientId;
  final String clientCode;
  final String clientName;
  final List<SupportRequestItem> requests;
  final String notice;

  factory ClientSupportPortal.fromPayload(Map<String, dynamic> payload) {
    final client = stringMap(payload['client']);
    final rawRequests = payload['requests'];
    if (client.isEmpty || rawRequests is! List) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete support data.',
        code: 'invalid_support_payload',
      );
    }
    return ClientSupportPortal(
      clientId: _requiredString(client, 'client_id'),
      clientCode: _requiredString(client, 'client_code'),
      clientName: _requiredString(client, 'client_name'),
      requests: rawRequests
          .map((item) => SupportRequestItem.fromPayload(stringMap(item)))
          .toList(growable: false),
      notice: _optionalString(payload['notice']) ??
          'SPINA staff will review your support requests.',
    );
  }
}

class SupportRequestItem {
  const SupportRequestItem({
    required this.requestId,
    required this.clientId,
    required this.clientCode,
    required this.clientName,
    required this.category,
    required this.subject,
    required this.message,
    required this.referenceText,
    required this.status,
    required this.createdAt,
    required this.managementResponse,
    this.managedByName,
    this.respondedAt,
    this.resolvedAt,
    this.cancelledAt,
  });

  final String requestId;
  final String clientId;
  final String clientCode;
  final String clientName;
  final String category;
  final String subject;
  final String message;
  final String referenceText;
  final String status;
  final DateTime createdAt;
  final String? managedByName;
  final String managementResponse;
  final DateTime? respondedAt;
  final DateTime? resolvedAt;
  final DateTime? cancelledAt;

  bool get isOpen => status.toLowerCase() == 'open';

  String get categoryLabel {
    return switch (category.toLowerCase()) {
      'payment' => 'Payment',
      'loan' => 'Loan',
      'renewal' => 'Renewal',
      'account' => 'Account',
      _ => 'Other',
    };
  }

  String get statusLabel {
    return switch (status.toLowerCase()) {
      'answered' => 'Answered',
      'resolved' => 'Resolved',
      'cancelled' => 'Cancelled',
      _ => 'Open',
    };
  }

  factory SupportRequestItem.fromPayload(Map<String, dynamic> payload) {
    return SupportRequestItem(
      requestId: _requiredString(payload, 'request_id'),
      clientId: _requiredString(payload, 'client_id'),
      clientCode: _requiredString(payload, 'client_code'),
      clientName: _requiredString(payload, 'client_name'),
      category: _requiredString(payload, 'category'),
      subject: _requiredString(payload, 'subject'),
      message: _requiredString(payload, 'message'),
      referenceText: _optionalString(payload['reference_text']) ?? '',
      status: _requiredString(payload, 'status'),
      createdAt: _requiredDate(payload, 'created_at'),
      managedByName: _optionalString(payload['managed_by_name']),
      managementResponse:
          _optionalString(payload['management_response']) ?? '',
      respondedAt: _optionalDate(payload['responded_at']),
      resolvedAt: _optionalDate(payload['resolved_at']),
      cancelledAt: _optionalDate(payload['cancelled_at']),
    );
  }
}

String _requiredString(Map<String, dynamic> payload, String key) {
  final value = _optionalString(payload[key]);
  if (value == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_support_payload',
    );
  }
  return value;
}

String? _optionalString(Object? value) {
  final text = value?.toString().trim() ?? '';
  return text.isEmpty ? null : text;
}

DateTime _requiredDate(Map<String, dynamic> payload, String key) {
  final parsed = _optionalDate(payload[key]);
  if (parsed == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_support_payload',
    );
  }
  return parsed;
}

DateTime? _optionalDate(Object? value) {
  final text = _optionalString(value);
  return text == null ? null : DateTime.tryParse(text);
}
