import 'dart:convert';

bool treasuryUuid(Object? value) =>
    value is String &&
    RegExp(
      r'^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$',
    ).hasMatch(value);
String requireTreasuryId(Object? value) {
  if (!treasuryUuid(value)) {
    throw const FormatException('Choose the exact current record.');
  }
  return value as String;
}

Map<String, dynamic> treasuryObject(Object? value) {
  if (value is! Map<String, dynamic>) {
    throw const FormatException('The Treasury record is incomplete.');
  }
  return value;
}

Object? immutableTreasury(Object? value) => value is Map
    ? Map<String, dynamic>.unmodifiable(
        value.map((k, v) => MapEntry(k.toString(), immutableTreasury(v))),
      )
    : value is List
    ? List<Object?>.unmodifiable(value.map(immutableTreasury))
    : value;
String canonicalTreasury(Object? value) {
  Object? sorted(Object? v) => v is Map
      ? {
          for (final key in (v.keys.map((k) => k.toString()).toList()..sort()))
            key: sorted(v[key]),
        }
      : v is List
      ? v.map(sorted).toList()
      : v;
  return jsonEncode(sorted(value));
}

class TreasuryMoney {
  TreasuryMoney(Object? value, {bool positive = false, bool signed = false}) {
    if (value is! String ||
        !RegExp(
          signed
              ? r'^-?(0|[1-9][0-9]{0,15})\.[0-9]{2}$'
              : r'^(0|[1-9][0-9]{0,15})\.[0-9]{2}$',
        ).hasMatch(value) ||
        (positive && value == '0.00')) {
      throw const FormatException(
        'Enter an exact PHP amount with two decimal places.',
      );
    }
    text = value;
  }
  late final String text;
  @override
  String toString() => text;
}

enum TreasuryAction {
  loanPayoutAcknowledge('loan_payout_acknowledge', 'Loan payout acknowledge'),
  loanPayoutCancel('loan_payout_cancel', 'Loan payout cancel'),
  loanPayoutFirstLoanComplete(
    'loan_payout_first_loan_complete',
    'Loan payout first loan complete',
  ),
  loanPayoutPrepare('loan_payout_prepare', 'Loan payout prepare'),
  loanPayoutRecipientConfirm(
    'loan_payout_recipient_confirm',
    'Loan payout recipient confirm',
  ),
  loanPayoutRenewalComplete(
    'loan_payout_renewal_complete',
    'Loan payout renewal complete',
  ),
  collectorSurplusReturnReverse(
    'collector_surplus_return_reverse',
    'Record observed return reversal',
  ),
  collectorCountAccept('collector_count_accept', 'Count accept'),
  collectorCountRecord('collector_count_record', 'Count record'),
  collectorCustodyExceptionRecord(
    'collector_custody_exception_record',
    'Custody exception record',
  ),
  collectorCustodyExceptionReturnAcknowledge(
    'collector_custody_exception_return_acknowledge',
    'Custody exception return acknowledge',
  ),
  collectorCustodyExceptionReturnPrepare(
    'collector_custody_exception_return_prepare',
    'Custody exception return prepare',
  ),
  collectorSurplusActionCancel(
    'collector_surplus_action_cancel',
    'Surplus action cancel',
  ),
  collectorSurplusApplicationPrepare(
    'collector_surplus_application_prepare',
    'Surplus application prepare',
  ),
  collectorSurplusApplicationRequest(
    'collector_surplus_application_request',
    'Surplus application request',
  ),
  collectorSurplusOpeningActivate(
    'collector_surplus_opening_activate',
    'Surplus opening activate',
  ),
  collectorSurplusOpeningPrepare(
    'collector_surplus_opening_prepare',
    'Surplus opening prepare',
  ),
  collectorSurplusRecognize('collector_surplus_recognize', 'Surplus recognize'),
  collectorSurplusResolveSource(
    'collector_surplus_resolve_source',
    'Surplus resolve source',
  ),
  collectorSurplusReturnAcknowledge(
    'collector_surplus_return_acknowledge',
    'Surplus return acknowledge',
  ),
  collectorSurplusReturnPrepare(
    'collector_surplus_return_prepare',
    'Surplus return prepare',
  ),
  collectorSurplusReturnRecord(
    'collector_surplus_return_record',
    'Surplus return record',
  ),
  collectorSurplusReturnRequest(
    'collector_surplus_return_request',
    'Surplus return request',
  ),
  accountConfigure('account_configure', 'Configure account'),
  accountGrant('account_grant', 'Account access'),
  openingPrepare('opening_prepare', 'Prepare observed opening'),
  openingActivate('opening_activate', 'Activate observed opening'),
  claimReview('claim_review', 'Review payment proof'),
  receiptVerify('receipt_verify', 'Verify received funds'),
  receiptApply('receipt_apply', 'Record loan payment'),
  disbursementRecord('disbursement_record', 'Record actual movement'),
  transferRecord('transfer_record', 'Record transfer leg'),
  movementClassify('movement_classify', 'Classify movement'),
  movementCorrect('movement_correct', 'Correct false observation'),
  receiptApplicationReverse(
    'receipt_application_reverse',
    'Reverse loan application',
  ),
  reconciliationObserve('reconciliation_observe', 'Add statement observation'),
  reconciliationMatch('reconciliation_match', 'Match statement transaction'),
  reconciliationClose('reconciliation_close', 'Close reconciliation'),
  reconciliationSupersede(
    'reconciliation_supersede',
    'Supersede reconciliation',
  );

  const TreasuryAction(this.code, this.label);
  final String code;
  final String label;
  static TreasuryAction fromCode(String code) => values.firstWhere(
    (v) => v.code == code,
    orElse: () => throw const FormatException('Unsupported Treasury action.'),
  );
}

enum TreasuryListKind { claims, events, receipts, reconciliations, openings }

enum TreasuryFieldKind {
  text,
  id,
  money,
  positiveMoney,
  integer,
  instant,
  date,
  boolean,
  choice,
  ids,
  dates,
  permissions,
  loans,
  observations,
  followup,
  digest,
  destination,
}

