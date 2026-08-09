class OpeningBalanceJournalDraftStatus {
  const OpeningBalanceJournalDraftStatus({
    required this.workbookId,
    required this.cutoverDate,
    required this.workbookStatus,
    required this.journalEntryId,
    required this.journalStatus,
    required this.entryNumber,
    required this.journalLineCount,
    required this.totalDebit,
    required this.totalCredit,
    required this.draftPrepared,
    required this.openingBalancePostingEnabled,
    required this.automaticSourcePostingEnabled,
    required this.notice,
  });

  final String workbookId;
  final DateTime cutoverDate;
  final String workbookStatus;
  final String? journalEntryId;
  final String? journalStatus;
  final String? entryNumber;
  final int journalLineCount;
  final double totalDebit;
  final double totalCredit;
  final bool draftPrepared;
  final bool openingBalancePostingEnabled;
  final bool automaticSourcePostingEnabled;
  final String notice;

  bool get canPrepare =>
      workbookStatus == 'review_ready' &&
      !draftPrepared &&
      !openingBalancePostingEnabled &&
      !automaticSourcePostingEnabled;

  factory OpeningBalanceJournalDraftStatus.fromPayload(
    Map<String, dynamic> payload,
  ) {
    return OpeningBalanceJournalDraftStatus(
      workbookId: payload['workbook_id']?.toString() ?? '',
      cutoverDate: DateTime.parse(payload['cutover_date'].toString()),
      workbookStatus: payload['workbook_status']?.toString() ?? '',
      journalEntryId: _optionalText(payload['journal_entry_id']),
      journalStatus: _optionalText(payload['journal_status']),
      entryNumber: _optionalText(payload['entry_number']),
      journalLineCount: _int(payload['journal_line_count']),
      totalDebit: _double(payload['total_debit']),
      totalCredit: _double(payload['total_credit']),
      draftPrepared: payload['draft_prepared'] == true,
      openingBalancePostingEnabled:
          payload['opening_balance_posting_enabled'] == true,
      automaticSourcePostingEnabled:
          payload['automatic_source_posting_enabled'] == true,
      notice: payload['notice']?.toString() ?? '',
    );
  }
}

String? _optionalText(Object? value) {
  final text = value?.toString().trim();
  return text == null || text.isEmpty ? null : text;
}

int _int(Object? value) {
  if (value is num) return value.toInt();
  return int.tryParse(value?.toString() ?? '') ?? 0;
}

double _double(Object? value) {
  if (value is num) return value.toDouble();
  return double.tryParse(value?.toString() ?? '') ?? 0;
}
