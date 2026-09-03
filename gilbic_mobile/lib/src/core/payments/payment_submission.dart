import 'dart:math';

import 'package:gilbic_mobile/src/core/network/spina_api.dart';

enum CollectionEntryType {
  payment('payment'),
  advance('advance'),
  pass('pass');

  const CollectionEntryType(this.apiValue);

  final String apiValue;

  static CollectionEntryType? fromValue(Object? value) {
    final normalized = value?.toString().trim().toLowerCase();
    for (final type in CollectionEntryType.values) {
      if (type.apiValue == normalized || type.name == normalized) {
        return type;
      }
    }
    return null;
  }
}

enum PaymentAllocationIntent {
  scheduled('scheduled'),
  extraAsAdvance('extra_as_advance'),
  extraAsPrincipalReduction('extra_as_principal_reduction'),
  // Kept only so an older queued draft can still be represented. New UI must
  // never create this ambiguous intent; the server fails closed when true extra
  // cash requires a borrower choice.
  voluntaryExtra('voluntary_extra');

  const PaymentAllocationIntent(this.apiValue);

  final String apiValue;
}

enum PastDueReasonCode {
  noCash('no_cash', 'No cash'),
  clientAbsent('client_absent', 'Client absent'),
  businessSlow('business_slow', 'Business slow'),
  sickHospital('sick_hospital', 'Sick/Hospital'),
  emergency('emergency', 'Emergency'),
  promisedToPayLater('promised_to_pay_later', 'Promised to pay later'),
  other('other', 'Other');

  const PastDueReasonCode(this.apiValue, this.label);

  final String apiValue;
  final String label;
}

class PastDueFollowupDraft {
  const PastDueFollowupDraft({
    required this.reasonCode,
    this.note = '',
    this.promisedPaymentDate,
    this.promisedAmount,
  });

  final PastDueReasonCode reasonCode;
  final String note;
  final DateTime? promisedPaymentDate;
  final double? promisedAmount;

  String? validate({required DateTime collectionDate}) {
    if (reasonCode == PastDueReasonCode.other && note.trim().isEmpty) {
      return 'Other Past Due reason requires a short explanation.';
    }
    if (reasonCode == PastDueReasonCode.promisedToPayLater) {
      if (promisedPaymentDate == null) {
        return 'Choose the promised payment date.';
      }
      if (DateTime(
        promisedPaymentDate!.year,
        promisedPaymentDate!.month,
        promisedPaymentDate!.day,
      ).isBefore(DateTime(
        collectionDate.year,
        collectionDate.month,
        collectionDate.day,
      ))) {
        return 'Promised payment date cannot be before the collection date.';
      }
      if (promisedAmount == null || promisedAmount! <= 0) {
        return 'Enter the promised amount.';
      }
    } else if (promisedPaymentDate != null || promisedAmount != null) {
      return 'Promise date and amount are only for Promised to pay later.';
    }
    return null;
  }

  Map<String, Object?> toJson() => <String, Object?>{
        'reason_code': reasonCode.apiValue,
        'note': note.trim(),
        'promised_payment_date': promisedPaymentDate == null
            ? null
            : _date(promisedPaymentDate!),
        'promised_amount': promisedAmount,
      };
}

class PaymentSubmissionDraft {
  const PaymentSubmissionDraft({
    required this.idempotencyKey,
    required this.routeEntryId,
    required this.clientId,
    required this.loanId,
    required this.collectionDate,
    required this.entryType,
    required this.recordedAt,
    required this.deviceId,
    required this.deviceSequence,
    this.amount,
    this.advanceFrom,
    this.advanceUntil,
    this.coveredDates = const <DateTime>[],
    this.note = '',
    this.routeRevision,
    this.paymentAllocationIntent = PaymentAllocationIntent.scheduled,
    this.pastDueFollowup,
  });

  final String idempotencyKey;
  final String routeEntryId;
  final String clientId;
  final String loanId;
  final DateTime collectionDate;
  final CollectionEntryType entryType;
  final DateTime recordedAt;
  final String deviceId;
  final int deviceSequence;
  final double? amount;
  final DateTime? advanceFrom;
  final DateTime? advanceUntil;
  final List<DateTime> coveredDates;
  final String note;
  final String? routeRevision;
  final PaymentAllocationIntent paymentAllocationIntent;
  final PastDueFollowupDraft? pastDueFollowup;