class TreasuryField {
  const TreasuryField(
    this.key,
    this.label,
    this.kind, {
    this.required = true,
    this.choices = const [],
    this.defaultValue,
    this.maxLength = 1000,
    this.minimum = 1,
  });
  final String key, label;
  final TreasuryFieldKind kind;
  final bool required;
  final List<String> choices;
  final Object? defaultValue;
  final int maxLength, minimum;
  Object? parse(Object? value) {
    if (value == null || value == '') {
      if (defaultValue != null) return defaultValue;
      if (!required) return null;
      throw FormatException('$label is required.');
    }
    switch (kind) {
      case TreasuryFieldKind.destination:
        final row = treasuryObject(value);
        if (row.keys.any((k) => !['kind', 'recipient_reference'].contains(k)) ||
            !['physical_cash', 'gcash', 'bank'].contains(row['kind']) ||
            !row.containsKey('recipient_reference')) {
          throw const FormatException(
            'Review the exact recipient destination.',
          );
        }
        final ref = row['recipient_reference'];
        if (ref != null &&
                (ref is! String || ref.trim().isEmpty || ref.length > 200) ||
            row['kind'] != 'physical_cash' && ref == null) {
          throw const FormatException(
            'Recipient reference is required for wallet or bank.',
          );
        }
        return immutableTreasury(row);

      case TreasuryFieldKind.id:
        return requireTreasuryId(value);
      case TreasuryFieldKind.money:
        return TreasuryMoney(value).text;
      case TreasuryFieldKind.positiveMoney:
        return TreasuryMoney(value, positive: true).text;
      case TreasuryFieldKind.integer:
        if (value is! int || value < minimum) {
          throw FormatException('$label must be a current whole version.');
        }
        return value;
      case TreasuryFieldKind.boolean:
        if (value is! bool) {
          throw FormatException('$label must be explicitly confirmed.');
        }
        return value;
      case TreasuryFieldKind.instant:
        if (value is! String ||
            !RegExp(r'(Z|[+-]\d{2}:\d{2})$').hasMatch(value) ||
            DateTime.tryParse(value) == null) {
          throw FormatException('$label requires date, time and timezone.');
        }
        return value;
      case TreasuryFieldKind.date:
        if (value is! String ||
            !RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(value) ||
            DateTime.tryParse(value)?.toIso8601String().substring(0, 10) !=
                value) {
          throw FormatException('$label requires a valid date.');
        }
        return value;
      case TreasuryFieldKind.choice:
        if (value is! String || !choices.contains(value)) {
          throw FormatException('Choose $label.');
        }
        return value;
      case TreasuryFieldKind.followup:
        final row = treasuryObject(value);
        if (row.keys.any(
          (k) => ![
            'reason_code',
            'note',
            'promised_payment_date',
            'promised_amount',
          ].contains(k),
        )) {
          throw const FormatException('Invalid past due follow-up.');
        }
        const codes = [
          'no_cash',
          'client_absent',
          'business_slow',
          'sick_hospital',
          'emergency',
          'promised_to_pay_later',
          'other',
        ];
        if (!codes.contains(row['reason_code']) ||
            row['note'] != null &&
                (row['note'] is! String ||
                    (row['note'] as String).length > 500)) {
          throw const FormatException('Choose a valid past due follow-up.');
        }
        final promise = row['reason_code'] == 'promised_to_pay_later';
        if (promise) {
          const TreasuryField(
            'date',
            'Promise date',
            TreasuryFieldKind.date,
          ).parse(row['promised_payment_date']);
          TreasuryMoney(row['promised_amount'], positive: true);
        } else if (row['promised_payment_date'] != null ||
            row['promised_amount'] != null) {
          throw const FormatException(
            'Promise details require promised to pay later.',
          );
        }
        if (row['reason_code'] == 'other' &&
            (row['note'] as String? ?? '').trim().isEmpty) {
          throw const FormatException('Other requires an explanation.');
        }
        return row;
      case TreasuryFieldKind.digest:
        if (value is! String || !RegExp(r'^[a-f0-9]{64}$').hasMatch(value)) {
          throw const FormatException('Review a current server preview.');
        }
        return value;
      case TreasuryFieldKind.ids:
        if (value is! List || value.isEmpty || value.length > 2) {
          throw const FormatException('Choose one or two current loans.');
        }
        return value.map(requireTreasuryId).toList();
      case TreasuryFieldKind.dates:
        if (value is! List || value.length > 366) {
          throw const FormatException('Choose valid coverage dates.');
        }
        return value
            .map(
              (v) => const TreasuryField(
                'date',
                'Coverage date',
                TreasuryFieldKind.date,
              ).parse(v),
            )
            .toList();
      case TreasuryFieldKind.permissions:
        if (value is! List ||
            value.length > 10 ||
            value.any(
              (v) => v is! String || !treasuryPermissionCodes.contains(v),
            )) {
          throw const FormatException('Choose supported access permissions.');
        }
        return value;
      case TreasuryFieldKind.loans:
        if (value is! List || value.isEmpty || value.length > 2) {
          throw const FormatException('Choose one or two current loans.');
        }
        return value.map((v) {
          final row = treasuryObject(v);
          if (row.keys.any(
            (k) => !['loan_id', 'expected_version'].contains(k),
          )) {
            throw const FormatException('Invalid loan choice.');
          }
          return {
            'loan_id': requireTreasuryId(row['loan_id']),
            'expected_version': const TreasuryField(
              'version',
              'Loan version',
              TreasuryFieldKind.integer,
              minimum: 0,
            ).parse(row['expected_version']),
          };
        }).toList();
      case TreasuryFieldKind.observations:
        if (value is! List || value.length > 500) {
          throw const FormatException('Statement transaction limit is 500.');
        }
        return value.map((v) {
          final row = treasuryObject(v);
          final result = <String, dynamic>{};
          for (final f in observationFields) {
            result[f.key] = f.parse(row[f.key]);
          }
          if (row.keys.any((k) => !result.containsKey(k))) {
            throw const FormatException('Invalid statement transaction.');
          }
          return result;
        }).toList();
      case TreasuryFieldKind.text:
        if (value is! String ||
            value.trim().isEmpty ||
            value.length > maxLength) {
          throw FormatException('$label is incomplete or too long.');
        }
        return value.trim();
    }
  }
}

const treasuryPermissionCodes = [
  'treasury.account.manage',
  'treasury.view',
  'treasury.proof.submit.assigned',
  'treasury.proof.review',
  'treasury.receipt.verify',
  'treasury.payment.apply',
  'treasury.disbursement.record',
  'treasury.transfer.record',
  'treasury.reconcile',
  'treasury.adjust',
  'treasury.collector_surplus.receive',
  'treasury.collector_surplus.resolve',
  'treasury.collector_surplus.settle',
  'treasury.collector_surplus.view',
];
const idKind = TreasuryFieldKind.id,
    textKind = TreasuryFieldKind.text,
    moneyKind = TreasuryFieldKind.money,
    positiveKind = TreasuryFieldKind.positiveMoney,
    intKind = TreasuryFieldKind.integer,
    timeKind = TreasuryFieldKind.instant,
    choiceKind = TreasuryFieldKind.choice,
    boolKind = TreasuryFieldKind.boolean;
