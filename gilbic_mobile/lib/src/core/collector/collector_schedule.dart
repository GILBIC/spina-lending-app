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
  final double amount;
  final double contractualAmount;
  final double paidAmount;
  final double prepaidAmount;
  final double remainingAmount;
  final int? installmentId;
  final int? installmentNumber;
  final DateTime? contractualDueDate;
  final double? principalComponent;
  final double? interestComponent;
  final double principalReductionAmount;
  final String? pastDueReasonCode;
  final String? pastDueReasonNote;
  final DateTime? promisedForDate;
  final double promiseRemainingAmount;
  final String? promiseStatus;
  final String? noCollectionReason;

  static CollectorScheduleRow? fromPayload(Object? value) {
    final data = stringMap(value);
    if (data.isEmpty) return null;

    return CollectorScheduleRow(
      kind: firstNonEmptyString(<Object?>[data['kind']]) ?? 'installment',
      date: _date(data['date']),
      status: firstNonEmptyString(<Object?>[data['status']]) ?? 'Scheduled',
      amount: firstNumber(<Object?>[data['amount']])?.toDouble() ?? 0,
      contractualAmount:
          firstNumber(<Object?>[data['contractual_amount']])?.toDouble() ?? 0,
      paidAmount:
          firstNumber(<Object?>[data['paid_amount']])?.toDouble() ?? 0,
      prepaidAmount:
          firstNumber(<Object?>[data['prepaid_amount']])?.toDouble() ?? 0,
      remainingAmount:
          firstNumber(<Object?>[data['remaining_amount']])?.toDouble() ?? 0,
      installmentId:
          firstNumber(<Object?>[data['installment_id']])?.toInt(),
      installmentNumber:
          firstNumber(<Object?>[data['installment_number']])?.toInt(),
      contractualDueDate: _date(data['contractual_due_date']),
      principalComponent:
          firstNumber(<Object?>[data['principal_component']])?.toDouble(),
      interestComponent:
          firstNumber(<Object?>[data['interest_component']])?.toDouble(),
      principalReductionAmount:
          firstNumber(<Object?>[data['principal_reduction_amount']])
                  ?.toDouble() ??
              0,
      pastDueReasonCode:
          firstNonEmptyString(<Object?>[data['past_due_reason_code']]),
      pastDueReasonNote:
          firstNonEmptyString(<Object?>[data['past_due_reason_note']]),
      promisedForDate: _date(data['promised_for_date']),
      promiseRemainingAmount:
          firstNumber(<Object?>[data['promise_remaining_amount']])
                  ?.toDouble() ??
              0,
      promiseStatus:
          firstNonEmptyString(<Object?>[data['promise_status']]),
      noCollectionReason:
          firstNonEmptyString(<Object?>[data['no_collection_reason']]),
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
  final double pastDueAmount;
  final int pastDueCount;
  final int scheduleExtensionSlots;
  final bool maturityExtended;
  final DateTime? baseMaturity;
  final DateTime? updatedMaturity;
  final String maturityProjectionStatus;
  final List<CollectorScheduleRow> rows;

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
      pastDueAmount:
          firstNumber(<Object?>[data['past_due_amount']])?.toDouble() ?? 0,
      pastDueCount:
          firstNumber(<Object?>[data['past_due_count']])?.toInt() ?? 0,
      scheduleExtensionSlots:
          firstNumber(<Object?>[data['schedule_extension_slots']])?.toInt() ?? 0,
      maturityExtended: _boolValue(data['maturity_extended']),
      baseMaturity: _date(data['base_maturity']),
      updatedMaturity: _date(data['updated_maturity']),
      maturityProjectionStatus:
          firstNonEmptyString(<Object?>[data['maturity_projection_status']]) ?? '',
      rows: rows,
    );
  }
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