  String? validate() {
    if (idempotencyKey.trim().isEmpty) {
      return 'A payment idempotency key is required.';
    }
    if (routeEntryId.trim().isEmpty ||
        clientId.trim().isEmpty ||
        loanId.trim().isEmpty) {
      return 'The route entry, client, and loan are required.';
    }
    if (deviceId.trim().isEmpty || deviceSequence < 1) {
      return 'A valid device identity and sequence are required.';
    }

    final normalizedDates = _sortedUniqueDates(coveredDates);
    if (normalizedDates.length != coveredDates.length) {
      return 'Covered dates must not contain duplicates.';
    }

    switch (entryType) {
      case CollectionEntryType.payment:
        if (amount == null || amount! <= 0) {
          return 'A payment amount greater than zero is required.';
        }
        if (advanceFrom != null || advanceUntil != null) {
          return 'A normal payment cannot contain coverage bounds.';
        }
        if (normalizedDates.isNotEmpty &&
            (normalizedDates.length != 1 ||
                !_sameDate(normalizedDates.single, collectionDate))) {
          return 'A normal payment may reference only the collection date.';
        }
        if (pastDueFollowup != null) {
          final followupError = pastDueFollowup!.validate(
            collectionDate: collectionDate,
          );
          if (followupError != null) {
            return followupError;
          }
        }
        break;
      case CollectionEntryType.advance:
        if (pastDueFollowup != null) {
          return 'A covered-date payment cannot contain a Past Due follow-up.';
        }
        if (paymentAllocationIntent != PaymentAllocationIntent.scheduled) {
          return 'Legacy covered-date ADV cannot also contain a Regular extra allocation choice.';
        }
        if (amount == null || amount! <= 0) {
          return 'A covered-date payment amount greater than zero is required.';
        }
        if (normalizedDates.isEmpty) {
          return 'Choose at least one covered date.';
        }
        if (advanceFrom == null || advanceUntil == null) {
          return 'The first and last selected covered dates are required.';
        }
        if (!_sameDate(normalizedDates.first, advanceFrom!)) {
          return 'The first coverage bound must match the earliest selected date.';
        }
        if (!_sameDate(normalizedDates.last, advanceUntil!)) {
          return 'The last coverage bound must match the latest selected date.';
        }
        break;
      case CollectionEntryType.pass:
        if (paymentAllocationIntent != PaymentAllocationIntent.scheduled) {
          return 'Unable-to-pay cannot contain a payment allocation intent.';
        }
        if (amount != null && amount != 0) {
          return 'An unable-to-pay entry cannot contain a payment amount.';
        }
        if (advanceFrom != null ||
            advanceUntil != null ||
            normalizedDates.isNotEmpty) {
          return 'An unable-to-pay entry cannot contain covered dates.';
        }
        if (pastDueFollowup == null) {
          return 'Choose a Past Due reason before saving Unable to pay.';
        }
        final followupError = pastDueFollowup!.validate(
          collectionDate: collectionDate,
        );
        if (followupError != null) {
          return followupError;
        }
        break;
    }
    return null;
  }

  Map<String, Object?> toJson() {
    final normalizedDates = _sortedUniqueDates(coveredDates);
    return <String, Object?>{
      'client_transaction_id': idempotencyKey,
      'route_entry_id': routeEntryId,
      'client_id': clientId,
      'loan_id': loanId,
      'collection_date': _date(collectionDate),
      'entry_type': entryType.apiValue,
      'amount': amount,
      'advance_from': advanceFrom == null ? null : _date(advanceFrom!),
      'advance_until': advanceUntil == null ? null : _date(advanceUntil!),
      'covered_dates': normalizedDates.map(_date).toList(growable: false),
      'recorded_at': recordedAt.toUtc().toIso8601String(),
      'device_id': deviceId,
      'device_sequence': deviceSequence,
      'note': note.trim(),
      'route_revision': routeRevision,
      if (paymentAllocationIntent != PaymentAllocationIntent.scheduled)
        'payment_allocation_intent': paymentAllocationIntent.apiValue,
      if (pastDueFollowup != null)
        'past_due_followup': pastDueFollowup!.toJson(),
    };
  }
}

enum PaymentSubmissionDisposition {
  accepted,
  duplicate,
  conflict,
  rejected,
}

class PaymentSubmissionResult {
  const PaymentSubmissionResult({
    required this.disposition,
    required this.idempotencyKey,
    required this.message,
    this.serverTransactionId,
    this.receiptNumber,
    this.officialBalance,
    this.acceptedAt,
    this.code,
    this.routeRevision,
  });

  final PaymentSubmissionDisposition disposition;
  final String idempotencyKey;
  final String message;
  final String? serverTransactionId;
  final String? receiptNumber;
  final double? officialBalance;
  final DateTime? acceptedAt;
  final String? code;
  final String? routeRevision;

  bool get isFinalSuccess =>
      disposition == PaymentSubmissionDisposition.accepted ||
      disposition == PaymentSubmissionDisposition.duplicate;