const reasonField = TreasuryField('reason', 'Reason', textKind);
const observationFields = [
  TreasuryField('id', 'Statement row ID', idKind),
  TreasuryField('provider', 'Provider', textKind, maxLength: 200),
  TreasuryField(
    'reference',
    'Reference (if present)',
    textKind,
    required: false,
    maxLength: 200,
  ),
  TreasuryField(
    'direction',
    'Direction',
    choiceKind,
    choices: ['credit', 'debit'],
  ),
  TreasuryField('amount', 'Amount', positiveKind),
  TreasuryField('effective_at', 'Actual transaction time', timeKind),
];
const applicationFields = [
  TreasuryField(
    'mode',
    'Application mode',
    choiceKind,
    choices: ['single', 'combined'],
  ),
  TreasuryField('total_amount', 'Amount to apply', positiveKind),
  TreasuryField('loans', 'Current loan choices', TreasuryFieldKind.loans),
  TreasuryField(
    'intent',
    'Allocation intent',
    choiceKind,
    choices: [
      'scheduled',
      'no_collection_voluntary',
      'extra_as_advance',
      'extra_as_principal_reduction',
    ],
    defaultValue: 'scheduled',
  ),
  TreasuryField(
    'covered_dates',
    'Coverage dates',
    TreasuryFieldKind.dates,
    defaultValue: [],
  ),
  TreasuryField(
    'extra_choice',
    'Excess allocation',
    choiceKind,
    required: false,
    choices: [
      'seven_by_seven_advance',
      'seven_by_seven_extra_principal',
      'regular_advance',
      'regular_principal_reduction',
    ],
  ),
  TreasuryField(
    'regular_past_due_followup',
    'Regular past due follow-up',
    TreasuryFieldKind.followup,
    required: false,
  ),
  TreasuryField('effective_date', 'Effective date', TreasuryFieldKind.date),
];
const transactionFields = [
  TreasuryField('amount', 'Actual amount', positiveKind),
  TreasuryField('fee', 'Actual fee', moneyKind, defaultValue: '0.00'),
  TreasuryField('provider', 'Provider', textKind, maxLength: 200),
  TreasuryField('reference', 'Recipient reference', textKind, maxLength: 200),
  TreasuryField('effective_at', 'Actual transaction time', timeKind),
  TreasuryField('evidence_id', 'Recipient evidence ID', idKind),
  TreasuryField('recipient_attestation', 'Recipient verification', textKind),
  reasonField,
];
final Map<TreasuryAction, List<TreasuryField>> treasuryFields = {
  TreasuryAction.loanPayoutAcknowledge: [
    TreasuryField('payout_id', 'Payout id', TreasuryFieldKind.id),
    TreasuryField(
      'payout_version',
      'Payout version',
      TreasuryFieldKind.integer,
    ),
    TreasuryField(
      'stage',
      'Stage',
      TreasuryFieldKind.choice,
      choices: ["recipient", "borrower_handover", "borrower"],
    ),
    TreasuryField('received', 'Received', TreasuryFieldKind.boolean),
    TreasuryField(
      'reviewed_amount',
      'Reviewed amount',
      TreasuryFieldKind.positiveMoney,
    ),
    TreasuryField(
      'receipt_method',
      'Receipt method',
      TreasuryFieldKind.choice,
      choices: ["cash", "gcash", "bank"],
    ),
    TreasuryField(
      'acknowledged_at',
      'Acknowledged at',
      TreasuryFieldKind.instant,
    ),
    TreasuryField(
      'attestation',
      'Attestation',
      TreasuryFieldKind.text,
      maxLength: 1000,
    ),
  ],
  TreasuryAction.loanPayoutCancel: [
    TreasuryField('payout_id', 'Payout id', TreasuryFieldKind.id),
    TreasuryField(
      'payout_version',
      'Payout version',
      TreasuryFieldKind.integer,
    ),
    TreasuryField('reason', 'Reason', TreasuryFieldKind.text, maxLength: 1000),
  ],
  TreasuryAction.loanPayoutFirstLoanComplete: [
    TreasuryField('payout_id', 'Payout id', TreasuryFieldKind.id),
    TreasuryField(
      'payout_version',
      'Payout version',
      TreasuryFieldKind.integer,
    ),
    TreasuryField('evidence_id', 'Evidence id', TreasuryFieldKind.id),
    TreasuryField(
      'reviewed_amount',
      'Reviewed amount',
      TreasuryFieldKind.positiveMoney,
    ),
    TreasuryField(
      'borrower_confirmed',
      'Borrower confirmed',
      TreasuryFieldKind.boolean,
    ),
    TreasuryField(
      'receipt_method',
      'Receipt method',
      TreasuryFieldKind.choice,
      choices: ["cash", "gcash", "bank"],
    ),
    TreasuryField(
      'acknowledged_at',
      'Acknowledged at',
      TreasuryFieldKind.instant,
    ),
    TreasuryField(
      'borrower_attestation',
      'Borrower attestation',
      TreasuryFieldKind.text,
      maxLength: 1000,
    ),
  ],
  TreasuryAction.loanPayoutPrepare: [
    TreasuryField(
      'source_kind',
      'Source kind',
      TreasuryFieldKind.choice,
      choices: ["first_loan", "renewal"],
    ),
    TreasuryField('source_id', 'Source id', TreasuryFieldKind.id),
    TreasuryField(
      'destination',
      'Destination',
      TreasuryFieldKind.choice,
      required: false,
      choices: ["collector", "borrower"],
      defaultValue: "collector",
    ),
    TreasuryField(
      'recipient_reference',
      'Recipient reference',
      TreasuryFieldKind.text,
      maxLength: 200,
    ),
    TreasuryField(
      'authorization_id',
      'Authorization id',
      TreasuryFieldKind.id,
      required: false,
    ),
    TreasuryField(
      'packet_hash',
      'Packet hash',
      TreasuryFieldKind.digest,
      required: false,
    ),
    TreasuryField(
      'contract_evidence_reference',
      'Contract evidence reference',
      TreasuryFieldKind.text,
      required: false,
      maxLength: 200,
    ),
    TreasuryField('source_digest', 'Source digest', TreasuryFieldKind.digest),
  ],
  TreasuryAction.loanPayoutRecipientConfirm: [
    TreasuryField('payout_id', 'Payout id', TreasuryFieldKind.id),
    TreasuryField(
      'payout_version',
      'Payout version',
      TreasuryFieldKind.integer,
    ),
    TreasuryField('evidence_id', 'Evidence id', TreasuryFieldKind.id),
    TreasuryField(
      'reviewed_amount',
      'Reviewed amount',
      TreasuryFieldKind.positiveMoney,
    ),
    TreasuryField('received', 'Received', TreasuryFieldKind.boolean),
    TreasuryField(
      'acknowledged_at',
      'Acknowledged at',
      TreasuryFieldKind.instant,
    ),
    TreasuryField(
      'recipient_attestation',
      'Recipient attestation',
      TreasuryFieldKind.text,
      maxLength: 1000,
    ),
  ],
  TreasuryAction.loanPayoutRenewalComplete: [
    TreasuryField('payout_id', 'Payout id', TreasuryFieldKind.id),
    TreasuryField(
      'payout_version',
      'Payout version',
      TreasuryFieldKind.integer,
    ),
    TreasuryField('evidence_id', 'Evidence id', TreasuryFieldKind.id),
    TreasuryField(
      'reviewed_amount',
      'Reviewed amount',
      TreasuryFieldKind.positiveMoney,
    ),
    TreasuryField(
      'proof_review_confirmed',
      'Proof review confirmed',
      TreasuryFieldKind.boolean,
    ),
    TreasuryField('reason', 'Reason', TreasuryFieldKind.text, maxLength: 1000),
  ],
  TreasuryAction.collectorSurplusReturnReverse: [
    TreasuryField('action_id', 'Action id', TreasuryFieldKind.id),
    TreasuryField(
      'action_version',
      'Action version',
      TreasuryFieldKind.integer,
    ),
    TreasuryField('amount', 'Amount', TreasuryFieldKind.positiveMoney),
    TreasuryField(
      'provider',
      'Provider',
      TreasuryFieldKind.text,
      maxLength: 200,
    ),
    TreasuryField(
      'reference',
      'Reference',
      TreasuryFieldKind.text,
      maxLength: 200,
    ),
    TreasuryField('effective_at', 'Effective at', TreasuryFieldKind.instant),
    TreasuryField('evidence_id', 'Evidence id', TreasuryFieldKind.id),
    TreasuryField(
      'recipient_attestation',
      'Recipient attestation',
      TreasuryFieldKind.text,
      maxLength: 1000,
    ),
    TreasuryField('reason', 'Reason', TreasuryFieldKind.text, maxLength: 1000),
  ],
  TreasuryAction.collectorCountAccept: [
    TreasuryField('count_id', 'Count id', TreasuryFieldKind.id),
    TreasuryField('count_version', 'Count version', TreasuryFieldKind.integer),
    TreasuryField('source_digest', 'Source digest', TreasuryFieldKind.digest),
    TreasuryField(
      'physical_receipt_acknowledged',
      'Physical receipt acknowledged',
      TreasuryFieldKind.boolean,
    ),
    TreasuryField(
      'credit_application_id',
      'Credit application id',
      TreasuryFieldKind.id,
      required: false,
    ),
    TreasuryField(
      'credit_application_version',
      'Credit application version',
      TreasuryFieldKind.integer,
      required: false,
    ),
  ],
  TreasuryAction.collectorCountRecord: [
    TreasuryField('remittance_id', 'Remittance id', TreasuryFieldKind.id),
    TreasuryField('source_digest', 'Source digest', TreasuryFieldKind.digest),
    TreasuryField('counted_amount', 'Counted amount', TreasuryFieldKind.money),
    TreasuryField('counted_at', 'Counted at', TreasuryFieldKind.instant),
    TreasuryField('evidence_id', 'Evidence id', TreasuryFieldKind.id),
    TreasuryField(
      'recipient_attestation',
      'Recipient attestation',
      TreasuryFieldKind.text,
      maxLength: 1000,
    ),
    TreasuryField(
      'review_acknowledged',
      'Review acknowledged',
      TreasuryFieldKind.boolean,
    ),
  ],
  TreasuryAction.collectorCustodyExceptionRecord: [
    TreasuryField('count_id', 'Count id', TreasuryFieldKind.id),
    TreasuryField('count_version', 'Count version', TreasuryFieldKind.integer),
    TreasuryField('source_digest', 'Source digest', TreasuryFieldKind.digest),
    TreasuryField(
      'retained_amount',
      'Retained amount',
      TreasuryFieldKind.positiveMoney,
    ),
    TreasuryField('retained_at', 'Retained at', TreasuryFieldKind.instant),
    TreasuryField('evidence_id', 'Evidence id', TreasuryFieldKind.id),
    TreasuryField(
      'holder_attestation',
      'Holder attestation',
      TreasuryFieldKind.text,
      maxLength: 1000,
    ),
    TreasuryField('reason', 'Reason', TreasuryFieldKind.text, maxLength: 1000),
  ],
  TreasuryAction.collectorCustodyExceptionReturnAcknowledge: [
    TreasuryField('action_id', 'Action id', TreasuryFieldKind.id),
    TreasuryField(
      'action_version',
      'Action version',
      TreasuryFieldKind.integer,
    ),
    TreasuryField('event_id', 'Event id', TreasuryFieldKind.id),
    TreasuryField('event_version', 'Event version', TreasuryFieldKind.integer),
    TreasuryField(
      'reviewed_amount',
      'Reviewed amount',
      TreasuryFieldKind.positiveMoney,
    ),
    TreasuryField(
      'confirmation',
      'Confirmation',
      TreasuryFieldKind.choice,
      choices: ['received', 'not_received'],
    ),
    TreasuryField(
      'acknowledged_at',
      'Acknowledged at',
      TreasuryFieldKind.instant,
    ),
    TreasuryField('reason', 'Reason', TreasuryFieldKind.text, maxLength: 1000),
    TreasuryField('exception_id', 'Exception id', TreasuryFieldKind.id),
    TreasuryField(
      'exception_version',
      'Exception version',
      TreasuryFieldKind.integer,
    ),
  ],
  TreasuryAction.collectorCustodyExceptionReturnPrepare: [
    TreasuryField('exception_id', 'Exception id', TreasuryFieldKind.id),
    TreasuryField(
      'exception_version',
      'Exception version',
      TreasuryFieldKind.integer,
    ),
    TreasuryField('amount', 'Amount', TreasuryFieldKind.positiveMoney),
    TreasuryField('evidence_id', 'Evidence id', TreasuryFieldKind.id),
    TreasuryField('reason', 'Reason', TreasuryFieldKind.text, maxLength: 1000),
  ],
  TreasuryAction.collectorSurplusActionCancel: [
    TreasuryField('action_id', 'Action id', TreasuryFieldKind.id),
    TreasuryField(
      'action_version',
      'Action version',
      TreasuryFieldKind.integer,
    ),
    TreasuryField('evidence_id', 'Evidence id', TreasuryFieldKind.id),
    TreasuryField('reason', 'Reason', TreasuryFieldKind.text, maxLength: 1000),
  ],
  TreasuryAction.collectorSurplusApplicationPrepare: [
    TreasuryField('credit_id', 'Credit id', TreasuryFieldKind.id),
    TreasuryField(
      'credit_version',
      'Credit version',
      TreasuryFieldKind.integer,
    ),
    TreasuryField(
      'collector_request_id',
      'Collector request id',
      TreasuryFieldKind.id,
    ),
    TreasuryField(
      'collector_request_version',
      'Collector request version',
      TreasuryFieldKind.integer,
    ),
    TreasuryField('remittance_id', 'Remittance id', TreasuryFieldKind.id),
    TreasuryField('source_digest', 'Source digest', TreasuryFieldKind.digest),
    TreasuryField('amount', 'Amount', TreasuryFieldKind.positiveMoney),
    TreasuryField('evidence_id', 'Evidence id', TreasuryFieldKind.id),
    TreasuryField('reason', 'Reason', TreasuryFieldKind.text, maxLength: 1000),
  ],
  TreasuryAction.collectorSurplusApplicationRequest: [
    TreasuryField('credit_id', 'Credit id', TreasuryFieldKind.id),
    TreasuryField(
      'credit_version',
      'Credit version',
      TreasuryFieldKind.integer,
    ),
    TreasuryField('remittance_id', 'Remittance id', TreasuryFieldKind.id),
    TreasuryField('source_digest', 'Source digest', TreasuryFieldKind.digest),
    TreasuryField('amount', 'Amount', TreasuryFieldKind.positiveMoney),
    TreasuryField('reason', 'Reason', TreasuryFieldKind.text, maxLength: 1000),
  ],
  TreasuryAction.collectorSurplusOpeningActivate: [
    TreasuryField('anchor_id', 'Anchor id', TreasuryFieldKind.id),
    TreasuryField(
      'anchor_version',
      'Anchor version',
      TreasuryFieldKind.integer,
    ),
    TreasuryField('reason', 'Reason', TreasuryFieldKind.text, maxLength: 1000),
  ],
  TreasuryAction.collectorSurplusOpeningPrepare: [
    const TreasuryField(
      'anchor_kind',
      'Opening classification',
      TreasuryFieldKind.choice,
      required: false,
      choices: ['credit', 'pending_excess'],
      defaultValue: 'credit',
    ),
    TreasuryField(
      'collector_user_id',
      'Collector user id',
      TreasuryFieldKind.id,
    ),
    TreasuryField('opening_id', 'Opening id', TreasuryFieldKind.id),
    TreasuryField(
      'opening_version',
      'Opening version',
      TreasuryFieldKind.integer,
    ),
    TreasuryField('amount', 'Amount', TreasuryFieldKind.positiveMoney),
    TreasuryField('evidence_id', 'Evidence id', TreasuryFieldKind.id),
    TreasuryField(
      'overlap_review_acknowledged',
      'Overlap review acknowledged',
      TreasuryFieldKind.boolean,
    ),
    TreasuryField('reason', 'Reason', TreasuryFieldKind.text, maxLength: 1000),
  ],
  TreasuryAction.collectorSurplusRecognize: [
    TreasuryField(
      'source_review_acknowledged',
      'Source review acknowledged',
      TreasuryFieldKind.boolean,
    ),
    TreasuryField('case_id', 'Case id', TreasuryFieldKind.id),
    TreasuryField('case_version', 'Case version', TreasuryFieldKind.integer),
    TreasuryField('amount', 'Amount', TreasuryFieldKind.positiveMoney),
    TreasuryField('source_digest', 'Source digest', TreasuryFieldKind.digest),
    TreasuryField('evidence_id', 'Evidence id', TreasuryFieldKind.id),
    TreasuryField('reason', 'Reason', TreasuryFieldKind.text, maxLength: 1000),
  ],
  TreasuryAction.collectorSurplusResolveSource: [
    TreasuryField('case_id', 'Case id', TreasuryFieldKind.id, required: false),
    TreasuryField(
      'case_version',
      'Case version',
      TreasuryFieldKind.integer,
      required: false,
    ),
    TreasuryField(
      'credit_id',
      'Credit id',
      TreasuryFieldKind.id,
      required: false,
    ),
    TreasuryField(
      'credit_version',
      'Credit version',
      TreasuryFieldKind.integer,
      required: false,
    ),
    TreasuryField('source_id', 'Source id', TreasuryFieldKind.id),
    TreasuryField('source_digest', 'Source digest', TreasuryFieldKind.digest),
    TreasuryField('amount', 'Amount', TreasuryFieldKind.positiveMoney),
    TreasuryField('evidence_id', 'Evidence id', TreasuryFieldKind.id),
    TreasuryField('reason', 'Reason', TreasuryFieldKind.text, maxLength: 1000),
  ],
  TreasuryAction.collectorSurplusReturnAcknowledge: [
    TreasuryField('action_id', 'Action id', TreasuryFieldKind.id),
    TreasuryField(
      'action_version',
      'Action version',
      TreasuryFieldKind.integer,
    ),
    TreasuryField('event_id', 'Event id', TreasuryFieldKind.id),
    TreasuryField('event_version', 'Event version', TreasuryFieldKind.integer),
    TreasuryField(
      'reviewed_amount',
      'Reviewed amount',
      TreasuryFieldKind.positiveMoney,
    ),
    TreasuryField(
      'confirmation',
      'Confirmation',
      TreasuryFieldKind.choice,
      choices: ['received', 'not_received'],
    ),
    TreasuryField(
      'acknowledged_at',
      'Acknowledged at',
      TreasuryFieldKind.instant,
    ),
    TreasuryField('reason', 'Reason', TreasuryFieldKind.text, maxLength: 1000),
    TreasuryField('credit_id', 'Credit id', TreasuryFieldKind.id),
    TreasuryField(
      'credit_version',
      'Credit version',
      TreasuryFieldKind.integer,
    ),
  ],
  TreasuryAction.collectorSurplusReturnPrepare: [
    TreasuryField('credit_id', 'Credit id', TreasuryFieldKind.id),
    TreasuryField(
      'credit_version',
      'Credit version',
      TreasuryFieldKind.integer,
    ),
    TreasuryField(
      'collector_request_id',
      'Collector request id',
      TreasuryFieldKind.id,
    ),
    TreasuryField(
      'collector_request_version',
      'Collector request version',
      TreasuryFieldKind.integer,
    ),
    TreasuryField('amount', 'Amount', TreasuryFieldKind.positiveMoney),
    TreasuryField('destination', 'Destination', TreasuryFieldKind.destination),
    TreasuryField('evidence_id', 'Evidence id', TreasuryFieldKind.id),
    TreasuryField('reason', 'Reason', TreasuryFieldKind.text, maxLength: 1000),
  ],
  TreasuryAction.collectorSurplusReturnRecord: [
    TreasuryField('action_id', 'Action id', TreasuryFieldKind.id),
    TreasuryField(
      'action_version',
      'Action version',
      TreasuryFieldKind.integer,
    ),
    TreasuryField('event_id', 'Event id', TreasuryFieldKind.id),
    TreasuryField('event_version', 'Event version', TreasuryFieldKind.integer),
    TreasuryField(
      'acknowledgment_id',
      'Acknowledgment id',
      TreasuryFieldKind.id,
    ),
    TreasuryField(
      'acknowledgment_version',
      'Acknowledgment version',
      TreasuryFieldKind.integer,
    ),
    TreasuryField('reason', 'Reason', TreasuryFieldKind.text, maxLength: 1000),
  ],
  TreasuryAction.collectorSurplusReturnRequest: [
    TreasuryField('credit_id', 'Credit id', TreasuryFieldKind.id),
    TreasuryField(
      'credit_version',
      'Credit version',
      TreasuryFieldKind.integer,
    ),
    TreasuryField('amount', 'Amount', TreasuryFieldKind.positiveMoney),
    TreasuryField('destination', 'Destination', TreasuryFieldKind.destination),
    TreasuryField('reason', 'Reason', TreasuryFieldKind.text, maxLength: 1000),
  ],
  TreasuryAction.accountConfigure: const [
    TreasuryField('ledger_context_id', 'Ledger context ID', idKind),
    TreasuryField(
      'context',
      'Ledger context',
      choiceKind,
      choices: ['owner_operations', 'corporate_legal', 'synthetic'],
    ),
    TreasuryField(
      'kind',
      'Account kind',
      choiceKind,
      choices: ['physical_cash', 'gcash', 'bank', 'transit'],
    ),
    TreasuryField('alias', 'Account alias', textKind, maxLength: 120),
    TreasuryField(
      'ownership',
      'Ownership',
      choiceKind,
      choices: ['owner_personal', 'owner_business', 'corporate', 'synthetic'],
    ),
    TreasuryField('custodian_user_id', 'Verified custodian account ID', idKind),
    TreasuryField(
      'masked_identifier',
      'Masked identifier',
      textKind,
      required: false,
      maxLength: 100,
    ),
    TreasuryField(
      'payment_instructions',
      'Payment instructions',
      textKind,
      required: false,
    ),
    TreasuryField(
      'designated_receiving',
      'Receiving account',
      boolKind,
      defaultValue: false,
    ),
    TreasuryField('active', 'Active', boolKind, defaultValue: true),
  ],
  TreasuryAction.accountGrant: const [
    TreasuryField('user_id', 'Verified delegate account ID', idKind),
    TreasuryField('permissions', 'Permissions', TreasuryFieldKind.permissions),
    TreasuryField(
      'private_history',
      'Private history access',
      boolKind,
      defaultValue: false,
    ),
    TreasuryField('enabled', 'Enabled', boolKind, defaultValue: true),
  ],
  TreasuryAction.openingPrepare: const [
    TreasuryField('cutoff', 'Observed cutoff', timeKind),
    TreasuryField('amount', 'Observed amount', moneyKind),
    TreasuryField('evidence_id', 'Opening evidence ID', idKind),
    reasonField,
    TreasuryField(
      'personal_amount',
      'Personal portion',
      moneyKind,
      required: false,
    ),
    TreasuryField(
      'third_party_amount',
      'Third-party portion',
      moneyKind,
      required: false,
    ),
    TreasuryField(
      'transit_amount',
      'Transit portion',
      moneyKind,
      required: false,
    ),
  ],
  TreasuryAction.openingActivate: const [
    TreasuryField('opening_id', 'Prepared opening ID', idKind),
    TreasuryField('opening_version', 'Opening version', intKind),
    TreasuryField('confirmed', 'Observed count verified', boolKind),
    reasonField,
  ],
  TreasuryAction.claimReview: const [
    TreasuryField('claim_id', 'Payment proof ID', idKind),
    TreasuryField('claim_version', 'Proof version', intKind),
    TreasuryField(
      'decision',
      'Review decision',
      choiceKind,
      choices: ['reviewed', 'correction_required', 'rejected'],
    ),
    reasonField,
  ],
  TreasuryAction.receiptVerify: const [
    TreasuryField('client_id', 'Borrower ID', idKind),
    TreasuryField('claim_id', 'Related proof ID', idKind, required: false),
    TreasuryField('claim_version', 'Proof version', intKind, required: false),
    TreasuryField('amount', 'Received amount', positiveKind),
    TreasuryField('provider', 'Provider', textKind, maxLength: 200),
    TreasuryField(
      'reference',
      'Recipient transaction reference',
      textKind,
      maxLength: 200,
    ),
    TreasuryField('effective_at', 'Received transaction time', timeKind),
    TreasuryField('evidence_id', 'Recipient evidence ID', idKind),
    TreasuryField('recipient_attestation', 'Recipient verification', textKind),
    reasonField,
  ],
  TreasuryAction.receiptApply: [
    const TreasuryField('receipt_id', 'Verified receipt ID', idKind),
    const TreasuryField(
      'digest',
      'Server preview digest',
      TreasuryFieldKind.digest,
    ),
    ...applicationFields,
  ],
  TreasuryAction.disbursementRecord: [
    ...transactionFields.where((f) => f.key != 'reference'),
    const TreasuryField(
      'reference',
      'Actual reference (if present)',
      textKind,
      required: false,
      maxLength: 200,
    ),
    const TreasuryField(
      'direction',
      'Direction',
      choiceKind,
      choices: ['credit', 'debit'],
      defaultValue: 'debit',
    ),
    const TreasuryField(
      'purpose',
      'Purpose',
      choiceKind,
      choices: [
        'unclassified',
        'personal',
        'loan_release',
        'renewal',
        'payroll',
        'salary_advance',
        'expense',
        'refund',
        'collector_surplus_return',
        'collector_custody_exception_return',
        'owner_contribution',
        'owner_withdrawal',
        'deposit',
      ],
    ),
    const TreasuryField(
      'source_id',
      'Approved source ID',
      idKind,
      required: false,
    ),
    const TreasuryField(
      'source_version',
      'Current source version',
      intKind,
      required: false,
    ),
    const TreasuryField('payee_id', 'Actual payee ID', idKind, required: false),
    const TreasuryField(
      'destination_confirmed',
      'Destination verified',
      boolKind,
      defaultValue: false,
    ),
    const TreasuryField(
      'destination_evidence_id',
      'Destination evidence ID',
      idKind,
      required: false,
    ),
    const TreasuryField(
      'payee_acknowledgment',
      'Actual payee acknowledgment',
      textKind,
      required: false,
    ),
    const TreasuryField(
      'receipt_id',
      'Related original receipt ID',
      idKind,
      required: false,
    ),
  ],
  TreasuryAction.transferRecord: [
    ...transactionFields,
    const TreasuryField('transfer_id', 'Paired transfer ID', idKind),
    const TreasuryField(
      'leg',
      'Actual leg',
      choiceKind,
      choices: ['source', 'destination'],
    ),
    const TreasuryField('other_account_id', 'Other account ID', idKind),
    const TreasuryField(
      'other_account_version',
      'Other account version',
      intKind,
    ),
  ],
  TreasuryAction.movementClassify: const [
    TreasuryField('event_id', 'Movement ID', idKind),
    TreasuryField('event_version', 'Movement version', intKind),
    TreasuryField(
      'classification',
      'Classification',
      choiceKind,
      choices: [
        'personal',
        'owner_contribution',
        'owner_withdrawal',
        'unclassified',
      ],
    ),
    reasonField,
  ],
  TreasuryAction.movementCorrect: const [
    TreasuryField('event_id', 'Original movement ID', idKind),
    TreasuryField('event_version', 'Movement version', intKind),
    TreasuryField('evidence_id', 'Correction evidence ID', idKind),
    reasonField,
    TreasuryField(
      'correction',
      'Correction',
      choiceKind,
      choices: ['false_observation'],
      defaultValue: 'false_observation',
    ),
  ],
  TreasuryAction.receiptApplicationReverse: const [
    TreasuryField('receipt_id', 'Receipt ID', idKind),
    TreasuryField('application_id', 'Official application ID', idKind),
    reasonField,
  ],
  TreasuryAction.reconciliationObserve: const [
    TreasuryField('reconciliation_id', 'Statement session ID', idKind),
    TreasuryField('coverage_start', 'Coverage start', timeKind),
    TreasuryField('cutoff', 'Coverage cutoff', timeKind),
    TreasuryField('actual_balance', 'Observed balance', moneyKind),
    TreasuryField('evidence_id', 'Private statement evidence ID', idKind),
    TreasuryField('complete_history', 'Full coverage verified', boolKind),
    TreasuryField(
      'rows',
      'Statement transactions',
      TreasuryFieldKind.observations,
    ),
  ],
  TreasuryAction.reconciliationMatch: const [
    TreasuryField('reconciliation_id', 'Statement session ID', idKind),
    TreasuryField(
      'reconciliation_version',
      'Statement session version',
      intKind,
    ),
    TreasuryField('observation_id', 'Statement row ID', idKind),
    TreasuryField('event_id', 'Existing movement ID', idKind),
    TreasuryField(
      'component',
      'Matched component',
      choiceKind,
      choices: ['total', 'principal', 'fee'],
      defaultValue: 'total',
    ),
    TreasuryField(
      'exception_reason',
      'Exception explanation',
      textKind,
      required: false,
    ),
  ],
  TreasuryAction.reconciliationClose: const [
    TreasuryField('reconciliation_id', 'Statement session ID', idKind),
    TreasuryField(
      'reconciliation_version',
      'Statement session version',
      intKind,
    ),
    TreasuryField('opening_id', 'Observed opening ID', idKind),
    TreasuryField(
      'movement_watermark',
      'Current movement watermark',
      intKind,
      minimum: 0,
    ),
    reasonField,
  ],
  TreasuryAction.reconciliationSupersede: const [
    TreasuryField('reconciliation_id', 'New statement session ID', idKind),
    TreasuryField('reconciliation_version', 'New statement version', intKind),
    TreasuryField('opening_id', 'Observed opening ID', idKind),
    TreasuryField(
      'movement_watermark',
      'Current movement watermark',
      intKind,
      minimum: 0,
    ),
    TreasuryField('prior_reconciliation_id', 'Prior closed session ID', idKind),
    reasonField,
  ],
};

