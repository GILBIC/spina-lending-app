import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class FinancialAccountingOverview {
  const FinancialAccountingOverview({
    required this.summary,
    required this.foundation,
    required this.accounts,
    required this.fiscalPeriods,
    required this.policies,
    required this.foundationStatus,
    required this.fiscalPeriodStatus,
    required this.periodManagementEnabled,
    required this.journalStatus,
    required this.trialBalanceStatus,
    required this.notice,
  });

  final FinancialAccountingSummary summary;
  final AccountingFoundationSummary foundation;
  final List<AccountingAccount> accounts;
  final List<AccountingFiscalPeriod> fiscalPeriods;
  final List<LoanAccountingPolicy> policies;
  final String foundationStatus;
  final String fiscalPeriodStatus;
  final bool periodManagementEnabled;
  final String journalStatus;
  final String trialBalanceStatus;
  final String notice;

  factory FinancialAccountingOverview.fromPayload(Map<String, dynamic> payload) {
    final rawPolicies = payload['policies'];
    final rawAccounts = payload['accounts'];
    final rawFiscalPeriods = payload['fiscal_periods'];
    if (rawPolicies is! List ||
        rawAccounts is! List ||
        rawFiscalPeriods is! List) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete Financial Accounting data.',
        code: 'invalid_financial_accounting_payload',
      );
    }
    return FinancialAccountingOverview(
      summary: FinancialAccountingSummary.fromPayload(
        stringMap(payload['summary']),
      ),
      foundation: AccountingFoundationSummary.fromPayload(
        stringMap(payload['foundation']),
      ),
      accounts: rawAccounts
          .map((item) => AccountingAccount.fromPayload(stringMap(item)))
          .toList(growable: false),
      fiscalPeriods: rawFiscalPeriods
          .map((item) => AccountingFiscalPeriod.fromPayload(stringMap(item)))
          .toList(growable: false),
      policies: rawPolicies
          .map((item) => LoanAccountingPolicy.fromPayload(stringMap(item)))
          .toList(growable: false),
      foundationStatus: _requiredString(payload, 'foundation_status'),
      fiscalPeriodStatus: _requiredString(payload, 'fiscal_period_status'),
      periodManagementEnabled: payload['period_management_enabled'] == true,
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

class AccountingFoundationSummary {
  const AccountingFoundationSummary({
    required this.accountCount,
    required this.postingAccountCount,
    required this.fiscalPeriodCount,
    required this.openPeriodCount,
    required this.journalEntryCount,
    required this.draftJournalCount,
    required this.postedJournalCount,
    required this.reversalDraftCount,
  });

  final int accountCount;
  final int postingAccountCount;
  final int fiscalPeriodCount;
  final int openPeriodCount;
  final int journalEntryCount;
  final int draftJournalCount;
  final int postedJournalCount;
  final int reversalDraftCount;

  factory AccountingFoundationSummary.fromPayload(Map<String, dynamic> payload) {
    return AccountingFoundationSummary(
      accountCount: _requiredInt(payload, 'account_count'),
      postingAccountCount: _requiredInt(payload, 'posting_account_count'),
      fiscalPeriodCount: _requiredInt(payload, 'fiscal_period_count'),
      openPeriodCount: _requiredInt(payload, 'open_period_count'),
      journalEntryCount: _requiredInt(payload, 'journal_entry_count'),
      draftJournalCount: _requiredInt(payload, 'draft_journal_count'),
      postedJournalCount: _requiredInt(payload, 'posted_journal_count'),
      reversalDraftCount: _requiredInt(payload, 'reversal_draft_count'),
    );
  }
}

class AccountingAccount {
  const AccountingAccount({
    required this.code,
    required this.systemKey,
    required this.name,
    required this.accountType,
    required this.normalBalance,
    required this.isPosting,
    required this.isActive,
  });

  final String code;
  final String systemKey;
  final String name;
  final String accountType;
  final String normalBalance;
  final bool isPosting;
  final bool isActive;

  factory AccountingAccount.fromPayload(Map<String, dynamic> payload) {
    return AccountingAccount(
      code: _requiredString(payload, 'code'),
      systemKey: _requiredString(payload, 'system_key'),
      name: _requiredString(payload, 'name'),
      accountType: _requiredString(payload, 'account_type'),
      normalBalance: _requiredString(payload, 'normal_balance'),
      isPosting: payload['is_posting'] == true,
      isActive: payload['is_active'] == true,
    );
  }
}

class AccountingFiscalPeriod {
  const AccountingFiscalPeriod({
    required this.periodId,
    required this.label,
    required this.startDate,
    required this.endDate,
    required this.status,
    required this.journalCount,
    required this.draftJournalCount,
    required this.postedJournalCount,
    this.closedByName,
    this.closedAt,
  });

  final String periodId;
  final String label;
  final DateTime startDate;
  final DateTime endDate;
  final String status;
  final int journalCount;
  final int draftJournalCount;
  final int postedJournalCount;
  final String? closedByName;
  final DateTime? closedAt;

  factory AccountingFiscalPeriod.fromPayload(Map<String, dynamic> payload) {
    return AccountingFiscalPeriod(
      periodId: _requiredString(payload, 'period_id'),
      label: _requiredString(payload, 'label'),
      startDate: _requiredDate(payload, 'start_date'),
      endDate: _requiredDate(payload, 'end_date'),
      status: _requiredString(payload, 'status'),
      journalCount: _requiredInt(payload, 'journal_count'),
      draftJournalCount: _requiredInt(payload, 'draft_journal_count'),
      postedJournalCount: _requiredInt(payload, 'posted_journal_count'),
      closedByName: _optionalString(payload['closed_by_name']),
      closedAt: _optionalDateTime(payload['closed_at']),
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

DateTime _requiredDate(Map<String, dynamic> payload, String key) {
  final parsed = DateTime.tryParse(payload[key]?.toString() ?? '');
  if (parsed == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_financial_accounting_payload',
    );
  }
  return DateTime(parsed.year, parsed.month, parsed.day);
}

String? _optionalString(Object? value) {
  final normalized = value?.toString().trim() ?? '';
  return normalized.isEmpty ? null : normalized;
}

DateTime? _optionalDateTime(Object? value) {
  final normalized = value?.toString().trim() ?? '';
  if (normalized.isEmpty) {
    return null;
  }
  return DateTime.tryParse(normalized);
}
