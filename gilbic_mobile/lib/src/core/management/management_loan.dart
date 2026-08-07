import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ManagementLoanPortfolio {
  const ManagementLoanPortfolio({
    required this.summary,
    required this.loans,
    required this.notice,
  });

  final ManagementLoanSummary summary;
  final List<ManagementLoanItem> loans;
  final String notice;

  factory ManagementLoanPortfolio.fromPayload(Map<String, dynamic> payload) {
    final rawLoans = payload['loans'];
    if (rawLoans is! List) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete Loan Management data.',
        code: 'invalid_management_loan_payload',
      );
    }
    return ManagementLoanPortfolio(
      summary: ManagementLoanSummary.fromPayload(stringMap(payload['summary'])),
      loans: rawLoans
          .map((item) => ManagementLoanItem.fromPayload(stringMap(item)))
          .toList(growable: false),
      notice: _optionalString(payload['notice']) ??
          'Loan Management is view-only in mobile.',
    );
  }
}

class ManagementLoanSummary {
  const ManagementLoanSummary({
    required this.activeLoanCount,
    required this.activeClientCount,
    required this.activePrincipalTotal,
    required this.activeRemainingTotal,
    required this.overdueActiveCount,
    required this.activeSevenBySevenCount,
    required this.approvedRenewalCount,
  });

  final int activeLoanCount;
  final int activeClientCount;
  final double activePrincipalTotal;
  final double activeRemainingTotal;
  final int overdueActiveCount;
  final int activeSevenBySevenCount;
  final int approvedRenewalCount;

  factory ManagementLoanSummary.fromPayload(Map<String, dynamic> payload) {
    return ManagementLoanSummary(
      activeLoanCount: _requiredInt(payload, 'active_loan_count'),
      activeClientCount: _requiredInt(payload, 'active_client_count'),
      activePrincipalTotal: _requiredDouble(payload, 'active_principal_total'),
      activeRemainingTotal: _requiredDouble(payload, 'active_remaining_total'),
      overdueActiveCount: _requiredInt(payload, 'overdue_active_count'),
      activeSevenBySevenCount:
          _requiredInt(payload, 'active_seven_by_seven_count'),
      approvedRenewalCount: _requiredInt(payload, 'approved_renewal_count'),
    );
  }
}

class ManagementLoanItem {
  const ManagementLoanItem({
    required this.loanId,
    required this.loanNumber,
    required this.clientId,
    required this.clientCode,
    required this.clientName,
    required this.clientStatus,
    required this.loanTypeName,
    required this.calculationMode,
    required this.principal,
    required this.dailyAmount,
    required this.remainingBalance,
    required this.paidAmount,
    required this.paidPercent,
    required this.loanStatus,
    required this.passCount,
    required this.paymentCount,
    required this.stateVersion,
    required this.isOverdue,
    this.clientArea,
    this.loanTypeCode,
    this.interestRate,
    this.dateReleased,
    this.dueDate,
    this.lastPaymentDate,
    this.advanceUntil,
    this.renewalRequestStatus,
  });

  final String loanId;
  final String loanNumber;
  final String clientId;
  final String clientCode;
  final String clientName;
  final String? clientArea;
  final String clientStatus;
  final String? loanTypeCode;
  final String loanTypeName;
  final String calculationMode;
  final double principal;
  final double dailyAmount;
  final double? interestRate;
  final double remainingBalance;
  final double paidAmount;
  final double paidPercent;
  final DateTime? dateReleased;
  final DateTime? dueDate;
  final String loanStatus;
  final DateTime? lastPaymentDate;
  final DateTime? advanceUntil;
  final int passCount;
  final int paymentCount;
  final int stateVersion;
  final String? renewalRequestStatus;
  final bool isOverdue;

  bool get isSevenBySeven => calculationMode.toLowerCase() == 'seven_by_seven';

  factory ManagementLoanItem.fromPayload(Map<String, dynamic> payload) {
    return ManagementLoanItem(
      loanId: _requiredString(payload, 'loan_id'),
      loanNumber: _requiredString(payload, 'loan_number'),
      clientId: _requiredString(payload, 'client_id'),
      clientCode: _requiredString(payload, 'client_code'),
      clientName: _requiredString(payload, 'client_name'),
      clientArea: _optionalString(payload['client_area']),
      clientStatus: _requiredString(payload, 'client_status'),
      loanTypeCode: _optionalString(payload['loan_type_code']),
      loanTypeName: _requiredString(payload, 'loan_type_name'),
      calculationMode: _requiredString(payload, 'calculation_mode'),
      principal: _requiredDouble(payload, 'principal'),
      dailyAmount: _requiredDouble(payload, 'daily_amount'),
      interestRate: _optionalDouble(payload['interest_rate']),
      remainingBalance: _requiredDouble(payload, 'remaining_balance'),
      paidAmount: _requiredDouble(payload, 'paid_amount'),
      paidPercent: _requiredDouble(payload, 'paid_percent'),
      dateReleased: _optionalDate(payload['date_released']),
      dueDate: _optionalDate(payload['due_date']),
      loanStatus: _requiredString(payload, 'loan_status'),
      lastPaymentDate: _optionalDate(payload['last_payment_date']),
      advanceUntil: _optionalDate(payload['advance_until']),
      passCount: _requiredInt(payload, 'pass_count'),
      paymentCount: _requiredInt(payload, 'payment_count'),
      stateVersion: _requiredInt(payload, 'state_version'),
      renewalRequestStatus:
          _optionalString(payload['renewal_request_status']),
      isOverdue: payload['is_overdue'] == true,
    );
  }
}

String _requiredString(Map<String, dynamic> payload, String key) {
  final value = _optionalString(payload[key]);
  if (value == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_management_loan_payload',
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
      code: 'invalid_management_loan_payload',
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
      code: 'invalid_management_loan_payload',
    );
  }
  return parsed;
}

DateTime? _optionalDate(Object? value) {
  final text = _optionalString(value);
  return text == null ? null : DateTime.tryParse(text);
}
