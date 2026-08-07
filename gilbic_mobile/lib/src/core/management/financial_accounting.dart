import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class FinancialAccountingOverview {
  const FinancialAccountingOverview({
    required this.summary,
    required this.policies,
    required this.journalStatus,
    required this.trialBalanceStatus,
    required this.notice,
  });

  final FinancialAccountingSummary summary;
  final List<LoanAccountingPolicy> policies;
  final String journalStatus;
  final String trialBalanceStatus;
  final String notice;

  factory FinancialAccountingOverview.fromPayload(Map<String, dynamic> payload) {
    final rawPolicies = payload['policies'];
    if (rawPolicies is! List) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete Financial Accounting data.',
        code: 'invalid_financial_accounting_payload',
      );
    }
    return FinancialAccountingOverview(
      summary: FinancialAccountingSummary.fromPayload(
        stringMap(payload['summary']),
      ),
      policies: rawPolicies
          .map((item) => LoanAccountingPolicy.fromPayload(stringMap(item)))
          .toList(growable: false),
      journalStatus: _requiredString(payload, 'journal_status'),
      trialBalanceStatus: _requiredString(payload, 'trial_balance_status'),
      notice: _requiredString(payload, 'notice'),
    );
  }
}

class FinancialAccountingSummary {
  const FinancialAccountingSummary({
    required this.activeLoanCount,
    required this.activePrincipal,
    required this.operationalOutstanding,
    required this.regularOutstanding,
    required this.sevenBySevenOutstanding,
    required this.unremittedCash,
    required this.receivedRemittanceTotal,
    required this.validCollectionCount,
    required this.correctionCount,
    required this.voidCount,
  });

  final int activeLoanCount;
  final double activePrincipal;
  final double operationalOutstanding;
  final double regularOutstanding;
  final double sevenBySevenOutstanding;
  final double unremittedCash;
  final double receivedRemittanceTotal;
  final int validCollectionCount;
  final int correctionCount;
  final int voidCount;

  factory FinancialAccountingSummary.fromPayload(Map<String, dynamic> payload) {
    return FinancialAccountingSummary(
      activeLoanCount: _requiredInt(payload, 'active_loan_count'),
      activePrincipal: _requiredDouble(payload, 'active_principal'),
      operationalOutstanding:
          _requiredDouble(payload, 'operational_outstanding'),
      regularOutstanding: _requiredDouble(payload, 'regular_outstanding'),
      sevenBySevenOutstanding:
          _requiredDouble(payload, 'seven_by_seven_outstanding'),
      unremittedCash: _requiredDouble(payload, 'unremitted_cash'),
      receivedRemittanceTotal:
          _requiredDouble(payload, 'received_remittance_total'),
      validCollectionCount: _requiredInt(payload, 'valid_collection_count'),
      correctionCount: _requiredInt(payload, 'correction_count'),
      voidCount: _requiredInt(payload, 'void_count'),
    );
  }
}

class LoanAccountingPolicy {
  const LoanAccountingPolicy({
    required this.code,
    required this.name,
    required this.termDays,
    required this.calculationMode,
    required this.dailyInterestPer1000,
    required this.mobileCollectionsEnabled,
    required this.operationalRule,
    required this.accountingRule,
    required this.renewalRule,
  });

  final String code;
  final String name;
  final int termDays;
  final String calculationMode;
  final double dailyInterestPer1000;
  final bool mobileCollectionsEnabled;
  final String operationalRule;
  final String accountingRule;
  final String renewalRule;

  factory LoanAccountingPolicy.fromPayload(Map<String, dynamic> payload) {
    return LoanAccountingPolicy(
      code: _requiredString(payload, 'code'),
      name: _requiredString(payload, 'name'),
      termDays: _requiredInt(payload, 'term_days'),
      calculationMode: _requiredString(payload, 'calculation_mode'),
      dailyInterestPer1000:
          _requiredDouble(payload, 'daily_interest_per_1000'),
      mobileCollectionsEnabled:
          payload['mobile_collections_enabled'] == true,
      operationalRule: _requiredString(payload, 'operational_rule'),
      accountingRule: _requiredString(payload, 'accounting_rule'),
      renewalRule: _requiredString(payload, 'renewal_rule'),
    );
  }
}

String _requiredString(Map<String, dynamic> payload, String key) {
  final value = payload[key]?.toString().trim() ?? '';
  if (value.isEmpty) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_financial_accounting_payload',
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
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_financial_accounting_payload',
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
      code: 'invalid_financial_accounting_payload',
    );
  }
  return parsed;
}