class TreasuryCommand {
  TreasuryCommand(
    this.action, {
    required String requestId,
    String? accountId,
    int? expectedVersion,
    required Map<String, dynamic> fields,
  }) {
    final own =
        collectorOwnActions.contains(action) ||
        action == TreasuryAction.loanPayoutAcknowledge;
    if (own && (accountId != null || expectedVersion != null)) {
      throw const FormatException("Own requests carry no account authority.");
    }
    if (!own &&
        (expectedVersion == null ||
            expectedVersion <
                (action == TreasuryAction.accountConfigure ? 0 : 1))) {
      throw const FormatException('Refresh the current account version.');
    }
    final schema = treasuryFields[action]!;
    if (fields.keys.any((key) => !schema.any((f) => f.key == key))) {
      throw const FormatException('Unsupported Treasury request field.');
    }
    final body = <String, dynamic>{
      'action': action.code,
      'request_id': requireTreasuryId(requestId),
      if (!own) 'account_id': requireTreasuryId(accountId),
      if (!own) 'expected_version': expectedVersion,
    };
    for (final f in schema) {
      final value = f.parse(fields[f.key]);
      if (value != null ||
          action == TreasuryAction.disbursementRecord && f.key == 'reference') {
        body[f.key] = value;
      }
    }
    if (action == TreasuryAction.openingActivate && body['confirmed'] != true) {
      throw const FormatException('Confirm the actual observed opening.');
    }
    for (final key in [
      'review_acknowledged',
      'physical_receipt_acknowledged',
      'source_review_acknowledged',
      'overlap_review_acknowledged',
    ]) {
      if (body.containsKey(key) && body[key] != true) {
        throw FormatException('Explicit $key review is required.');
      }
    }
    if (action == TreasuryAction.collectorSurplusResolveSource &&
        ((body['case_id'] == null) == (body['credit_id'] == null) ||
            (body['case_id'] == null) != (body['case_version'] == null) ||
            (body['credit_id'] == null) != (body['credit_version'] == null))) {
      throw const FormatException(
        'Choose one exact case or credit with its version.',
      );
    }
    if (action == TreasuryAction.loanPayoutPrepare) {
      const authority = [
        'authorization_id',
        'packet_hash',
        'contract_evidence_reference',
      ];
      if (body['source_kind'] == 'first_loan' &&
              authority.any((k) => body[k] == null) ||
          body['source_kind'] == 'renewal' &&
              authority.any((k) => body[k] != null)) {
        throw const FormatException(
          'The exact approved source authority is required.',
        );
      }
    }
    _body = treasuryObject(immutableTreasury(body));
  }
  final TreasuryAction action;
  late final Map<String, dynamic> _body;
  String get requestId => _body['request_id'] as String;
  String get accountId => _body['account_id'] as String;
  int get expectedVersion => _body['expected_version'] as int;
  Map<String, dynamic> toJson() => _body;
}

