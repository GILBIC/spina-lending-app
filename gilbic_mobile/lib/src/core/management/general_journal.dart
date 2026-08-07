import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class AccountingJournalLine {
  const AccountingJournalLine({
    required this.lineNumber,
    required this.accountCode,
    required this.accountName,
    required this.description,
    required this.debit,
    required this.credit,
  });

  factory AccountingJournalLine.fromPayload(Map<String, dynamic> payload) {
    return AccountingJournalLine(
      lineNumber: intValue(payload['line_number']),
      accountCode: stringValue(payload['account_code']),
      accountName: stringValue(payload['account_name']),
      description: stringValue(payload['description']),
      debit: doubleValue(payload['debit']),
      credit: doubleValue(payload['credit']),
    );
  }

  final int lineNumber;
  final String accountCode;
  final String accountName;
  final String description;
  final double debit;
  final double credit;
}

class AccountingJournalEntry {
  const AccountingJournalEntry({
    required this.entryId,
    required this.entryNumber,
    required this.periodId,
    required this.periodLabel,
    required this.postingDate,
    required this.description,
    required this.status,
    required this.sourceType,
    required this.sourceReference,
    required this.reversalOfEntryId,
    required this.createdByName,
    required this.postedByName,
    required this.createdAt,
    required this.postedAt,
    required this.totalDebit,
    required this.totalCredit,
    required this.lines,
  });

  factory AccountingJournalEntry.fromPayload(Map<String, dynamic> payload) {
    return AccountingJournalEntry(
      entryId: stringValue(payload['entry_id']),
      entryNumber: nullableString(payload['entry_number']),
      periodId: stringValue(payload['period_id']),
      periodLabel: stringValue(payload['period_label']),
      postingDate: DateTime.parse(stringValue(payload['posting_date'])),
      description: stringValue(payload['description']),
      status: stringValue(payload['status']),
      sourceType: nullableString(payload['source_type']),
      sourceReference: nullableString(payload['source_reference']),
      reversalOfEntryId: nullableString(payload['reversal_of_entry_id']),
      createdByName: stringValue(payload['created_by_name']),
      postedByName: nullableString(payload['posted_by_name']),
      createdAt: DateTime.parse(stringValue(payload['created_at'])),
      postedAt: nullableDateTime(payload['posted_at']),
      totalDebit: doubleValue(payload['total_debit']),
      totalCredit: doubleValue(payload['total_credit']),
      lines: listValue(payload['lines'])
          .map((item) => AccountingJournalLine.fromPayload(stringMap(item)))
          .toList(growable: false),
    );
  }

  final String entryId;
  final String? entryNumber;
  final String periodId;
  final String periodLabel;
  final DateTime postingDate;
  final String description;
  final String status;
  final String? sourceType;
  final String? sourceReference;
  final String? reversalOfEntryId;
  final String createdByName;
  final String? postedByName;
  final DateTime createdAt;
  final DateTime? postedAt;
  final double totalDebit;
  final double totalCredit;
  final List<AccountingJournalLine> lines;

  bool get isDraft => status == 'draft';
  bool get isPosted => status == 'posted';
  bool get isManual => sourceType == 'manual';
}

class AccountingTrialBalanceLine {
  const AccountingTrialBalanceLine({
    required this.accountCode,
    required this.accountName,
    required this.accountType,
    required this.normalBalance,
    required this.totalDebit,
    required this.totalCredit,
    required this.debitBalance,
    required this.creditBalance,
  });

  factory AccountingTrialBalanceLine.fromPayload(Map<String, dynamic> payload) {
    return AccountingTrialBalanceLine(
      accountCode: stringValue(payload['account_code']),
      accountName: stringValue(payload['account_name']),
      accountType: stringValue(payload['account_type']),
      normalBalance: stringValue(payload['normal_balance']),
      totalDebit: doubleValue(payload['total_debit']),
      totalCredit: doubleValue(payload['total_credit']),
      debitBalance: doubleValue(payload['debit_balance']),
      creditBalance: doubleValue(payload['credit_balance']),
    );
  }

  final String accountCode;
  final String accountName;
  final String accountType;
  final String normalBalance;
  final double totalDebit;
  final double totalCredit;
  final double debitBalance;
  final double creditBalance;
}

class AccountingTrialBalance {
  const AccountingTrialBalance({
    required this.periodId,
    required this.periodLabel,
    required this.totalDebits,
    required this.totalCredits,
    required this.balanced,
    required this.lines,
  });

  factory AccountingTrialBalance.fromPayload(Map<String, dynamic> payload) {
    return AccountingTrialBalance(
      periodId: nullableString(payload['period_id']),
      periodLabel: nullableString(payload['period_label']),
      totalDebits: doubleValue(payload['total_debits']),
      totalCredits: doubleValue(payload['total_credits']),
      balanced: boolValue(payload['balanced']),
      lines: listValue(payload['lines'])
          .map((item) => AccountingTrialBalanceLine.fromPayload(stringMap(item)))
          .toList(growable: false),
    );
  }

  final String? periodId;
  final String? periodLabel;
  final double totalDebits;
  final double totalCredits;
  final bool balanced;
  final List<AccountingTrialBalanceLine> lines;
}

class GeneralJournalSnapshot {
  const GeneralJournalSnapshot({
    required this.entries,
    required this.canManage,
    required this.automaticLoanPostingEnabled,
  });

  factory GeneralJournalSnapshot.fromPayload(Map<String, dynamic> payload) {
    return GeneralJournalSnapshot(
      entries: listValue(payload['entries'])
          .map((item) => AccountingJournalEntry.fromPayload(stringMap(item)))
          .toList(growable: false),
      canManage: boolValue(payload['can_manage']),
      automaticLoanPostingEnabled: boolValue(
        payload['automatic_loan_posting_enabled'],
      ),
    );
  }

  final List<AccountingJournalEntry> entries;
  final bool canManage;
  final bool automaticLoanPostingEnabled;
}

class JournalLineDraft {
  const JournalLineDraft({
    required this.accountCode,
    this.description = '',
    this.debit = 0,
    this.credit = 0,
  });

  final String accountCode;
  final String description;
  final double debit;
  final double credit;

  Map<String, Object> toPayload() => <String, Object>{
        'account_code': accountCode,
        'description': description,
        'debit': debit.toStringAsFixed(2),
        'credit': credit.toStringAsFixed(2),
      };
}

DateTime? nullableDateTime(Object? value) {
  final text = nullableString(value);
  return text == null ? null : DateTime.tryParse(text);
}

String? nullableString(Object? value) {
  if (value == null) {
    return null;
  }
  final text = value.toString().trim();
  return text.isEmpty || text.toLowerCase() == 'null' ? null : text;
}

String stringValue(Object? value) => value?.toString() ?? '';

int intValue(Object? value) {
  if (value is int) {
    return value;
  }
  return int.tryParse(value?.toString() ?? '') ?? 0;
}

double doubleValue(Object? value) {
  if (value is num) {
    return value.toDouble();
  }
  return double.tryParse(value?.toString().replaceAll(',', '') ?? '') ?? 0;
}

bool boolValue(Object? value) {
  if (value is bool) {
    return value;
  }
  final normalized = value?.toString().trim().toLowerCase();
  return normalized == 'true' || normalized == '1';
}

List<dynamic> listValue(Object? value) {
  return value is List ? value : const <dynamic>[];
}
