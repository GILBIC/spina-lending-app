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
      debit: journalMoney(payload['debit']),
      credit: journalMoney(payload['credit']),
    );
  }

  final int lineNumber;
  final String accountCode;
  final String accountName;
  final String description;
  final String debit;
  final String credit;
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
      totalDebit: journalMoney(payload['total_debit']),
      totalCredit: journalMoney(payload['total_credit']),
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
  final String totalDebit;
  final String totalCredit;
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
      totalDebit: journalMoney(payload['total_debit']),
      totalCredit: journalMoney(payload['total_credit']),
      debitBalance: journalMoney(payload['debit_balance']),
      creditBalance: journalMoney(payload['credit_balance']),
    );
  }

  final String accountCode;
  final String accountName;
  final String accountType;
  final String normalBalance;
  final String totalDebit;
  final String totalCredit;
  final String debitBalance;
  final String creditBalance;
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
      totalDebits: journalMoney(payload['total_debits']),
      totalCredits: journalMoney(payload['total_credits']),
      balanced: boolValue(payload['balanced']),
      lines: listValue(payload['lines'])
          .map(
            (item) => AccountingTrialBalanceLine.fromPayload(stringMap(item)),
          )
          .toList(growable: false),
    );
  }

  final String? periodId;
  final String? periodLabel;
  final String totalDebits;
  final String totalCredits;
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
    this.debit = '0.00',
    this.credit = '0.00',
  });

  final String accountCode;
  final String description;
  final String debit;
  final String credit;

  Map<String, Object> toPayload() => <String, Object>{
    'account_code': accountCode,
    'description': description,
    'debit': journalMoney(debit, forInput: true),
    'credit': journalMoney(credit, forInput: true),
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

/// Exact decimal amounts; the 18-digit bound applies to entered journal lines,
/// while server ledger aggregates may be larger. Never rounds or defaults.
String journalMoney(Object? value, {bool forInput = false}) {
  if (value is! String) {
    throw const FormatException(
      'Use decimal text with at most two decimal places.',
    );
  }
  final text = value.trim();
  if (!RegExp(r'^(0|[1-9][0-9]*)(\.[0-9]{1,2})?$').hasMatch(text) ||
      (forInput && text.split('.').first.length > 16)) {
    throw const FormatException(
      'Use a nonnegative amount with at most two decimal places and 16 whole digits.',
    );
  }
  final parts = text.split('.');
  return '${parts.first}.${parts.length == 1 ? '00' : parts.last.padRight(2, '0')}';
}

BigInt journalCents(String value) =>
    BigInt.parse(journalMoney(value).replaceAll('.', ''));

String journalAmountFromCents(BigInt value) {
  final text = value.toString().padLeft(3, '0');
  return '${text.substring(0, text.length - 2)}.${text.substring(text.length - 2)}';
}
