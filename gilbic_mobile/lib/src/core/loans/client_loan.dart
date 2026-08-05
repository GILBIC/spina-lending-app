import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ClientLoanPortfolio {
  const ClientLoanPortfolio({
    required this.clientId,
    required this.clientCode,
    required this.clientName,
    required this.clientStatus,
    required this.loans,
    this.area,
  });

  final String clientId;
  final String clientCode;
  final String clientName;
  final String? area;
  final String clientStatus;
  final List<ClientLoan> loans;

  factory ClientLoanPortfolio.fromPayload(Map<String, dynamic> payload) {
    final client = stringMap(payload['client']);
    final rawLoans = payload['loans'];
    if (client.isEmpty || rawLoans is! List) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete loan data.',
        code: 'invalid_client_loan_payload',
      );
    }
    return ClientLoanPortfolio(
      clientId: requiredString(client, 'client_id'),
      clientCode: requiredString(client, 'client_code'),
      clientName: requiredString(client, 'client_name'),
      area: optionalString(client['area']),
      clientStatus: requiredString(client, 'status'),
      loans: rawLoans
          .map((item) => ClientLoan.fromPayload(stringMap(item)))
          .toList(growable: false),
    );
  }

  List<ClientLoan> get activeLoans => loans
      .where((loan) => loan.status.toLowerCase() == 'active')
      .toList(growable: false);

  List<ClientLoan> get previousLoans => loans
      .where((loan) => loan.status.toLowerCase() != 'active')
      .toList(growable: false);
}

class ClientLoan {
  const ClientLoan({
    required this.loanId,
    required this.loanNumber,
    required this.loanTypeName,
    required this.principal,
    required this.dailyAmount,
    required this.status,
    required this.remainingBalance,
    required this.paidAmount,
    required this.passCount,
    required this.stateVersion,
    required this.paymentCount,
    this.loanTypeCode,
    this.interestRate,
    this.dateReleased,
    this.dueDate,
    this.lastPaymentDate,
    this.advanceUntil,
  });

  final String loanId;
  final String loanNumber;
  final String? loanTypeCode;
  final String loanTypeName;
  final double principal;
  final double dailyAmount;
  final double? interestRate;
  final DateTime? dateReleased;
  final DateTime? dueDate;
  final String status;
  final double remainingBalance;
  final double paidAmount;
  final int passCount;
  final DateTime? lastPaymentDate;
  final DateTime? advanceUntil;
  final int stateVersion;
  final int paymentCount;

  factory ClientLoan.fromPayload(Map<String, dynamic> payload) {
    if (payload.isEmpty) {
      throw const SpinaApiException(
        'The SPINA server returned an empty loan record.',
        code: 'invalid_client_loan_record',
      );
    }
    return ClientLoan(
      loanId: requiredString(payload, 'loan_id'),
      loanNumber: requiredString(payload, 'loan_number'),
      loanTypeCode: optionalString(payload['loan_type_code']),
      loanTypeName: requiredString(payload, 'loan_type_name'),
      principal: requiredDouble(payload, 'principal'),
      dailyAmount: requiredDouble(payload, 'daily_amount'),
      interestRate: optionalDouble(payload['interest_rate']),
      dateReleased: optionalDate(payload['date_released']),
      dueDate: optionalDate(payload['due_date']),
      status: requiredString(payload, 'status'),
      remainingBalance: requiredDouble(payload, 'remaining_balance'),
      paidAmount: requiredDouble(payload, 'paid_amount'),
      passCount: requiredInt(payload, 'pass_count'),
      lastPaymentDate: optionalDate(payload['last_payment_date']),
      advanceUntil: optionalDate(payload['advance_until']),
      stateVersion: requiredInt(payload, 'state_version'),
      paymentCount: requiredInt(payload, 'payment_count'),
    );
  }

  double get progress {
    if (principal <= 0) {
      return 0;
    }
    return (paidAmount / principal).clamp(0, 1).toDouble();
  }

  bool get isSevenBySeven {
    final normalized = '${loanTypeCode ?? ''} $loanTypeName'.toLowerCase();
    return normalized.contains('7x7') || normalized.contains('seven_by_seven');
  }
}

String requiredString(Map<String, dynamic> payload, String key) {
  final value = optionalString(payload[key]);
  if (value == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_client_loan_payload',
    );
  }
  return value;
}

String? optionalString(Object? value) {
  final text = value?.toString().trim() ?? '';
  return text.isEmpty ? null : text;
}

double requiredDouble(Map<String, dynamic> payload, String key) {
  final value = optionalDouble(payload[key]);
  if (value == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_client_loan_payload',
    );
  }
  return value;
}

double? optionalDouble(Object? value) {
  if (value is num) {
    return value.toDouble();
  }
  return double.tryParse(value?.toString() ?? '');
}

int requiredInt(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value is int) {
    return value;
  }
  final parsed = int.tryParse(value?.toString() ?? '');
  if (parsed == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_client_loan_payload',
    );
  }
  return parsed;
}

DateTime? optionalDate(Object? value) {
  final text = optionalString(value);
  return text == null ? null : DateTime.tryParse(text);
}