  static PaymentSubmissionResult fromPayload(
    Object? value, {
    required String idempotencyKey,
    required PaymentSubmissionDisposition fallbackDisposition,
  }) {
    final outer = stringMap(value);
    final transaction = stringMap(
      outer['transaction'] ?? outer['payment'] ?? outer['collection'],
    );
    final source = transaction.isEmpty ? outer : transaction;
    final rawDisposition = firstNonEmptyString(<Object?>[
      outer['disposition'],
      outer['result'],
      outer['status'],
      source['disposition'],
      source['result'],
      source['status'],
    ]);
    final duplicate = outer['duplicate'] == true ||
        source['duplicate'] == true ||
        rawDisposition?.toLowerCase() == 'duplicate';
    final disposition = duplicate
        ? PaymentSubmissionDisposition.duplicate
        : _dispositionFromValue(rawDisposition) ?? fallbackDisposition;

    return PaymentSubmissionResult(
      disposition: disposition,
      idempotencyKey: firstNonEmptyString(<Object?>[
            outer['client_transaction_id'],
            outer['idempotency_key'],
            source['client_transaction_id'],
            source['idempotency_key'],
          ]) ??
          idempotencyKey,
      message: firstNonEmptyString(<Object?>[
            outer['message'],
            source['message'],
          ]) ??
          _defaultMessage(disposition),
      serverTransactionId: firstNonEmptyString(<Object?>[
        source['transaction_id'],
        source['payment_id'],
        source['collection_id'],
        source['id'],
        outer['transaction_id'],
      ]),
      receiptNumber: firstNonEmptyString(<Object?>[
        source['receipt_number'],
        source['receipt_no'],
        outer['receipt_number'],
      ]),
      officialBalance: firstNumber(<Object?>[
        source['official_balance'],
        source['remaining_balance'],
        source['balance'],
        outer['official_balance'],
      ])?.toDouble(),
      acceptedAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[
              source['accepted_at'],
              source['posted_at'],
              source['created_at'],
              outer['accepted_at'],
            ]) ??
            '',
      ),
      code: firstNonEmptyString(<Object?>[
        outer['code'],
        stringMap(outer['error'])['code'],
        source['code'],
      ]),
      routeRevision: firstNonEmptyString(<Object?>[
        source['route_revision'],
        outer['route_revision'],
      ]),
    );
  }
}

abstract interface class IdempotencyKeyGenerator {
  String generate();
}

class SecureIdempotencyKeyGenerator implements IdempotencyKeyGenerator {
  SecureIdempotencyKeyGenerator({Random? random})
      : _random = random ?? Random.secure();

  final Random _random;

  @override
  String generate() {
    final bytes = List<int>.generate(16, (_) => _random.nextInt(256));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    final hex = bytes.map((byte) => byte.toRadixString(16).padLeft(2, '0')).join();
    return '${hex.substring(0, 8)}-'
        '${hex.substring(8, 12)}-'
        '${hex.substring(12, 16)}-'
        '${hex.substring(16, 20)}-'
        '${hex.substring(20)}';
  }
}

PaymentSubmissionDisposition? _dispositionFromValue(String? value) {
  return switch (value?.trim().toLowerCase()) {
    'accepted' || 'success' || 'posted' =>
      PaymentSubmissionDisposition.accepted,
    'duplicate' || 'replayed' => PaymentSubmissionDisposition.duplicate,
    'conflict' => PaymentSubmissionDisposition.conflict,
    'rejected' || 'invalid' || 'failed' =>
      PaymentSubmissionDisposition.rejected,
    _ => null,
  };
}

String _defaultMessage(PaymentSubmissionDisposition disposition) {
  return switch (disposition) {
    PaymentSubmissionDisposition.accepted => 'The collection was accepted.',
    PaymentSubmissionDisposition.duplicate =>
      'This collection was already accepted.',
    PaymentSubmissionDisposition.conflict =>
      'The collection conflicts with newer server data.',
    PaymentSubmissionDisposition.rejected =>
      'The collection was rejected by the server.',
  };
}

List<DateTime> _sortedUniqueDates(Iterable<DateTime> values) {
  final byText = <String, DateTime>{};
  for (final value in values) {
    final normalized = DateTime(value.year, value.month, value.day);
    byText[_date(normalized)] = normalized;
  }
  final result = byText.values.toList(growable: false)
    ..sort((left, right) => left.compareTo(right));
  return result;
}

bool _sameDate(DateTime left, DateTime right) =>
    left.year == right.year &&
    left.month == right.month &&
    left.day == right.day;

String _date(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}
