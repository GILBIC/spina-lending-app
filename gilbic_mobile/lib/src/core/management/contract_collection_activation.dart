class ContractCollectionActivationData {
  const ContractCollectionActivationData({
    required this.permission,
    required this.activeCount,
    required this.readyToActivateCount,
    required this.notice,
    required this.loans,
  });

  final bool permission;
  final int activeCount;
  final int readyToActivateCount;
  final String notice;
  final List<ContractCollectionActivationLoan> loans;

  factory ContractCollectionActivationData.fromPayload(
    Map<String, dynamic> payload,
  ) {
    final rawLoans = payload['loans'];
    return ContractCollectionActivationData(
      permission: payload['permission'] == true,
      activeCount: _intValue(payload['active_count']),
      readyToActivateCount: _intValue(payload['ready_to_activate_count']),
      notice: _stringValue(payload['notice']),
      loans: rawLoans is List
          ? rawLoans
              .whereType<Map>()
              .map(
                (row) => ContractCollectionActivationLoan.fromPayload(
                  row.map((key, value) => MapEntry('$key', value)),
                ),
              )
              .toList(growable: false)
          : const <ContractCollectionActivationLoan>[],
    );
  }
}

class ContractCollectionActivationLoan {
  const ContractCollectionActivationLoan({
    required this.loanId,
    required this.loanNumber,
    required this.clientName,
    required this.loanTypeName,
    required this.loanStatus,
    required this.remainingBalance,
    required this.mobileCollectionsEnabled,
    required this.mobileBalanceMode,
    required this.scheduleId,
    required this.scheduleVersion,
    required this.paymentFrequency,
    required this.contractReference,
    required this.dpdDataStatus,
    required this.contractualScheduleTotal,
    required this.allocatedScheduleTotal,
    required this.unpaidContractualAmount,
    required this.scheduleVerified,
    required this.balanceReconciled,
    required this.accountingSafe,
    required this.activationEventId,
    required this.activationAction,
    required this.activationScheduleId,
    required this.activationNote,
    required this.activationActedAt,
    required this.isActive,
    required this.activeForCurrentSchedule,
    required this.canActivate,
    required this.canDeactivate,
    required this.blockers,
  });

  final String loanId;
  final String loanNumber;
  final String clientName;
  final String loanTypeName;
  final String loanStatus;
  final double remainingBalance;
  final bool mobileCollectionsEnabled;
  final String mobileBalanceMode;
  final String? scheduleId;
  final int? scheduleVersion;
  final String paymentFrequency;
  final String contractReference;
  final String dpdDataStatus;
  final double contractualScheduleTotal;
  final double allocatedScheduleTotal;
  final double unpaidContractualAmount;
  final bool scheduleVerified;
  final bool balanceReconciled;
  final bool accountingSafe;
  final int? activationEventId;
  final String activationAction;
  final String? activationScheduleId;
  final String activationNote;
  final DateTime? activationActedAt;
  final bool isActive;
  final bool activeForCurrentSchedule;
  final bool canActivate;
  final bool canDeactivate;
  final List<String> blockers;

  String get readinessLabel {
    if (activeForCurrentSchedule) return 'Active';
    if (isActive) return 'Needs deactivation';
    if (canActivate) return 'Ready to activate';
    if (!scheduleVerified) return 'Needs signed contract';
    if (!balanceReconciled) return 'Needs reconciliation';
    return 'Not ready';
  }

  factory ContractCollectionActivationLoan.fromPayload(
    Map<String, dynamic> payload,
  ) {
    final rawBlockers = payload['blockers'];
    return ContractCollectionActivationLoan(
      loanId: _stringValue(payload['loan_id']),
      loanNumber: _stringValue(payload['loan_number']),
      clientName: _stringValue(payload['client_name']),
      loanTypeName: _stringValue(payload['loan_type_name']),
      loanStatus: _stringValue(payload['loan_status']),
      remainingBalance: _doubleValue(payload['remaining_balance']),
      mobileCollectionsEnabled: payload['mobile_collections_enabled'] == true,
      mobileBalanceMode: _stringValue(payload['mobile_balance_mode']),
      scheduleId: _nullableString(payload['schedule_id']),
      scheduleVersion: _nullableInt(payload['schedule_version']),
      paymentFrequency: _stringValue(payload['payment_frequency']),
      contractReference: _stringValue(payload['contract_reference']),
      dpdDataStatus: _stringValue(payload['dpd_data_status']),
      contractualScheduleTotal: _doubleValue(payload['contractual_schedule_total']),
      allocatedScheduleTotal: _doubleValue(payload['allocated_schedule_total']),
      unpaidContractualAmount: _doubleValue(payload['unpaid_contractual_amount']),
      scheduleVerified: payload['schedule_verified'] == true,
      balanceReconciled: payload['balance_reconciled'] == true,
      accountingSafe: payload['accounting_safe'] == true,
      activationEventId: _nullableInt(payload['activation_event_id']),
      activationAction: _stringValue(payload['activation_action']),
      activationScheduleId: _nullableString(payload['activation_schedule_id']),
      activationNote: _stringValue(payload['activation_note']),
      activationActedAt: _dateTimeValue(payload['activation_acted_at']),
      isActive: payload['is_active'] == true,
      activeForCurrentSchedule: payload['active_for_current_schedule'] == true,
      canActivate: payload['can_activate'] == true,
      canDeactivate: payload['can_deactivate'] == true,
      blockers: rawBlockers is List
          ? rawBlockers.map((value) => '$value').toList(growable: false)
          : const <String>[],
    );
  }
}

String _stringValue(Object? value) => value == null ? '' : '$value';

String? _nullableString(Object? value) {
  final text = _stringValue(value).trim();
  return text.isEmpty ? null : text;
}

int _intValue(Object? value) {
  if (value is int) return value;
  return int.tryParse(_stringValue(value)) ?? 0;
}

int? _nullableInt(Object? value) {
  if (value == null) return null;
  if (value is int) return value;
  return int.tryParse(_stringValue(value));
}

double _doubleValue(Object? value) {
  if (value is num) return value.toDouble();
  return double.tryParse(_stringValue(value)) ?? 0;
}

DateTime? _dateTimeValue(Object? value) {
  final text = _stringValue(value).trim();
  return text.isEmpty ? null : DateTime.tryParse(text);
}
