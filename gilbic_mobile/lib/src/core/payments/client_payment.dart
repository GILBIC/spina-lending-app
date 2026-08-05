import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ClientPaymentTimeline {
  const ClientPaymentTimeline({
    required this.clientId,
    required this.clientCode,
    required this.clientName,
    required this.payments,
    required this.proofUploadAvailable,
    required this.proofMessage,
  });

  final String clientId;
  final String clientCode;
  final String clientName;
  final List<ClientPayment> payments;
  final bool proofUploadAvailable;
  final String proofMessage;

  factory ClientPaymentTimeline.fromPayload(Map<String, dynamic> payload) {
    final client = stringMap(payload['client']);
    final proof = stringMap(payload['payment_proof']);
    final rawPayments = payload['payments'];
    if (client.isEmpty || rawPayments is! List) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete payment data.',
        code: 'invalid_client_payment_payload',
      );
    }
    return ClientPaymentTimeline(
      clientId: _requiredString(client, 'client_id'),
      clientCode: _requiredString(client, 'client_code'),
      clientName: _requiredString(client, 'client_name'),
      payments: rawPayments
          .map((item) => ClientPayment.fromPayload(stringMap(item)))
          .toList(growable: false),
      proofUploadAvailable: proof['upload_available'] == true,
      proofMessage: _optionalString(proof['message']) ??
          'Collector-recorded payments use official SPINA receipts.',
    );
  }

  List<ClientPayment> get validPayments => payments
      .where((payment) => !payment.isVoided)
      .toList(growable: false);

  double get validTotal => validPayments.fold<double>(
        0,
        (total, payment) => total + payment.amount,
      );
}

class ClientPayment {
  const ClientPayment({
    required this.transactionId,
    required this.receiptNumber,
    required this.loanId,
    required this.loanNumber,
    required this.loanTypeName,
    required this.collectorName,
    required this.collectionDate,
    required this.recordedAt,
    required this.entryType,
    required this.amount,
    required this.coveredDates,
    required this.status,
    required this.isVoided,
    required this.editVersion,
    this.previousBalance,
    this.officialBalance,
    this.note,
    this.collectionOrigin,
    this.voidedAt,
    this.voidReason,
    this.remittanceNumber,
    this.remittanceStatus,
    this.remittanceSubmittedAt,
    this.remittanceReceivedAt,
  });

  final String transactionId;
  final String receiptNumber;
  final String loanId;
  final String loanNumber;
  final String loanTypeName;
  final String collectorName;
  final DateTime collectionDate;
  final DateTime recordedAt;
  final String entryType;
  final double amount;
  final List<DateTime> coveredDates;
  final double? previousBalance;
  final double? officialBalance;
  final String? note;
  final String? collectionOrigin;
  final String status;
  final bool isVoided;
  final DateTime? voidedAt;
  final String? voidReason;
  final int editVersion;
  final String? remittanceNumber;
  final String? remittanceStatus;
  final DateTime? remittanceSubmittedAt;
  final DateTime? remittanceReceivedAt;

  factory ClientPayment.fromPayload(Map<String, dynamic> payload) {
    final rawCoveredDates = payload['covered_dates'];
    if (payload.isEmpty || rawCoveredDates is! List) {
      throw const SpinaApiException(
        'The SPINA server returned an incomplete payment record.',
        code: 'invalid_client_payment_record',
      );
    }
    return ClientPayment(
      transactionId: _requiredString(payload, 'transaction_id'),
      receiptNumber: _requiredString(payload, 'receipt_number'),
      loanId: _requiredString(payload, 'loan_id'),
      loanNumber: _requiredString(payload, 'loan_number'),
      loanTypeName: _requiredString(payload, 'loan_type_name'),
      collectorName: _requiredString(payload, 'collector_name'),
      collectionDate: _requiredDate(payload, 'collection_date'),
      recordedAt: _requiredDate(payload, 'recorded_at'),
      entryType: _requiredString(payload, 'entry_type'),
      amount: _requiredDouble(payload, 'amount'),
      coveredDates: rawCoveredDates
          .map(_optionalDate)
          .whereType<DateTime>()
          .toList(growable: false),
      previousBalance: _optionalDouble(payload['previous_balance']),
      officialBalance: _optionalDouble(payload['official_balance']),
      note: _optionalString(payload['note']),
      collectionOrigin: _optionalString(payload['collection_origin']),
      status: _requiredString(payload, 'status'),
      isVoided: payload['is_voided'] == true,
      voidedAt: _optionalDate(payload['voided_at']),
      voidReason: _optionalString(payload['void_reason']),
      editVersion: _requiredInt(payload, 'edit_version'),
      remittanceNumber: _optionalString(payload['remittance_number']),
      remittanceStatus: _optionalString(payload['remittance_status']),
      remittanceSubmittedAt:
          _optionalDate(payload['remittance_submitted_at']),
      remittanceReceivedAt:
          _optionalDate(payload['remittance_received_at']),
    );
  }

  String get statusLabel {
    return switch (status.toLowerCase()) {
      'accepted' => 'Cash accepted',
      'remitted' => 'Remitted',
      'voided' => 'Voided',
      _ => 'Payment posted',
    };
  }
}

String _requiredString(Map<String, dynamic> payload, String key) {
  final value = _optionalString(payload[key]);
  if (value == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_client_payment_payload',
    );
  }
  return value;
}

String? _optionalString(Object? value) {
  final text = value?.toString().trim() ?? '';
  return text.isEmpty ? null : text;
}

double _requiredDouble(Map<String, dynamic> payload, String key) {
  final value = _optionalDouble(payload[key]);
  if (value == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_client_payment_payload',
    );
  }
  return value;
}

double? _optionalDouble(Object? value) {
  if (value is num) {
    return value.toDouble();
  }
  return double.tryParse(value?.toString() ?? '');
}

int _requiredInt(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value is int) {
    return value;
  }
  final parsed = int.tryParse(value?.toString() ?? '');
  if (parsed == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_client_payment_payload',
    );
  }
  return parsed;
}

DateTime _requiredDate(Map<String, dynamic> payload, String key) {
  final value = _optionalDate(payload[key]);
  if (value == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_client_payment_payload',
    );
  }
  return value;
}

DateTime? _optionalDate(Object? value) {
  final text = _optionalString(value);
  return text == null ? null : DateTime.tryParse(text);
}