String treasuryBlockerMessage(Object? value) {
  if (value is String && value.trim().isNotEmpty) {
    return value;
  }
  if (value is Map &&
      value['code'] is String &&
      (value['code'] as String).trim().isNotEmpty &&
      value['message'] is String &&
      (value['message'] as String).trim().isNotEmpty) {
    return value['message'] as String;
  }
  throw const FormatException('The server blocker is incomplete.');
}

/// Server amounts stay decimal strings; totals are never inferred from rows.
void validateTreasuryFinancialProjection(Object? value) {
  if (value is List) {
    for (final row in value) {
      validateTreasuryFinancialProjection(row);
    }
  } else if (value is Map) {
    for (final entry in value.entries) {
      if (entry.value != null &&
          const {
            'amount',
            'fee',
            'remaining_amount',
            'applied_amount',
            'refunded_amount',
            'unapplied_amount',
            'unallocated_amount',
            'total_amount',
            'actual_balance',
            'expected_balance',
            'difference',
            'transit_amount',
            'opening_balance',
            'principal_amount',
            'fee_amount',
          }.contains(entry.key)) {
        TreasuryMoney(
          entry.value,
          signed: const {
            'expected_balance',
            'difference',
            'actual_balance',
            'opening_balance',
          }.contains(entry.key),
        );
      }
      validateTreasuryFinancialProjection(entry.value);
    }
  }
}

