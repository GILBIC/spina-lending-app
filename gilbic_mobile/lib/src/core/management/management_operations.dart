import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ManagementOperationsOverview {
  const ManagementOperationsOverview({
    required this.summary,
    required this.entries,
    required this.audits,
    required this.notice,
  });

  final ManagementOperationsSummary summary;
  final List<ManagementOperationEntry> entries;
  final List<ManagementOperationAudit> audits;
  final String notice;

  factory ManagementOperationsOverview.fromPayload(Map<String, dynamic> payload) {
    final rawEntries = payload['entries'];
    final rawAudits = payload['audits'];
    if (rawEntries is! List || rawAudits is! List) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete Loan Operations data.',
        code: 'invalid_management_operations_payload',
      );
    }
    return ManagementOperationsOverview(
      summary: ManagementOperationsSummary.fromPayload(
        stringMap(payload['summary']),
      ),
      entries: rawEntries
          .map((item) => ManagementOperationEntry.fromPayload(stringMap(item)))
          .toList(growable: false),
      audits: rawAudits
          .map((item) => ManagementOperationAudit.fromPayload(stringMap(item)))
          .toList(growable: false),
      notice: _optionalString(payload['notice']) ??
          'Loan Operations is read-only in mobile.',
    );
  }
}

class ManagementOperationsSummary {
  const ManagementOperationsSummary({
    required this.latestDayAmount,
    required this.latestDayPaymentCount,
    required this.latestDayUnableToPayCount,
    required this.unremittedAmount,
    required this.unremittedEntryCount,
    required this.pendingRemittanceAmount,
    required this.pendingRemittanceCount,
    required this.receivedRemittanceAmount,
    required this.receivedRemittanceCount,
    required this.correctionCount,
    required this.voidCount,
    this.latestCollectionDate,
  });

  final DateTime? latestCollectionDate;
  final double latestDayAmount;
  final int latestDayPaymentCount;
  final int latestDayUnableToPayCount;
  final double unremittedAmount;
  final int unremittedEntryCount;
  final double pendingRemittanceAmount;
  final int pendingRemittanceCount;
  final double receivedRemittanceAmount;
  final int receivedRemittanceCount;
  final int correctionCount;
  final int voidCount;

  factory ManagementOperationsSummary.fromPayload(Map<String, dynamic> payload) {
    return ManagementOperationsSummary(
      latestCollectionDate: _optionalDate(payload['latest_collection_date']),
      latestDayAmount: _requiredDouble(payload, 'latest_day_amount'),
      latestDayPaymentCount: _requiredInt(payload, 'latest_day_payment_count'),
      latestDayUnableToPayCount:
          _requiredInt(payload, 'latest_day_unable_to_pay_count'),
      unremittedAmount: _requiredDouble(payload, 'unremitted_amount'),
      unremittedEntryCount: _requiredInt(payload, 'unremitted_entry_count'),
      pendingRemittanceAmount:
          _requiredDouble(payload, 'pending_remittance_amount'),
      pendingRemittanceCount:
          _requiredInt(payload, 'pending_remittance_count'),
      receivedRemittanceAmount:
          _requiredDouble(payload, 'received_remittance_amount'),
      receivedRemittanceCount:
          _requiredInt(payload, 'received_remittance_count'),
      correctionCount: _requiredInt(payload, 'correction_count'),
      voidCount: _requiredInt(payload, 'void_count'),
    );
  }
}

class ManagementOperationEntry {
  const ManagementOperationEntry({
    required this.transactionId,
    required this.receiptNumber,
    required this.collectionDate,
    required this.acceptedAt,
    required this.clientCode,
    required this.clientName,
    required this.loanNumber,
    required this.loanTypeName,
    required this.collectorName,
    required this.entryType,
    required this.amount,
    required this.officialBalance,
    required this.coveredDates,
    required this.editVersion,
    required this.status,
    this.remittanceNumber,
    this.voidReason,
  });

