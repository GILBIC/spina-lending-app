import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class CollectionCorrectionDraft {
  const CollectionCorrectionDraft({
    required this.transactionId,
    required this.entryType,
    required this.reason,
    this.amount,
    this.coveredDates = const <DateTime>[],
    this.note = '',
  });

  final String transactionId;
  final String entryType;
  final double? amount;
  final List<DateTime> coveredDates;
  final String note;
  final String reason;

  String? validate() {
    if (transactionId.trim().isEmpty) {
      return 'The collection transaction is missing. Refresh the route.';
    }
    if (!const <String>{'payment', 'advance', 'pass'}.contains(entryType)) {
      return 'Choose a valid collection entry type.';
    }
    if (reason.trim().isEmpty) {
      return 'Enter a reason for the correction.';
    }
    final dates = _sortedUniqueDates(coveredDates);
    if (dates.length != coveredDates.length) {
      return 'Covered dates must not contain duplicates.';
    }
    if (entryType == 'pass') {
      if (amount != null && amount != 0) {
        return 'Unable-to-pay cannot contain an amount.';
      }
      if (dates.isNotEmpty) {
        return 'Unable-to-pay cannot contain covered dates.';
      }
      return null;
    }
    if (amount == null || amount! <= 0) {
      return 'Enter an amount greater than zero.';
    }
    if (dates.isEmpty) {
      return 'Choose at least one covered date.';
    }
    return null;
  }

  Map<String, Object?> toJson() {
    return <String, Object?>{
      'entry_type': entryType,
      'amount': amount,
      'covered_dates': _sortedUniqueDates(coveredDates)
          .map(_date)
          .toList(growable: false),
      'note': note.trim(),
      'reason': reason.trim(),
    };
  }
}

class CollectionCorrectionResult {
  const CollectionCorrectionResult({
    required this.transactionId,
    required this.entryType,
    required this.amount,
    required this.coveredDates,
    required this.note,
    required this.officialBalance,
    required this.receiptNumber,
    required this.editVersion,
    required this.routeRevision,
    required this.editedAt,
  });

  final String transactionId;
  final String entryType;
  final double amount;
  final List<DateTime> coveredDates;
  final String note;
  final double officialBalance;
  final String receiptNumber;
  final int editVersion;
  final String routeRevision;
  final DateTime? editedAt;

  static CollectionCorrectionResult fromPayload(Object? value) {
    final data = stringMap(value);
    final transactionId = firstNonEmptyString(<Object?>[
      data['transaction_id'],
      data['id'],
    ]);
    if (transactionId == null) {
      throw const SpinaApiException(
        'The SPINA server returned an incomplete correction result.',
        code: 'invalid_correction_response',
      );
    }
    return CollectionCorrectionResult(
      transactionId: transactionId,
      entryType: firstNonEmptyString(<Object?>[data['entry_type']]) ?? 'payment',
      amount: firstNumber(<Object?>[data['amount']])?.toDouble() ?? 0,
      coveredDates: _dateList(data['covered_dates']),
      note: firstNonEmptyString(<Object?>[data['note']]) ?? '',
      officialBalance:
          firstNumber(<Object?>[data['official_balance']])?.toDouble() ?? 0,
      receiptNumber:
          firstNonEmptyString(<Object?>[data['receipt_number']]) ?? '',
      editVersion: firstNumber(<Object?>[data['edit_version']])?.toInt() ?? 0,
      routeRevision:
          firstNonEmptyString(<Object?>[data['route_revision']]) ?? '',
      editedAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['edited_at']]) ?? '',
      ),
    );
  }
}

List<DateTime> _sortedUniqueDates(Iterable<DateTime> values) {
  final byDate = <String, DateTime>{};
  for (final value in values) {
    final normalized = DateTime(value.year, value.month, value.day);
    byDate[_date(normalized)] = normalized;
  }
  final result = byDate.values.toList(growable: false)
    ..sort((left, right) => left.compareTo(right));
  return result;
}

List<DateTime> _dateList(Object? value) {
  if (value is! Iterable) {
    return const <DateTime>[];
  }
  return _sortedUniqueDates(
    value
        .map((item) => DateTime.tryParse(item.toString()))
        .whereType<DateTime>(),
  );
}

String _date(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}
