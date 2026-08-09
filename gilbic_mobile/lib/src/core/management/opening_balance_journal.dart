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
    required this.totalDebitExact,
    required this.totalCreditExact,
    required this.draftPrepared,
    required this.preparationReady,
    required this.preparationBlocker,
    required this.openingBalancePostingEnabled,
    required this.automaticSourcePostingEnabled,
    required this.postingReady,
    required this.postingBlocker,
    required this.postedByUserId,
    required this.postedAt,
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
  final String totalDebitExact;
  final String totalCreditExact;
  final bool draftPrepared;
  final bool preparationReady;
  final String? preparationBlocker;
  final bool openingBalancePostingEnabled;
  final bool automaticSourcePostingEnabled;
  final bool postingReady;
  final String? postingBlocker;
  final String? postedByUserId;
  final DateTime? postedAt;
  final String notice;

  bool get isPosted =>
      journalStatus == 'posted' && entryNumber != null && postedAt != null;

  bool get canPrepare => preparationReady && !draftPrepared;

  bool get canPost =>
      openingBalancePostingEnabled &&
      postingReady &&
      journalStatus == 'draft' &&
      journalEntryId != null &&
      !automaticSourcePostingEnabled;

  factory OpeningBalanceJournalDraftStatus.fromPayload(
    Map<String, dynamic> payload,
  ) {
    final totalDebitExact = _decimalText(payload['total_debit']);
    final totalCreditExact = _decimalText(payload['total_credit']);
    return OpeningBalanceJournalDraftStatus(
      workbookId: payload['workbook_id']?.toString() ?? '',
      cutoverDate: DateTime.parse(payload['cutover_date'].toString()),
      workbookStatus: payload['workbook_status']?.toString() ?? '',
      journalEntryId: _optionalText(payload['journal_entry_id']),
      journalStatus: _optionalText(payload['journal_status']),
      entryNumber: _optionalText(payload['entry_number']),
      journalLineCount: _int(payload['journal_line_count']),
      totalDebit: double.tryParse(totalDebitExact) ?? 0,
      totalCredit: double.tryParse(totalCreditExact) ?? 0,
      totalDebitExact: totalDebitExact,
      totalCreditExact: totalCreditExact,
      draftPrepared: payload['draft_prepared'] == true,
      preparationReady: payload['preparation_ready'] == true,
      preparationBlocker: _optionalText(payload['preparation_blocker']),
      openingBalancePostingEnabled:
          payload['opening_balance_posting_enabled'] == true,
      automaticSourcePostingEnabled:
          payload['automatic_source_posting_enabled'] == true,
      postingReady: payload['posting_ready'] == true,
      postingBlocker: _optionalText(payload['posting_blocker']),
      postedByUserId: _optionalText(payload['posted_by_user_id']),
      postedAt: _optionalDateTime(payload['posted_at']),
      notice: payload['notice']?.toString() ?? '',
    );
  }
}

String? _optionalText(Object? value) {
  final text = value?.toString().trim();
  return text == null || text.isEmpty ? null : text;
}

String _decimalText(Object? value) {
  final text = value?.toString().trim();
  return text == null || text.isEmpty ? '0' : text;
}

DateTime? _optionalDateTime(Object? value) {
  final text = _optionalText(value);
  return text == null ? null : DateTime.tryParse(text);
}

int _int(Object? value) {
  if (value is num) return value.toInt();
  return int.tryParse(value?.toString() ?? '') ?? 0;
}
