import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class CollectorScheduleRow {
  const CollectorScheduleRow({
    required this.kind,
    required this.date,
    required this.status,
    required this.amount,
    required this.contractualAmount,
    required this.paidAmount,
    required this.prepaidAmount,
    required this.remainingAmount,
    required this.installmentId,
    required this.installmentNumber,
    required this.contractualDueDate,
    required this.principalComponent,
    required this.interestComponent,
    required this.principalReductionAmount,
    required this.pastDueReasonCode,
    required this.pastDueReasonNote,
    required this.promisedForDate,
    required this.promiseRemainingAmount,
    required this.promiseStatus,
    required this.noCollectionReason,
  });

  final String kind;
  final DateTime? date;
  final String status;
  final String amount;
  final String contractualAmount;
  final String paidAmount;
  final String prepaidAmount;
  final String remainingAmount;
  final int? installmentId;
  final int? installmentNumber;
  final DateTime? contractualDueDate;
  final String? principalComponent;
  final String? interestComponent;
  final String principalReductionAmount;
  final String? pastDueReasonCode;
  final String? pastDueReasonNote;
  final DateTime? promisedForDate;
  final String promiseRemainingAmount;
  final String? promiseStatus;
  final String? noCollectionReason;

  static CollectorScheduleRow? fromPayload(Object? value) {
    final data = stringMap(value);
    if (data.isEmpty) return null;

    return CollectorScheduleRow(
      kind: firstNonEmptyString(<Object?>[data['kind']]) ?? 'installment',
      date: _date(data['date']),
      status: firstNonEmptyString(<Object?>[data['status']]) ?? 'Scheduled',
      amount: _requiredMoney(data, 'amount'),
      contractualAmount: _requiredMoney(data, 'contractual_amount'),
      paidAmount: _requiredMoney(data, 'paid_amount'),
      prepaidAmount: _requiredMoney(data, 'prepaid_amount'),
      remainingAmount: _requiredMoney(data, 'remaining_amount'),
      installmentId: firstNumber(<Object?>[data['installment_id']])?.toInt(),
      installmentNumber: firstNumber(<Object?>[
        data['installment_number'],
      ])?.toInt(),
      contractualDueDate: _date(data['contractual_due_date']),
      principalComponent: _optionalMoney(data, 'principal_component'),
      interestComponent: _optionalMoney(data, 'interest_component'),
      principalReductionAmount: _requiredMoney(
        data,
        'principal_reduction_amount',
      ),
      pastDueReasonCode: firstNonEmptyString(<Object?>[
        data['past_due_reason_code'],
      ]),
      pastDueReasonNote: firstNonEmptyString(<Object?>[
        data['past_due_reason_note'],
      ]),
      promisedForDate: _date(data['promised_for_date']),
      promiseRemainingAmount: _requiredMoney(data, 'promise_remaining_amount'),
      promiseStatus: firstNonEmptyString(<Object?>[data['promise_status']]),
      noCollectionReason: firstNonEmptyString(<Object?>[
        data['no_collection_reason'],
      ]),
    );
  }
}

class CollectorSchedule {
  const CollectorSchedule({
    required this.loanId,
    required this.loanNumber,
    required this.clientId,
    required this.clientName,
    required this.loanType,
    required this.calculationMode,
    required this.isSevenBySeven,
    required this.scheduleId,
    required this.scheduleVersion,
    required this.paymentFrequency,
    required this.contractReference,
    required this.asOfDate,
    required this.readOnly,
    required this.pastDueAmount,
    required this.pastDueCount,
    required this.scheduleExtensionSlots,
    required this.maturityExtended,
    required this.baseMaturity,
    required this.updatedMaturity,
    required this.maturityProjectionStatus,
    required this.rows,
    this.penaltyStatus = '',
    this.projectedPenalty,
    this.assessedPenaltyBalance,
    this.penaltyBase,
    this.remainingCostHeadroom,
    this.exactPayoffTotal,
    this.managementReviewRequiredReason = '',
  });

