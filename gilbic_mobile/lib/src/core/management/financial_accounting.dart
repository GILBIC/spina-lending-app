import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class FinancialAccountingOverview {
  const FinancialAccountingOverview({
    required this.summary,
    required this.foundation,
    required this.accounts,
    required this.fiscalPeriods,
    required this.policies,
    required this.cutoverSummary,
    required this.cutoverLoans,
    required this.openingBalanceSummary,
    required this.openingBalanceLines,
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
  final AccountingCutoverReadinessSummary cutoverSummary;
  final List<AccountingCutoverLoan> cutoverLoans;
  final OpeningBalanceCutoverSummary openingBalanceSummary;
  final List<OpeningBalanceCutoverLine> openingBalanceLines;
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
    final cutover = stringMap(payload['cutover']);
    final openingWorksheet = stringMap(payload['opening_balance_worksheet']);
    final rawCutoverLoans = cutover['loans'];
    final rawOpeningLines = openingWorksheet['lines'];
    if (rawPolicies is! List ||
        rawAccounts is! List ||
        rawFiscalPeriods is! List ||
        rawCutoverLoans is! List ||
        rawOpeningLines is! List) {
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
      cutoverSummary: AccountingCutoverReadinessSummary.fromPayload(
        stringMap(cutover['summary']),
      ),
      cutoverLoans: rawCutoverLoans
          .map((item) => AccountingCutoverLoan.fromPayload(stringMap(item)))
          .toList(growable: false),
      openingBalanceSummary: OpeningBalanceCutoverSummary.fromPayload(
        stringMap(openingWorksheet['summary']),
      ),
      openingBalanceLines: rawOpeningLines
          .map((item) => OpeningBalanceCutoverLine.fromPayload(stringMap(item)))
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

class AccountingCutoverReadinessSummary {
  const AccountingCutoverReadinessSummary({
    required this.activeLoanCount,
    required this.sourceReadyCount,
    required this.contractValidationCount,
    required this.blockedCount,
    required this.openingBalancesConfigured,
    required this.automaticSourcePostingEnabled,
    required this.overallStatus,
  });

  final int activeLoanCount;
  final int sourceReadyCount;
  final int contractValidationCount;
  final int blockedCount;
  final bool openingBalancesConfigured;
  final bool automaticSourcePostingEnabled;
  final String overallStatus;

  factory AccountingCutoverReadinessSummary.fromPayload(
    Map<String, dynamic> payload,
  ) {
    return AccountingCutoverReadinessSummary(
      activeLoanCount: _requiredInt(payload, 'active_loan_count'),
      sourceReadyCount: _requiredInt(payload, 'source_ready_count'),
      contractValidationCount:
          _requiredInt(payload, 'contract_validation_count'),
      blockedCount: _requiredInt(payload, 'blocked_count'),
      openingBalancesConfigured: payload['opening_balances_configured'] == true,
      automaticSourcePostingEnabled:
          payload['automatic_source_posting_enabled'] == true,
      overallStatus: _requiredString(payload, 'overall_status'),
    );
  }
}

class AccountingCutoverLoan {
  const AccountingCutoverLoan({
    required this.loanNumber,
    required this.clientCode,
    required this.clientName,
    required this.loanTypeName,
    required this.calculationMode,
    required this.termDays,
    required this.principal,
    required this.dailyAmount,
    required this.interestRate,
    required this.dateReleased,
    required this.dueDate,
    required this.operationalBalance,
    required this.regularContractTotal,
    required this.regularScheduledTotal,
    required this.sevenBySevenExpectedDailyInterest,
    required this.sevenBySevenContractInterestTotal,
    required this.sevenBySevenContractTotalIfPrincipalAtMaturity,
    required this.sevenBySevenBaseDailyRatePercent,
    required this.readinessStatus,
    required this.blockers,
  });

  final String loanNumber;
  final String clientCode;
  final String clientName;
  final String loanTypeName;
  final String calculationMode;
  final int termDays;
  final double principal;
  final double dailyAmount;
  final double? interestRate;
  final DateTime dateReleased;
  final DateTime dueDate;
  final double operationalBalance;
  final double? regularContractTotal;
  final double? regularScheduledTotal;
  final double? sevenBySevenExpectedDailyInterest;
  final double? sevenBySevenContractInterestTotal;
  final double? sevenBySevenContractTotalIfPrincipalAtMaturity;
  final double? sevenBySevenBaseDailyRatePercent;
  final String readinessStatus;
  final List<String> blockers;

  bool get isSevenBySeven => calculationMode == 'seven_by_seven';

  factory AccountingCutoverLoan.fromPayload(Map<String, dynamic> payload) {
    final rawBlockers = payload['blockers'];
    return AccountingCutoverLoan(
      loanNumber: _requiredString(payload, 'loan_number'),
      clientCode: _requiredString(payload, 'client_code'),
      clientName: _requiredString(payload, 'client_name'),
      loanTypeName: _requiredString(payload, 'loan_type_name'),
      calculationMode: _requiredString(payload, 'calculation_mode'),
      termDays: _requiredInt(payload, 'term_days'),
      principal: _requiredDouble(payload, 'principal'),
      dailyAmount: _requiredDouble(payload, 'daily_amount'),
      interestRate: _optionalDouble(payload['interest_rate']),
      dateReleased: _requiredDate(payload, 'date_released'),
      dueDate: _requiredDate(payload, 'due_date'),
      operationalBalance: _requiredDouble(payload, 'operational_balance'),
      regularContractTotal: _optionalDouble(payload['regular_contract_total']),
      regularScheduledTotal: _optionalDouble(payload['regular_scheduled_total']),
      sevenBySevenExpectedDailyInterest:
          _optionalDouble(payload['seven_by_seven_expected_daily_interest']),
      sevenBySevenContractInterestTotal:
          _optionalDouble(payload['seven_by_seven_contract_interest_total']),
      sevenBySevenContractTotalIfPrincipalAtMaturity: _optionalDouble(
        payload['seven_by_seven_contract_total_if_principal_at_maturity'],
      ),
      sevenBySevenBaseDailyRatePercent:
          _optionalDouble(payload['seven_by_seven_base_daily_rate_percent']),
      readinessStatus: _requiredString(payload, 'readiness_status'),
      blockers: rawBlockers is List
          ? rawBlockers.map((item) => item.toString()).toList(growable: false)
          : const <String>[],
    );
  }
}

class OpeningBalanceCutoverSummary {
  const OpeningBalanceCutoverSummary({
    required this.cutoverDate,
    required this.worksheetStatus,
    required this.worksheetLineCount,
    required this.sourceReferenceCount,
    required this.manualRequiredCount,
    required this.reconciliationRequiredCount,
    required this.calculationRequiredCount,
    required this.assessmentRequiredCount,
    required this.profitLossMigrationPolicyRequired,
    required this.worksheetBalanced,
    required this.readyToPost,
    required this.openingBalancePostingEnabled,
    required this.automaticSourcePostingEnabled,
  });

  final DateTime? cutoverDate;
  final String worksheetStatus;
  final int worksheetLineCount;
  final int sourceReferenceCount;
  final int manualRequiredCount;
  final int reconciliationRequiredCount;
  final int calculationRequiredCount;
  final int assessmentRequiredCount;
  final bool profitLossMigrationPolicyRequired;
  final bool worksheetBalanced;
  final bool readyToPost;
  final bool openingBalancePostingEnabled;
  final bool automaticSourcePostingEnabled;

  factory OpeningBalanceCutoverSummary.fromPayload(
    Map<String, dynamic> payload,
  ) {
    return OpeningBalanceCutoverSummary(
      cutoverDate: _optionalDate(payload['cutover_date']),
      worksheetStatus: _requiredString(payload, 'worksheet_status'),
      worksheetLineCount: _requiredInt(payload, 'worksheet_line_count'),
      sourceReferenceCount: _requiredInt(payload, 'source_reference_count'),
      manualRequiredCount: _requiredInt(payload, 'manual_required_count'),
      reconciliationRequiredCount:
          _requiredInt(payload, 'reconciliation_required_count'),
      calculationRequiredCount:
          _requiredInt(payload, 'calculation_required_count'),
      assessmentRequiredCount:
          _requiredInt(payload, 'assessment_required_count'),
      profitLossMigrationPolicyRequired:
          payload['profit_loss_migration_policy_required'] == true,
      worksheetBalanced: payload['worksheet_balanced'] == true,
      readyToPost: payload['ready_to_post'] == true,
      openingBalancePostingEnabled:
          payload['opening_balance_posting_enabled'] == true,
      automaticSourcePostingEnabled:
          payload['automatic_source_posting_enabled'] == true,
    );
  }
}

class OpeningBalanceCutoverLine {
  const OpeningBalanceCutoverLine({
    required this.accountCode,
    required this.systemKey,
    required this.accountName,
    required this.accountType,
    required this.normalBalance,
    required this.sourceReferenceAmount,
    required this.sourceBasis,
    required this.readinessStatus,
    required this.guidance,
  });

  final String accountCode;
  final String systemKey;
  final String accountName;
  final String accountType;
  final String normalBalance;
  final double? sourceReferenceAmount;
  final String sourceBasis;
  final String readinessStatus;
  final String guidance;

  factory OpeningBalanceCutoverLine.fromPayload(Map<String, dynamic> payload) {
    return OpeningBalanceCutoverLine(
      accountCode: _requiredString(payload, 'account_code'),
      systemKey: _requiredString(payload, 'system_key'),
      accountName: _requiredString(payload, 'account_name'),
      accountType: _requiredString(payload, 'account_type'),
      normalBalance: _requiredString(payload, 'normal_balance'),
      sourceReferenceAmount: _optionalDouble(payload['source_reference_amount']),
      sourceBasis: _requiredString(payload, 'source_basis'),
      readinessStatus: _requiredString(payload, 'readiness_status'),
      guidance: _requiredString(payload, 'guidance'),
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

double? _optionalDouble(Object? value) {
  if (value == null) {
    return null;
  }
  if (value is num) {
    return value.toDouble();
  }
  final normalized = value.toString().trim();
  if (normalized.isEmpty || normalized.toLowerCase() == 'null') {
    return null;
  }
  return double.tryParse(normalized);
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

DateTime? _optionalDate(Object? value) {
  final normalized = value?.toString().trim() ?? '';
  if (normalized.isEmpty || normalized.toLowerCase() == 'null') {
    return null;
  }
  final parsed = DateTime.tryParse(normalized);
  return parsed == null ? null : DateTime(parsed.year, parsed.month, parsed.day);
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
