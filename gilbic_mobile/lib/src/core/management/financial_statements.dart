import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/management/reporting_evidence.dart';

class FinancialStatementLine {
  const FinancialStatementLine({
    required this.accountCode,
    required this.accountName,
    required this.amount,
  });

  final String accountCode;
  final String accountName;
  final String amount;

  factory FinancialStatementLine.fromPayload(Map<String, dynamic> payload) {
    return FinancialStatementLine(
      accountCode: _requiredString(payload, 'account_code'),
      accountName: _requiredString(payload, 'account_name'),
      amount: _requiredMoney(payload, 'amount'),
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
  final String totalIncome;
  final String totalExpenses;
  final String netIncome;

  factory ProfitOrLossStatement.fromPayload(Map<String, dynamic> payload) {
    return ProfitOrLossStatement(
      incomeLines: _lines(payload['income_lines']),
      expenseLines: _lines(payload['expense_lines']),
      totalIncome: _requiredMoney(payload, 'total_income'),
      totalExpenses: _requiredMoney(payload, 'total_expenses'),
      netIncome: _requiredMoney(payload, 'net_income'),
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
  final String totalAssets;
  final String totalLiabilities;
  final String recordedEquity;
  final String unclosedEarningsToDate;
  final String totalEquity;
  final String totalLiabilitiesAndEquity;
  final bool balanced;

  factory FinancialPositionStatement.fromPayload(Map<String, dynamic> payload) {
    return FinancialPositionStatement(
      asOfDate: _requiredDate(payload, 'as_of_date'),
      assetLines: _lines(payload['asset_lines']),
      liabilityLines: _lines(payload['liability_lines']),
      equityLines: _lines(payload['equity_lines']),
      totalAssets: _requiredMoney(payload, 'total_assets'),
      totalLiabilities: _requiredMoney(payload, 'total_liabilities'),
      recordedEquity: _requiredMoney(payload, 'recorded_equity'),
      unclosedEarningsToDate: _requiredMoney(
        payload,
        'unclosed_earnings_to_date',
      ),
      totalEquity: _requiredMoney(payload, 'total_equity'),
      totalLiabilitiesAndEquity: _requiredMoney(
        payload,
        'total_liabilities_and_equity',
      ),
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
    this.reportingSupplement,
  });

  final FinancialStatementPeriod period;
  final ProfitOrLossStatement profitOrLoss;
  final FinancialPositionStatement financialPosition;
  final String source;
  final String notice;
  final Map<String, dynamic>? reportingSupplement;

  factory AccountingFinancialStatements.fromPayload(
    Map<String, dynamic> payload,
  ) {
    return AccountingFinancialStatements(
      period: FinancialStatementPeriod.fromPayload(
        stringMap(payload['period']),
      ),
      profitOrLoss: ProfitOrLossStatement.fromPayload(
        stringMap(payload['profit_or_loss']),
      ),
      financialPosition: FinancialPositionStatement.fromPayload(
        stringMap(payload['financial_position']),
      ),
      source: _requiredString(payload, 'source'),
      notice: _requiredString(payload, 'notice'),
      reportingSupplement: payload['reporting_supplement'] == null
          ? null
          : validateReportingSupplement(
              stringMap(payload['reporting_supplement']),
            ),
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

String _requiredMoney(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value is! String ||
      !RegExp(r'^-?(0|[1-9][0-9]*)\.[0-9]{2}$').hasMatch(value)) {
    throw const SpinaApiException(
      'The SPINA server returned incomplete Financial Statement data.',
      code: 'invalid_financial_statement_payload',
    );
  }
  return value;
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