class TreasuryActor {
  TreasuryActor.fromJson(Map<String, dynamic> json)
    : userId = requireTreasuryId(json['user_id']),
      deviceId = requireTreasuryId(json['device_id']);
  final String userId, deviceId;
  Map<String, dynamic> toJson() => {'user_id': userId, 'device_id': deviceId};
}

class TreasuryAccount {
  TreasuryAccount.fromJson(Map<String, dynamic> json)
    : id = requireTreasuryId(json['id']),
      ledgerContextId = requireTreasuryId(json['ledger_context_id']),
      raw = treasuryObject(immutableTreasury(json)) {
    if (json['version'] is! int ||
        json['version'] < 1 ||
        json['alias'] is! String ||
        json['currency'] != 'PHP' ||
        json['active'] is! bool ||
        json['actions'] is! List ||
        !(json['actions'] as List).every((v) => v is String) ||
        json['balance'] != null && json['balance'] is! Map) {
      throw const FormatException('The account projection is incomplete.');
    }
    final amount = balance?['expected_balance'];
    if (amount != null) TreasuryMoney(amount, signed: true);
    validateTreasuryFinancialProjection(json);
  }
  final String id, ledgerContextId;
  final Map<String, dynamic> raw;
  String get alias => raw['alias'] as String;
  int get version => raw['version'] as int;
  Map<String, dynamic>? get balance => raw['balance'] as Map<String, dynamic>?;
  List<String> get actions => (raw['actions'] as List).cast<String>();
  String get instructions => raw['payment_instructions'] as String? ?? '';
  bool permits(String action) =>
      raw['active'] == true && actions.contains(action);
}

