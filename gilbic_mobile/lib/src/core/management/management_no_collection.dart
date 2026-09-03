import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ManagementNoCollectionLoanState {
  const ManagementNoCollectionLoanState({
    required this.loanId,
    required this.loanNumber,
    required this.clientId,
    required this.clientName,
    required this.loanType,
    required this.scheduleId,
    required this.scheduleVersion,
    required this.paymentFrequency,
    required this.contractReference,
    required this.operationalVersion,
    required this.installments,
    required this.activeNoCollection,
  });

  final String loanId;
  final String loanNumber;
  final String clientId;
  final String clientName;
  final String loanType;
  final String scheduleId;
  final int scheduleVersion;
  final String paymentFrequency;
  final String contractReference;
  final int operationalVersion;
  final List<ManagementNoCollectionInstallment> installments;
  final List<ManagementNoCollectionActiveAdjustment> activeNoCollection;

  factory ManagementNoCollectionLoanState.fromPayload(Object? value) {
    final payload = stringMap(value);
    final rawInstallments = payload['installments'];
    final rawActive = payload['active_no_collection'];
    if (rawInstallments is! Iterable || rawActive is! Iterable) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete No Collection schedule data.',
        code: 'invalid_no_collection_state',
      );
    }
    return ManagementNoCollectionLoanState(
      loanId: _requiredString(payload, 'loan_id'),
      loanNumber: _requiredString(payload, 'loan_number'),
      clientId: _requiredString(payload, 'client_id'),
      clientName: _requiredString(payload, 'client_name'),
      loanType: _requiredString(payload, 'loan_type'),
      scheduleId: _requiredString(payload, 'schedule_id'),
      scheduleVersion: _requiredInt(payload, 'schedule_version'),
      paymentFrequency: _requiredString(payload, 'payment_frequency'),
      contractReference: _requiredString(payload, 'contract_reference'),
      operationalVersion: _requiredInt(payload, 'operational_version'),
      installments: rawInstallments
          .map(ManagementNoCollectionInstallment.fromPayload)
          .toList(growable: false),
      activeNoCollection: rawActive
          .map(ManagementNoCollectionActiveAdjustment.fromPayload)
          .toList(growable: false),
    );
  }
}

class ManagementNoCollectionInstallment {
  const ManagementNoCollectionInstallment({
    required this.installmentId,
    required this.installmentNumber,
    required this.contractualDueDate,
    required this.effectiveDueDate,
    required this.contractualAmount,
    required this.allocatedAmount,
    required this.remainingAmount,
    required this.isPaid,
    required this.isPartlyPaid,
    this.lastAdjustmentId,
  });

  final int installmentId;
  final int installmentNumber;
  final DateTime contractualDueDate;
  final DateTime effectiveDueDate;
  final double contractualAmount;
  final double allocatedAmount;
  final double remainingAmount;
  final bool isPaid;
  final bool isPartlyPaid;
  final String? lastAdjustmentId;

  bool get isShifted => !_sameDate(contractualDueDate, effectiveDueDate);

  factory ManagementNoCollectionInstallment.fromPayload(Object? value) {
    final payload = stringMap(value);
    return ManagementNoCollectionInstallment(
      installmentId: _requiredInt(payload, 'installment_id'),
      installmentNumber: _requiredInt(payload, 'installment_number'),
      contractualDueDate: _requiredDate(payload, 'contractual_due_date'),
      effectiveDueDate: _requiredDate(payload, 'effective_due_date'),
      contractualAmount: _requiredDouble(payload, 'contractual_amount'),
      allocatedAmount: _requiredDouble(payload, 'allocated_amount'),
      remainingAmount: _requiredDouble(payload, 'remaining_amount'),
      isPaid: payload['is_paid'] == true,
      isPartlyPaid: payload['is_partly_paid'] == true,
      lastAdjustmentId: _optionalString(payload['last_adjustment_id']),
    );
  }
}

class ManagementNoCollectionActiveAdjustment {
  const ManagementNoCollectionActiveAdjustment({
    required this.adjustmentId,
    required this.noCollectionDate,
    required this.reason,
    required this.resultingOperationalVersion,
    required this.actorName,
    required this.createdAt,
  });

  final String adjustmentId;
  final DateTime noCollectionDate;
  final String reason;
  final int resultingOperationalVersion;
  final String actorName;
  final DateTime createdAt;

  factory ManagementNoCollectionActiveAdjustment.fromPayload(Object? value) {
    final payload = stringMap(value);
    return ManagementNoCollectionActiveAdjustment(
      adjustmentId: _requiredString(payload, 'adjustment_id'),
      noCollectionDate: _requiredDate(payload, 'no_collection_date'),
      reason: _requiredString(payload, 'reason'),
      resultingOperationalVersion:
          _requiredInt(payload, 'resulting_operational_version'),
      actorName: _requiredString(payload, 'actor_name'),
      createdAt: _requiredDateTime(payload, 'created_at'),
    );
  }
}

