import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ClientRenewalPortal {
  const ClientRenewalPortal({
    required this.clientId,
    required this.clientCode,
    required this.clientName,
    required this.loans,
    required this.requests,
    required this.notice,
  });

  final String clientId;
  final String clientCode;
  final String clientName;
  final List<RenewalLoanOption> loans;
  final List<RenewalRequestItem> requests;
  final String notice;

  factory ClientRenewalPortal.fromPayload(Map<String, dynamic> payload) {
    final client = stringMap(payload['client']);
    final rawLoans = payload['loans'];
    final rawRequests = payload['requests'];
    if (client.isEmpty || rawLoans is! List || rawRequests is! List) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete renewal data.',
        code: 'invalid_renewal_payload',
      );
    }
    return ClientRenewalPortal(
      clientId: _requiredString(client, 'client_id'),
      clientCode: _requiredString(client, 'client_code'),
      clientName: _requiredString(client, 'client_name'),
      loans: rawLoans
          .map((item) => RenewalLoanOption.fromPayload(stringMap(item)))
          .toList(growable: false),
      requests: rawRequests
          .map((item) => RenewalRequestItem.fromPayload(stringMap(item)))
          .toList(growable: false),
      notice: _optionalString(payload['notice']) ??
          'Management must review every renewal request.',
    );
  }
}

class RenewalLoanOption {
  const RenewalLoanOption({
    required this.loanId,
    required this.loanNumber,
    required this.loanTypeName,
    required this.calculationMode,
    required this.principal,
    required this.remainingBalance,
    required this.paidAmount,
    required this.paidPercent,
    required this.dailyAmount,
    required this.dateReleased,
    required this.dueDate,
    required this.status,
    required this.eligible,
    required this.eligibilityMessage,
    this.pendingRequestId,
    this.blockingRequestStatus,
  });

  final String loanId;
  final String loanNumber;
  final String loanTypeName;
  final String calculationMode;
  final double principal;
  final double remainingBalance;
  final double paidAmount;
  final double paidPercent;
  final double dailyAmount;
  final DateTime dateReleased;
  final DateTime dueDate;
  final String status;
  final bool eligible;
  final String eligibilityMessage;
  final String? pendingRequestId;
  final String? blockingRequestStatus;

  bool get canRequest => eligible && pendingRequestId == null;

  bool get isAwaitingOfficeProcessing =>
      blockingRequestStatus?.toLowerCase() == 'approved';

  String get requestButtonLabel {
    if (isAwaitingOfficeProcessing) {
      return 'Office processing';
    }
    if (pendingRequestId != null) {
      return 'Request pending';
    }
    return eligible ? 'Request renewal' : 'Contact SPINA office';
  }

  factory RenewalLoanOption.fromPayload(Map<String, dynamic> payload) {
    return RenewalLoanOption(
      loanId: _requiredString(payload, 'loan_id'),
      loanNumber: _requiredString(payload, 'loan_number'),
      loanTypeName: _requiredString(payload, 'loan_type_name'),
      calculationMode: _requiredString(payload, 'calculation_mode'),
      principal: _requiredDouble(payload, 'principal'),
      remainingBalance: _requiredDouble(payload, 'remaining_balance'),
      paidAmount: _requiredDouble(payload, 'paid_amount'),
      paidPercent: _requiredDouble(payload, 'paid_percent'),
      dailyAmount: _requiredDouble(payload, 'daily_amount'),
      dateReleased: _requiredDate(payload, 'date_released'),
      dueDate: _requiredDate(payload, 'due_date'),
      status: _requiredString(payload, 'status'),
      eligible: payload['eligible'] == true,
      eligibilityMessage: _requiredString(payload, 'eligibility_message'),
      pendingRequestId: _optionalString(payload['pending_request_id']),
      blockingRequestStatus:
          _optionalString(payload['blocking_request_status']),
    );
  }
}

class RenewalRequestItem {
  const RenewalRequestItem({
    required this.requestId,
    required this.clientId,
    required this.clientCode,
    required this.clientName,
    required this.loanId,
    required this.loanNumber,
    required this.loanTypeName,
    required this.currentPrincipal,
    required this.remainingBalance,
    required this.requestedAmount,
    required this.clientMessage,
    required this.status,
    required this.submittedAt,
    required this.reviewNote,
    this.reviewedAt,
    this.reviewedByName,
    this.cancelledAt,
  });

  final String requestId;
  final String clientId;
  final String clientCode;
  final String clientName;
  final String loanId;
  final String loanNumber;
  final String loanTypeName;
  final double currentPrincipal;
  final double remainingBalance;
  final double requestedAmount;
  final String clientMessage;
  final String status;
  final DateTime submittedAt;
  final DateTime? reviewedAt;
  final String? reviewedByName;
  final String reviewNote;
  final DateTime? cancelledAt;

  bool get isPending => status.toLowerCase() == 'pending';

  String get statusLabel {
    return switch (status.toLowerCase()) {
      'approved' => 'Approved for office processing',
      'rejected' => 'Rejected',
      'cancelled' => 'Cancelled',
      _ => 'Pending review',
    };
  }

  factory RenewalRequestItem.fromPayload(Map<String, dynamic> payload) {
    return RenewalRequestItem(
      requestId: _requiredString(payload, 'request_id'),
      clientId: _requiredString(payload, 'client_id'),
      clientCode: _requiredString(payload, 'client_code'),
      clientName: _requiredString(payload, 'client_name'),
      loanId: _requiredString(payload, 'loan_id'),
      loanNumber: _requiredString(payload, 'loan_number'),
      loanTypeName: _requiredString(payload, 'loan_type_name'),
      currentPrincipal: _requiredDouble(payload, 'current_principal'),
      remainingBalance: _requiredDouble(payload, 'remaining_balance'),
      requestedAmount: _requiredDouble(payload, 'requested_amount'),
      clientMessage: _optionalString(payload['client_message']) ?? '',
      status: _requiredString(payload, 'status'),
      submittedAt: _requiredDate(payload, 'submitted_at'),
      reviewedAt: _optionalDate(payload['reviewed_at']),
      reviewedByName: _optionalString(payload['reviewed_by_name']),
      reviewNote: _optionalString(payload['review_note']) ?? '',
      cancelledAt: _optionalDate(payload['cancelled_at']),
    );
  }
}

String _requiredString(Map<String, dynamic> payload, String key) {
  final value = _optionalString(payload[key]);
  if (value == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_renewal_payload',
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
      code: 'invalid_renewal_payload',
    );
  }
  return parsed;
}

DateTime _requiredDate(Map<String, dynamic> payload, String key) {
  final parsed = _optionalDate(payload[key]);
  if (parsed == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_renewal_payload',
    );
  }
  return parsed;
}

DateTime? _optionalDate(Object? value) {
  final text = _optionalString(value);
  return text == null ? null : DateTime.tryParse(text);
}