class TreasuryWorkspace {
  TreasuryWorkspace.fromJson(
    Map<String, dynamic> json, {
    required String expectedUserId,
  }) : actor = TreasuryActor.fromJson(treasuryObject(json['actor'])),
       raw = treasuryObject(immutableTreasury(json)) {
    if (json['contract_version'] != 1 ||
        actor.userId != expectedUserId ||
        json['enabled'] is! bool ||
        json['owner_configured'] is! bool ||
        json['blockers'] is! List ||
        json['capabilities'] is! Map ||
        json['accounts'] is! List ||
        json['claims'] is! List) {
      throw const FormatException(
        'Cash and GCash Control is unavailable on this server.',
      );
    }
    accounts = (json['accounts'] as List)
        .map((v) => TreasuryAccount.fromJson(treasuryObject(v)))
        .toList(growable: false);
    validateTreasuryFinancialProjection(json);
    if (accounts.map((a) => a.id).toSet().length != accounts.length) {
      throw const FormatException('The account scope is invalid.');
    }
  }
  final TreasuryActor actor;
  final Map<String, dynamic> raw;
  late final List<TreasuryAccount> accounts;
  bool get writable =>
      raw['enabled'] == true && raw['owner_configured'] == true;
  bool capability(String action) =>
      writable && (raw['capabilities'] as Map)[action] == true;
  List<String> get blockers =>
      (raw['blockers'] as List).map((v) => v.toString()).toList();
  TreasuryAccount? account(String id) =>
      accounts.where((a) => a.id == id).firstOrNull;
  String get authorization => canonicalTreasury({
    'actor': actor.toJson(),
    'accounts': [
      for (final a in accounts)
        {
          'id': a.id,
          'actions': a.actions.toList()..sort(),
          'private': a.balance != null,
          'active': a.raw['active'],
          'ledger_context_id': a.ledgerContextId,
        },
    ],
    'capabilities': raw['capabilities'],
  });
}

