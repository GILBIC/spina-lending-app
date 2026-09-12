import 'package:gilbic_mobile/src/core/loans/client_loan.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ClientLoanSchedule {
  const ClientLoanSchedule({
    required this.loanId,
    required this.loanNumber,
    required this.loanType,
    required this.calculationMode,
    required this.isSevenBySeven,
    required this.paymentFrequency,
    required this.readOnly,
    required this.pastDueAmount,
    required this.pastDueCount,
    required this.scheduleExtensionSlots,
    required this.maturityStatus,
    required this.rows,
    this.contractualMaturity,
    this.operationalMaturity,
  });

  final String loanId;
  final String loanNumber;
  final String loanType;
  final String calculationMode;
  final bool isSevenBySeven;
  final String paymentFrequency;
  final bool readOnly;
  final double pastDueAmount;
  final int pastDueCount;
  final int scheduleExtensionSlots;
  final DateTime? contractualMaturity;
  final DateTime? operationalMaturity;
  final String maturityStatus;
  final List<ClientScheduleRow> rows;

  factory ClientLoanSchedule.fromPayload(Map<String, dynamic> payload) {
    final rawRows = payload['rows'];
    if (payload.isEmpty || rawRows is! List) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete schedule data.',
        code: 'invalid_client_schedule_payload',
      );
    }
    return ClientLoanSchedule(
      loanId: requiredString(payload, 'loan_id'),
      loanNumber: requiredString(payload, 'loan_number'),
      loanType: requiredString(payload, 'loan_type'),
      calculationMode: requiredString(payload, 'calculation_mode'),
      isSevenBySeven: payload['is_7x7'] == true,
      paymentFrequency: requiredString(payload, 'payment_frequency'),
      readOnly: payload['read_only'] == true,
      pastDueAmount: requiredDouble(payload, 'past_due_amount'),
      pastDueCount: requiredInt(payload, 'past_due_count'),
      scheduleExtensionSlots: requiredInt(payload, 'schedule_extension_slots'),
      contractualMaturity: optionalDate(payload['contractual_maturity']),
      operationalMaturity: optionalDate(payload['operational_maturity']),
      maturityStatus: requiredString(payload, 'maturity_status'),
      rows: rawRows
          .map((row) => ClientScheduleRow.fromPayload(stringMap(row)))
          .toList(growable: false),
    );
  }
}

class ClientScheduleRow {
  const ClientScheduleRow({
    required this.paymentDate,
    required this.amount,
    required this.status,
    required this.remainingAmount,
    this.note,
  });

  final DateTime paymentDate;
  final double amount;
  final String status;
  final double remainingAmount;
  final String? note;

  factory ClientScheduleRow.fromPayload(Map<String, dynamic> payload) {
    final details = stringMap(payload['details']);
    final paymentDate = optionalDate(payload['payment_date']);
    if (paymentDate == null) {
      throw const SpinaApiException(
        'The SPINA server returned an invalid schedule date.',
        code: 'invalid_client_schedule_payload',
      );
    }
    return ClientScheduleRow(
      paymentDate: paymentDate,
      amount: requiredDouble(payload, 'amount'),
      status: requiredString(payload, 'status'),
      remainingAmount: requiredDouble(details, 'remaining_amount'),
      note: optionalString(details['note']),
    );
  }
}
