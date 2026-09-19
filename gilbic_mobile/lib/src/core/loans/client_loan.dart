import 'package:gilbic_mobile/src/core/network/spina_api.dart';

final RegExp _decimalTextPattern = RegExp(r'^[+-]?\d+(?:\.\d+)?$');

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
    this.firstPaymentDate,
    this.lastPaymentDate,
    this.advanceUntil,
  });

  final String loanId;
  final String loanNumber;
  final String? loanTypeCode;
  final String loanTypeName;
  final String principal;
  final String dailyAmount;
  final String? interestRate;
  final DateTime? dateReleased;
  final DateTime? dueDate;
  final DateTime? firstPaymentDate;
  final String status;
  final String remainingBalance;
  final String paidAmount;
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
      principal: requiredDecimalText(payload, 'principal'),
      dailyAmount: requiredDecimalText(payload, 'daily_amount'),
      interestRate: optionalDecimalText(payload['interest_rate']),
      dateReleased: optionalDate(payload['date_released']),
      dueDate: optionalDate(payload['due_date']),
      firstPaymentDate: optionalDate(payload['first_payment_date']),
      status: requiredString(payload, 'status'),
      remainingBalance: requiredDecimalText(payload, 'remaining_balance'),
      paidAmount: requiredDecimalText(payload, 'paid_amount'),
      passCount: requiredInt(payload, 'pass_count'),
      lastPaymentDate: optionalDate(payload['last_payment_date']),
      advanceUntil: optionalDate(payload['advance_until']),
      stateVersion: requiredInt(payload, 'state_version'),
      paymentCount: requiredInt(payload, 'payment_count'),
    );
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

String requiredDecimalText(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value is! String) {
    throw SpinaApiException(
      'The SPINA server returned invalid $key.',
      code: 'invalid_client_loan_payload',
    );
  }
  final text = value.trim();
  if (!_decimalTextPattern.hasMatch(text)) {
    throw SpinaApiException(
      'The SPINA server returned invalid $key.',
      code: 'invalid_client_loan_payload',
    );
  }
  return text;
}

String? optionalDecimalText(Object? value) {
  if (value == null) {
    return null;
  }
  if (value is! String) {
    throw const SpinaApiException(
      'The SPINA server returned invalid decimal data.',
      code: 'invalid_client_loan_payload',
    );
  }
  final text = value.trim();
  if (!_decimalTextPattern.hasMatch(text)) {
    throw const SpinaApiException(
      'The SPINA server returned invalid decimal data.',
      code: 'invalid_client_loan_payload',
    );
  }
  return text;
}

String formatClientLoanMoney(String value) {
  final text = value.trim();
  final match = RegExp(r'^([+-]?)(\d+)(?:\.(\d+))?$').firstMatch(text);
  if (match == null) {
    return text;
  }
  final sign = match.group(1) ?? '';
  final whole = match.group(2) ?? '0';
  final rawFraction = match.group(3);
  final fraction = rawFraction == null
      ? '00'
      : rawFraction.length == 1
          ? '${rawFraction}0'
          : rawFraction;
  final grouped = whole.replaceAllMapped(
    RegExp(r'\B(?=(\d{3})+(?!\d))'),
    (_) => ',',
  );
  return '${sign == '-' ? '-' : sign == '+' ? '+' : ''}₱$grouped.$fraction';
}

String formatClientLoanRate(String value) {
  final text = value.trim();
  if (!_decimalTextPattern.hasMatch(text)) {
    return text;
  }
  if (!text.contains('.')) {
    return text;
  }
  final trimmed = text.replaceFirst(RegExp(r'0+$'), '').replaceFirst(RegExp(r'\.$'), '');
  return trimmed;
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
