import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class FinancialStatementLine {
  const FinancialStatementLine({
    required this.accountCode,
    required this.accountName,
    required this.amount,
  });

  final String accountCode;
  final String accountName;
  final double amount;

  factory FinancialStatementLine.fromPayload(Map<String, dynamic> payload) {
    return FinancialStatementLine(
      accountCode: _requiredString(payload, 'account_code'),
      accountName: _requiredString(payload, 'account_name'),
      amount: _requiredDouble(payload, 'amount'),
    );
  }
}

class FinancialStatementPeriod {
  const FinancialStatementPeriod({
    required this.periodId,
    required this.label,
    required this.startDate,
    required this.endDate,
    required this.status,
  });

  final String periodId;
  final String label;
  final DateTime startDate;
  final DateTime endDate;
  final String status;

  factory FinancialStatementPeriod.fromPayload(Map<String, dynamic> payload) {
    return FinancialStatementPeriod(
      periodId: _requiredString(payload, 'period_id'),
      label: _requiredString(payload, 'label'),
      startDate: _requiredDate(payload, 'start_date'),
      endDate: _requiredDate(payload, 'end_date'),
      status: _requiredString(payload, 'status'),
    );
  }
}

class ProfitOrLossStatement {
  const ProfitOrLossStatement({
    required this.incomeLines,
    required this.expenseLines,
    required this.totalIncome,
    required this.totalExpenses,
    required this.netIncome,
  });

  final List<FinancialStatementLine> incomeLines;
  final List<FinancialStatementLine> expenseLines;
  final double totalIncome;
  final double totalExpenses;
  final double netIncome;

  factory ProfitOrLossStatement.fromPayload(Map<String, dynamic> payload) {
    return ProfitOrLossStatement(
      incomeLines: _lines(payload['income_lines']),
      expenseLines: _lines(payload['expense_lines']),
      totalIncome: _requiredDouble(payload, 'total_income'),
      totalExpenses: _requiredDouble(payload, 'total_expenses'),
      netIncome: _requiredDouble(payload, 'net_income'),
    );
  }
}

class FinancialPositionStatement {
  const FinancialPositionStatement({
    required this.asOfDate,
    required this.assetLines,
    required this.liabilityLines,
    required this.equityLines,
    required this.totalAssets,
    required this.totalLiabilities,
    required this.recordedEquity,
    required this.unclosedEarningsToDate,
    required this.totalEquity,
    required this.totalLiabilitiesAndEquity,
    required this.balanced,
  });

  final DateTime asOfDate;
  final List<FinancialStatementLine> assetLines;
  final List<FinancialStatementLine> liabilityLines;
  final List<FinancialStatementLine> equityLines;
  final double totalAssets;
  final double totalLiabilities;
  final double recordedEquity;
  final double unclosedEarningsToDate;
  final double totalEquity;
  final double totalLiabilitiesAndEquity;
  final bool balanced;

  factory FinancialPositionStatement.fromPayload(Map<String, dynamic> payload) {
    return FinancialPositionStatement(
      asOfDate: _requiredDate(payload, 'as_of_date'),
      assetLines: _lines(payload['asset_lines']),
      liabilityLines: _lines(payload['liability_lines']),
      equityLines: _lines(payload['equity_lines']),
      totalAssets: _requiredDouble(payload, 'total_assets'),
      totalLiabilities: _requiredDouble(payload, 'total_liabilities'),
      recordedEquity: _requiredDouble(payload, 'recorded_equity'),
      unclosedEarningsToDate:
          _requiredDouble(payload, 'unclosed_earnings_to_date'),
      totalEquity: _requiredDouble(payload, 'total_equity'),
      totalLiabilitiesAndEquity:
          _requiredDouble(payload, 'total_liabilities_and_equity'),
      balanced: payload['balanced'] == true,
    );
  }
}

class AccountingFinancialStatements {
  const AccountingFinancialStatements({
    required this.period,
    required this.profitOrLoss,
    required this.financialPosition,
    required this.source,
    required this.notice,
  });

  final FinancialStatementPeriod period;
  final ProfitOrLossStatement profitOrLoss;
  final FinancialPositionStatement financialPosition;
  final String source;
  final String notice;

  factory AccountingFinancialStatements.fromPayload(Map<String, dynamic> payload) {
    return AccountingFinancialStatements(
      period: FinancialStatementPeriod.fromPayload(stringMap(payload['period'])),
      profitOrLoss:
          ProfitOrLossStatement.fromPayload(stringMap(payload['profit_or_loss'])),
      financialPosition: FinancialPositionStatement.fromPayload(
        stringMap(payload['financial_position']),
      ),
      source: _requiredString(payload, 'source'),
      notice: _requiredString(payload, 'notice'),
    );
  }
}

List<FinancialStatementLine> _lines(Object? raw) {
  if (raw is! List) {
    throw const SpinaApiException(
      'The SPINA server returned incomplete Financial Statement data.',
      code: 'invalid_financial_statement_payload',
    );
  }
  return raw
      .map((item) => FinancialStatementLine.fromPayload(stringMap(item)))
      .toList(growable: false);
}

String _requiredString(Map<String, dynamic> payload, String key) {
  final value = payload[key]?.toString().trim();
  if (value == null || value.isEmpty) {
    throw const SpinaApiException(
      'The SPINA server returned incomplete Financial Statement data.',
      code: 'invalid_financial_statement_payload',
    );
  }
  return value;
}

double _requiredDouble(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value is num) {
    return value.toDouble();
  }
  final parsed = double.tryParse(value?.toString() ?? '');
  if (parsed == null) {
    throw const SpinaApiException(
      'The SPINA server returned incomplete Financial Statement data.',
      code: 'invalid_financial_statement_payload',
    );
  }
  return parsed;
}

DateTime _requiredDate(Map<String, dynamic> payload, String key) {
  final parsed = DateTime.tryParse(payload[key]?.toString() ?? '');
  if (parsed == null) {
    throw const SpinaApiException(
      'The SPINA server returned incomplete Financial Statement data.',
      code: 'invalid_financial_statement_payload',
    );
  }
  return parsed;
}