class TreasuryPage {
  TreasuryPage.fromJson(
    Map<String, dynamic> json, {
    required int limit,
    required int offset,
  }) : raw = treasuryObject(immutableTreasury(json)) {
    if (json['items'] is! List ||
        json['total_count'] is! int ||
        json['total_count'] < 0 ||
        json['limit'] != limit ||
        json['offset'] != offset ||
        json['has_more'] is! bool ||
        !(json['totals'] == null || json['totals'] is Map)) {
      throw const FormatException(
        'These records are unavailable. Retry the read.',
      );
    }
    items = (json['items'] as List)
        .map((v) => treasuryObject(immutableTreasury(treasuryObject(v))))
        .toList(growable: false);
    validateTreasuryFinancialProjection(json);
    if (items.length > limit ||
        json['has_more'] != (offset + items.length < json['total_count'])) {
      throw const FormatException('The server page is incomplete.');
    }
  }
  final Map<String, dynamic> raw;
  late final List<Map<String, dynamic>> items;
  int get totalCount => raw['total_count'] as int;
  bool get hasMore => raw['has_more'] as bool;
  Map<String, dynamic>? get totals => raw['totals'] as Map<String, dynamic>?;
}

class TreasuryResult {
  TreasuryResult.fromJson(Map<String, dynamic> json)
    : raw = treasuryObject(immutableTreasury(json)) {
    if (json['contract_version'] != 1 ||
        !treasuryUuid(json['request_id']) ||
        !treasuryUuid(json['target_id']) ||
        json['action'] is! String ||
        !['saved', 'blocked'].contains(json['status']) ||
        json['version'] is! int ||
        json['version'] < 1 ||
        json['result'] is! Map) {
      throw const FormatException(
        'The result could not be confirmed. Recover the exact request.',
      );
    }
  }
  final Map<String, dynamic> raw;
  String get status => raw['status'] as String;
  String get targetId => raw['target_id'] as String;
  int get version => raw['version'] as int;
  Map<String, dynamic> get result => raw['result'] as Map<String, dynamic>;
}

const collectorOwnActions = {
  TreasuryAction.collectorSurplusReturnRequest,
  TreasuryAction.collectorSurplusApplicationRequest,
  TreasuryAction.collectorSurplusReturnAcknowledge,
  TreasuryAction.collectorCustodyExceptionReturnAcknowledge,
};
bool isCollectorSurplusAction(TreasuryAction action) =>
    action.code.startsWith('collector_');
String collectorCapability(TreasuryAction action) => switch (action) {
  TreasuryAction.collectorCountRecord => 'count_record',
  TreasuryAction.collectorCountAccept => 'count_accept',
  TreasuryAction.collectorCustodyExceptionRecord => 'exception_record',
  TreasuryAction.collectorCustodyExceptionReturnPrepare =>
    'exception_return_prepare',
  TreasuryAction.collectorCustodyExceptionReturnAcknowledge =>
    'exception_acknowledge',
  _ => action.code.replaceFirst('collector_surplus_', ''),
};

bool isLoanPayoutAction(TreasuryAction action) =>
    action.code.startsWith('loan_payout_');