  final String loanId;
  final String loanNumber;
  final String clientId;
  final String clientName;
  final String loanType;
  final String calculationMode;
  final bool isSevenBySeven;
  final String scheduleId;
  final int scheduleVersion;
  final String paymentFrequency;
  final String contractReference;
  final DateTime? asOfDate;
  final bool readOnly;
  final String pastDueAmount;
  final int pastDueCount;
  final int scheduleExtensionSlots;
  final bool maturityExtended;
  final DateTime? baseMaturity;
  final DateTime? updatedMaturity;
  final String maturityProjectionStatus;
  final List<CollectorScheduleRow> rows;
  final String penaltyStatus;
  final String? projectedPenalty;
  final String? assessedPenaltyBalance;
  final String? penaltyBase;
  final String? remainingCostHeadroom;
  final String? exactPayoffTotal;
  final String managementReviewRequiredReason;

  static CollectorSchedule fromPayload(Object? value) {
    final data = stringMap(value);
    final rawRows = data['rows'];
    final rows = rawRows is Iterable
        ? rawRows
              .map(CollectorScheduleRow.fromPayload)
              .whereType<CollectorScheduleRow>()
              .toList(growable: false)
        : const <CollectorScheduleRow>[];

    return CollectorSchedule(
      loanId: firstNonEmptyString(<Object?>[data['loan_id']]) ?? '',
      loanNumber: firstNonEmptyString(<Object?>[data['loan_number']]) ?? '',
      clientId: firstNonEmptyString(<Object?>[data['client_id']]) ?? '',
      clientName: firstNonEmptyString(<Object?>[data['client_name']]) ?? '',
      loanType: firstNonEmptyString(<Object?>[data['loan_type']]) ?? 'Loan',
      calculationMode:
          firstNonEmptyString(<Object?>[data['calculation_mode']]) ?? '',
      isSevenBySeven: _boolValue(data['is_7x7']),
      scheduleId: firstNonEmptyString(<Object?>[data['schedule_id']]) ?? '',
      scheduleVersion:
          firstNumber(<Object?>[data['schedule_version']])?.toInt() ?? 0,
      paymentFrequency:
          firstNonEmptyString(<Object?>[data['payment_frequency']]) ?? '',
      contractReference:
          firstNonEmptyString(<Object?>[data['contract_reference']]) ?? '',
      asOfDate: _date(data['as_of_date']),
      readOnly: _boolValue(data['read_only']),
      pastDueAmount: _requiredMoney(data, 'past_due_amount'),
      pastDueCount:
          firstNumber(<Object?>[data['past_due_count']])?.toInt() ?? 0,
      scheduleExtensionSlots:
          firstNumber(<Object?>[data['schedule_extension_slots']])?.toInt() ??
          0,
      maturityExtended: _boolValue(data['maturity_extended']),
      baseMaturity: _date(data['base_maturity']),
      updatedMaturity: _date(data['updated_maturity']),
      maturityProjectionStatus:
          firstNonEmptyString(<Object?>[data['maturity_projection_status']]) ??
          '',
      rows: rows,
      penaltyStatus:
          firstNonEmptyString(<Object?>[data['penalty_status']]) ?? '',
      projectedPenalty: _optionalMoney(data, 'projected_penalty'),
      assessedPenaltyBalance: _optionalMoney(data, 'assessed_penalty_balance'),
      penaltyBase: _optionalMoney(data, 'penalty_base'),
      remainingCostHeadroom: _optionalMoney(data, 'remaining_cost_headroom'),
      exactPayoffTotal: _optionalMoney(data, 'exact_payoff_total'),
      managementReviewRequiredReason:
          firstNonEmptyString(<Object?>[
            data['management_review_required_reason'],
          ]) ??
          '',
    );
  }
}

String _requiredMoney(Map<String, dynamic> payload, String key) {
  final value = _optionalMoney(payload, key);
  if (value == null) {
    throw const SpinaApiException(
      'The server returned incomplete schedule money. Refresh the schedule.',
    );
  }
  return value;
}

String? _optionalMoney(Map<String, dynamic> payload, String key) {
  final value = payload[key];
  if (value == null) return null;
  if (value is! String ||
      !RegExp(r'^\d+(?:\.\d{1,2})?$').hasMatch(value.trim())) {
    throw const SpinaApiException(
      'The server returned invalid schedule money. Refresh the schedule.',
    );
  }
  return value.trim();
}

DateTime? _date(Object? value) {
  final text = firstNonEmptyString(<Object?>[value]);
  return text == null ? null : DateTime.tryParse(text);
}

bool _boolValue(Object? value) {
  if (value is bool) return value;
  final text = value?.toString().trim().toLowerCase();
  return text == 'true' || text == '1' || text == 'yes';
}