class ManagementNoCollectionShift {
  const ManagementNoCollectionShift({
    required this.installmentId,
    required this.installmentNumber,
    required this.contractualDueDate,
    required this.priorEffectiveDueDate,
    required this.newEffectiveDueDate,
    required this.contractualAmount,
  });

  final int installmentId;
  final int installmentNumber;
  final DateTime contractualDueDate;
  final DateTime priorEffectiveDueDate;
  final DateTime newEffectiveDueDate;
  final double contractualAmount;

  factory ManagementNoCollectionShift.fromPayload(Object? value) {
    final payload = stringMap(value);
    return ManagementNoCollectionShift(
      installmentId: _requiredInt(payload, 'installment_id'),
      installmentNumber: _requiredInt(payload, 'installment_number'),
      contractualDueDate: _requiredDate(payload, 'contractual_due_date'),
      priorEffectiveDueDate: _requiredDate(payload, 'prior_effective_due_date'),
      newEffectiveDueDate: _requiredDate(payload, 'new_effective_due_date'),
      contractualAmount: _requiredDouble(payload, 'contractual_amount'),
    );
  }
}

class ManagementNoCollectionAdjustmentResult {
  const ManagementNoCollectionAdjustmentResult({
    required this.adjustmentId,
    required this.loanId,
    required this.scheduleId,
    required this.scheduleVersion,
    required this.paymentFrequency,
    required this.adjustmentType,
    required this.noCollectionDate,
    required this.reason,
    required this.expectedOperationalVersion,
    required this.resultingOperationalVersion,
    required this.createdAt,
    required this.shifts,
    this.reversesAdjustmentId,
  });

  final String adjustmentId;
  final String loanId;
  final String scheduleId;
  final int scheduleVersion;
  final String paymentFrequency;
  final String adjustmentType;
  final DateTime noCollectionDate;
  final String reason;
  final int expectedOperationalVersion;
  final int resultingOperationalVersion;
  final String? reversesAdjustmentId;
  final DateTime createdAt;
  final List<ManagementNoCollectionShift> shifts;

  factory ManagementNoCollectionAdjustmentResult.fromPayload(Object? value) {
    final payload = stringMap(value);
    final rawShifts = payload['shifts'];
    if (rawShifts is! Iterable) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete No Collection adjustment data.',
        code: 'invalid_no_collection_result',
      );
    }
    return ManagementNoCollectionAdjustmentResult(
      adjustmentId: _requiredString(payload, 'adjustment_id'),
      loanId: _requiredString(payload, 'loan_id'),
      scheduleId: _requiredString(payload, 'schedule_id'),
      scheduleVersion: _requiredInt(payload, 'schedule_version'),
      paymentFrequency: _requiredString(payload, 'payment_frequency'),
      adjustmentType: _requiredString(payload, 'adjustment_type'),
      noCollectionDate: _requiredDate(payload, 'no_collection_date'),
      reason: _requiredString(payload, 'reason'),
      expectedOperationalVersion:
          _requiredInt(payload, 'expected_operational_version'),
      resultingOperationalVersion:
          _requiredInt(payload, 'resulting_operational_version'),
      reversesAdjustmentId:
          _optionalString(payload['reverses_adjustment_id']),
      createdAt: _requiredDateTime(payload, 'created_at'),
      shifts: rawShifts
          .map(ManagementNoCollectionShift.fromPayload)
          .toList(growable: false),
    );
  }
}

String _requiredString(Map<String, dynamic> payload, String key) {
  final value = _optionalString(payload[key]);
  if (value == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_no_collection_payload',
    );
  }
  return value;
}

String? _optionalString(Object? value) {
  final text = value?.toString().trim() ?? '';
  return text.isEmpty ? null : text;
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
      code: 'invalid_no_collection_payload',
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
      code: 'invalid_no_collection_payload',
    );
  }
  return parsed;
}

DateTime _requiredDate(Map<String, dynamic> payload, String key) {
  final parsed = DateTime.tryParse(payload[key]?.toString() ?? '');
  if (parsed == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_no_collection_payload',
    );
  }
  return DateTime(parsed.year, parsed.month, parsed.day);
}

DateTime _requiredDateTime(Map<String, dynamic> payload, String key) {
  final parsed = DateTime.tryParse(payload[key]?.toString() ?? '');
  if (parsed == null) {
    throw SpinaApiException(
      'The SPINA server omitted $key.',
      code: 'invalid_no_collection_payload',
    );
  }
  return parsed;
}

bool _sameDate(DateTime first, DateTime second) =>
    first.year == second.year &&
    first.month == second.month &&
    first.day == second.day;