  final String transactionId;
  final String receiptNumber;
  final DateTime collectionDate;
  final DateTime acceptedAt;
  final String clientCode;
  final String clientName;
  final String loanNumber;
  final String loanTypeName;
  final String collectorName;
  final String entryType;
  final double amount;
  final double officialBalance;
  final List<DateTime> coveredDates;
  final int editVersion;
  final String status;
  final String? remittanceNumber;
  final String? voidReason;

  String get statusLabel {
    return switch (status.toLowerCase()) {
      'received' => 'Received',
      'submitted' => 'Remittance submitted',
      'voided' => 'Voided',
      _ => 'Unremitted',
    };
  }

  factory ManagementOperationEntry.fromPayload(Map<String, dynamic> payload) {
    final rawCovered = payload['covered_dates'];
    if (rawCovered is! List) {
      throw const SpinaApiException(
        'The SPINA server returned invalid covered-date data.',
        code: 'invalid_management_operations_payload',
      );
    }
    return ManagementOperationEntry(
      transactionId: _requiredString(payload, 'transaction_id'),
      receiptNumber: _requiredString(payload, 'receipt_number'),
      collectionDate: _requiredDate(payload, 'collection_date'),
      acceptedAt: _requiredDate(payload, 'accepted_at'),
      clientCode: _requiredString(payload, 'client_code'),
      clientName: _requiredString(payload, 'client_name'),
      loanNumber: _requiredString(payload, 'loan_number'),
      loanTypeName: _requiredString(payload, 'loan_type_name'),
      collectorName: _requiredString(payload, 'collector_name'),
      entryType: _requiredString(payload, 'entry_type'),
      amount: _requiredDouble(payload, 'amount'),
      officialBalance: _requiredDouble(payload, 'official_balance'),
      coveredDates: rawCovered
          .map((value) => DateTime.parse(value.toString()))
          .toList(growable: false),
      editVersion: _requiredInt(payload, 'edit_version'),
      status: _requiredString(payload, 'status'),
      remittanceNumber: _optionalString(payload['remittance_number']),
      voidReason: _optionalString(payload['void_reason']),
    );
  }
}

class ManagementOperationAudit {
  const ManagementOperationAudit({
    required this.eventId,
    required this.eventType,
    required this.happenedAt,
    required this.transactionId,
    required this.receiptNumber,
    required this.clientName,
    required this.loanNumber,
    required this.actorName,
    required this.reason,
  });

  final String eventId;
  final String eventType;
  final DateTime happenedAt;
  final String transactionId;
  final String receiptNumber;
  final String clientName;
  final String loanNumber;
  final String actorName;
  final String reason;

  factory ManagementOperationAudit.fromPayload(Map<String, dynamic> payload) {
    return ManagementOperationAudit(
      eventId: _requiredString(payload, 'event_id'),
      eventType: _requiredString(payload, 'event_type'),
      happenedAt: _requiredDate(payload, 'happened_at'),
      transactionId: _requiredString(payload, 'transaction_id'),
      receiptNumber: _requiredString(payload, 'receipt_number'),
      clientName: _requiredString(payload, 'client_name'),
      loanNumber: _requiredString(payload, 'loan_number'),
      actorName: _requiredString(payload, 'actor_name'),
      reason: _requiredString(payload, 'reason'),
    );
  }
}

String _requiredString(Map<String, dynamic> payload, String key) {
  final value = _optionalString(payload[key]);
  if (value == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_management_operations_payload',
    );
  }
  return value;
}

String? _optionalString(Object? value) {
  final text = value?.toString().trim() ?? '';
  return text.isEmpty ? null : text;
}

double _requiredDouble(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value is num) {
    return value.toDouble();
  }
  final parsed = double.tryParse(value?.toString() ?? '');
  if (parsed == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_management_operations_payload',
    );
  }
  return parsed;
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
      code: 'invalid_management_operations_payload',
    );
  }
  return parsed;
}

DateTime _requiredDate(Map<String, dynamic> payload, String key) {
  final parsed = _optionalDate(payload[key]);
  if (parsed == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_management_operations_payload',
    );
  }
  return parsed;
}

DateTime? _optionalDate(Object? value) {
  final text = _optionalString(value);
  return text == null ? null : DateTime.tryParse(text);
}
