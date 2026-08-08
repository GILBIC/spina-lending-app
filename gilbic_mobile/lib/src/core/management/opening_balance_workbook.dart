import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class OpeningBalanceWorkbookData {
  const OpeningBalanceWorkbookData({
    required this.summary,
    required this.lines,
    required this.managementEnabled,
    required this.notice,
  });

  final OpeningBalanceWorkbookSummary summary;
  final List<OpeningBalanceWorkbookLine> lines;
  final bool managementEnabled;
  final String notice;

  factory OpeningBalanceWorkbookData.fromPayload(Map<String, dynamic> payload) {
    final rawLines = payload['lines'];
    if (rawLines is! List) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete opening-balance workbook data.',
        code: 'invalid_opening_balance_workbook_payload',
      );
    }
    return OpeningBalanceWorkbookData(
      summary: OpeningBalanceWorkbookSummary.fromPayload(
        stringMap(payload['summary']),
      ),
      lines: rawLines
          .map((item) => OpeningBalanceWorkbookLine.fromPayload(stringMap(item)))
          .toList(growable: false),
      managementEnabled: payload['management_enabled'] == true,
      notice: _requiredString(payload, 'notice'),
    );
  }
}

class OpeningBalanceWorkbookSummary {
  const OpeningBalanceWorkbookSummary({
    required this.workbookId,
    required this.cutoverDate,
    required this.status,
    required this.lineCount,
    required this.sourceReferenceCount,
    required this.verifiedLineCount,
    required this.pendingLineCount,
    required this.profitLossPolicyConfirmed,
    required this.profitLossPolicyNote,
    required this.totalDebit,
    required this.totalCredit,
    required this.balanceVariance,
    required this.worksheetBalanced,
    required this.readyForReview,
    required this.readyToPost,
    required this.openingBalancePostingEnabled,
    required this.automaticSourcePostingEnabled,
  });

  final String? workbookId;
  final DateTime? cutoverDate;
  final String status;
  final int lineCount;
  final int sourceReferenceCount;
  final int verifiedLineCount;
  final int pendingLineCount;
  final bool profitLossPolicyConfirmed;
  final String? profitLossPolicyNote;
  final double totalDebit;
  final double totalCredit;
  final double balanceVariance;
  final bool worksheetBalanced;
  final bool readyForReview;
  final bool readyToPost;
  final bool openingBalancePostingEnabled;
  final bool automaticSourcePostingEnabled;

  bool get hasWorkbook => workbookId != null;
  bool get isDraft => status == 'draft';
  bool get isReviewReady => status == 'review_ready';

  factory OpeningBalanceWorkbookSummary.fromPayload(
    Map<String, dynamic> payload,
  ) {
    return OpeningBalanceWorkbookSummary(
      workbookId: _optionalString(payload['workbook_id']),
      cutoverDate: _optionalDate(payload['cutover_date']),
      status: _requiredString(payload, 'status'),
      lineCount: _requiredInt(payload, 'line_count'),
      sourceReferenceCount: _requiredInt(payload, 'source_reference_count'),
      verifiedLineCount: _requiredInt(payload, 'verified_line_count'),
      pendingLineCount: _requiredInt(payload, 'pending_line_count'),
      profitLossPolicyConfirmed:
          payload['profit_loss_policy_confirmed'] == true,
      profitLossPolicyNote: _optionalString(payload['profit_loss_policy_note']),
      totalDebit: _requiredDouble(payload, 'total_debit'),
      totalCredit: _requiredDouble(payload, 'total_credit'),
      balanceVariance: _requiredDouble(payload, 'balance_variance'),
      worksheetBalanced: payload['worksheet_balanced'] == true,
      readyForReview: payload['ready_for_review'] == true,
      readyToPost: payload['ready_to_post'] == true,
      openingBalancePostingEnabled:
          payload['opening_balance_posting_enabled'] == true,
      automaticSourcePostingEnabled:
          payload['automatic_source_posting_enabled'] == true,
    );
  }
}

class OpeningBalanceWorkbookLine {
  const OpeningBalanceWorkbookLine({
    required this.workbookId,
    required this.accountCode,
    required this.systemKey,
    required this.accountName,
    required this.accountType,
    required this.normalBalance,
    required this.sourceReferenceAmount,
    required this.sourceBasis,
    required this.requirementType,
    required this.guidance,
    required this.proposedDebit,
    required this.proposedCredit,
    required this.verificationStatus,
    required this.evidenceNote,
  });

  final String? workbookId;
  final String accountCode;
  final String systemKey;
  final String accountName;
  final String accountType;
  final String normalBalance;
  final double? sourceReferenceAmount;
  final String sourceBasis;
  final String requirementType;
  final String guidance;
  final double? proposedDebit;
  final double? proposedCredit;
  final String verificationStatus;
  final String? evidenceNote;

  bool get isVerified => verificationStatus == 'verified';

  factory OpeningBalanceWorkbookLine.fromPayload(Map<String, dynamic> payload) {
    return OpeningBalanceWorkbookLine(
      workbookId: _optionalString(payload['workbook_id']),
      accountCode: _requiredString(payload, 'account_code'),
      systemKey: _requiredString(payload, 'system_key'),
      accountName: _requiredString(payload, 'account_name'),
      accountType: _requiredString(payload, 'account_type'),
      normalBalance: _requiredString(payload, 'normal_balance'),
      sourceReferenceAmount: _optionalDouble(payload['source_reference_amount']),
      sourceBasis: _requiredString(payload, 'source_basis'),
      requirementType: _requiredString(payload, 'requirement_type'),
      guidance: _requiredString(payload, 'guidance'),
      proposedDebit: _optionalDouble(payload['proposed_debit']),
      proposedCredit: _optionalDouble(payload['proposed_credit']),
      verificationStatus: _requiredString(payload, 'verification_status'),
      evidenceNote: _optionalString(payload['evidence_note']),
    );
  }
}

String _requiredString(Map<String, dynamic> payload, String key) {
  final value = payload[key]?.toString().trim() ?? '';
  if (value.isEmpty) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_opening_balance_workbook_payload',
    );
  }
  return value;
}

String? _optionalString(Object? value) {
  final normalized = value?.toString().trim() ?? '';
  return normalized.isEmpty || normalized.toLowerCase() == 'null'
      ? null
      : normalized;
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
      code: 'invalid_opening_balance_workbook_payload',
    );
  }
  return parsed;
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
      code: 'invalid_opening_balance_workbook_payload',
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

DateTime? _optionalDate(Object? value) {
  final normalized = value?.toString().trim() ?? '';
  if (normalized.isEmpty || normalized.toLowerCase() == 'null') {
    return null;
  }
  final parsed = DateTime.tryParse(normalized);
  return parsed == null ? null : DateTime(parsed.year, parsed.month, parsed.day);
}
