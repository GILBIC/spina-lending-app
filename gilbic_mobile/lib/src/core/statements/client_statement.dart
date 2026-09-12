import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ClientStatement {
  const ClientStatement({
    required this.clientCode,
    required this.clientName,
    required this.loans,
    required this.payments,
  });

  final String clientCode;
  final String clientName;
  final List<ClientStatementLoan> loans;
  final List<ClientStatementPayment> payments;

  factory ClientStatement.fromPayload(Map<String, dynamic> payload) {
    final client = stringMap(payload['client']);
    final rawLoans = payload['loans'];
    final rawPayments = payload['payments'];
    if (client.isEmpty || rawLoans is! List || rawPayments is! List) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete statement data.',
        code: 'invalid_client_statement_payload',
      );
    }
    return ClientStatement(
      clientCode: _requiredText(client, 'client_code'),
      clientName: _requiredText(client, 'client_name'),
      loans: rawLoans
          .map((item) => ClientStatementLoan.fromPayload(stringMap(item)))
          .toList(growable: false),
      payments: rawPayments
          .map((item) => ClientStatementPayment.fromPayload(stringMap(item)))
          .toList(growable: false),
    );
  }
}

class ClientStatementLoan {
  const ClientStatementLoan({
    required this.loanNumber,
    required this.loanTypeName,
    required this.principal,
    required this.remainingBalance,
    required this.status,
  });

  final String loanNumber;
  final String loanTypeName;
  final String principal;
  final String remainingBalance;
  final String status;

  factory ClientStatementLoan.fromPayload(Map<String, dynamic> payload) {
    return ClientStatementLoan(
      loanNumber: _requiredText(payload, 'loan_number'),
      loanTypeName: _requiredText(payload, 'loan_type_name'),
      principal: _requiredMoney(payload, 'principal'),
      remainingBalance: _requiredMoney(payload, 'remaining_balance'),
      status: _requiredText(payload, 'status'),
    );
  }
}

class ClientStatementPayment {
  const ClientStatementPayment({
    required this.receiptNumber,
    required this.loanNumber,
    required this.collectionDate,
    required this.amount,
    required this.status,
    required this.isVoided,
    this.officialBalance,
  });

  final String receiptNumber;
  final String loanNumber;
  final DateTime collectionDate;
  final String amount;
  final String? officialBalance;
  final String status;
  final bool isVoided;

  factory ClientStatementPayment.fromPayload(Map<String, dynamic> payload) {
    final dateText = _requiredText(payload, 'collection_date');
    final collectionDate = DateTime.tryParse(dateText);
    if (collectionDate == null) {
      throw const SpinaApiException(
        'The SPINA server returned an invalid statement date.',
        code: 'invalid_client_statement_payload',
      );
    }
    return ClientStatementPayment(
      receiptNumber: _requiredText(payload, 'receipt_number'),
      loanNumber: _requiredText(payload, 'loan_number'),
      collectionDate: collectionDate,
      amount: _requiredMoney(payload, 'amount'),
      officialBalance: _optionalMoney(payload['official_balance']),
      status: _requiredText(payload, 'status'),
      isVoided: payload['is_voided'] == true,
    );
  }
}

String _requiredText(Map<String, dynamic> payload, String key) {
  final text = payload[key]?.toString().trim() ?? '';
  if (text.isEmpty) {
    throw const SpinaApiException(
      'The SPINA server returned incomplete statement data.',
      code: 'invalid_client_statement_payload',
    );
  }
  return text;
}

String _requiredMoney(Map<String, dynamic> payload, String key) {
  final value = _optionalMoney(payload[key]);
  if (value == null) {
    throw const SpinaApiException(
      'The SPINA server returned invalid statement money data.',
      code: 'invalid_client_statement_payload',
    );
  }
  return value;
}

String? _optionalMoney(Object? value) {
  if (value == null) return null;
  if (value is! String) {
    throw const SpinaApiException(
      'The SPINA server returned invalid statement money data.',
      code: 'invalid_client_statement_payload',
    );
  }
  final text = value.trim();
  if (!RegExp(r'^[+-]?\d+(?:\.\d+)?$').hasMatch(text)) {
    throw const SpinaApiException(
      'The SPINA server returned invalid statement money data.',
      code: 'invalid_client_statement_payload',
    );
  }
  return text;
}
