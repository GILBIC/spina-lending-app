import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class CollectorRoute {
  const CollectorRoute({
    required this.routeDate,
    required this.collectorName,
    required this.areas,
    required this.entries,
    required this.expectedTotal,
  });

  final DateTime? routeDate;
  final String collectorName;
  final List<String> areas;
  final List<CollectorRouteEntry> entries;
  final double expectedTotal;

  Map<String, Object?> toJson() {
    return <String, Object?>{
      'route_date': routeDate?.toIso8601String(),
      'collector_name': collectorName,
      'areas': areas,
      'expected_total': expectedTotal,
      'entries': entries
          .map((entry) => entry.toJson())
          .toList(growable: false),
    };
  }

  static CollectorRoute fromPayload(Object? value) {
    final outer = stringMap(value);
    final route = stringMap(outer['route']);
    final source = route.isEmpty ? outer : route;
    final rawEntries = source['entries'] ??
        source['clients'] ??
        source['items'] ??
        outer['route_entries'] ??
        outer['clients'];
    final entries = rawEntries is Iterable
        ? rawEntries
            .map(CollectorRouteEntry.fromPayload)
            .whereType<CollectorRouteEntry>()
            .toList(growable: false)
        : const <CollectorRouteEntry>[];

    final rawAreas = stringList(source['areas'] ?? outer['areas']);
    final derivedAreas = entries
        .map((entry) => entry.area)
        .where((area) => area.isNotEmpty)
        .toSet()
        .toList(growable: false);
    final expected = firstNumber(<Object?>[
      source['expected_total'],
      source['total_expected'],
      source['expected_amount'],
      outer['expected_total'],
    ]);

    return CollectorRoute(
      routeDate: DateTime.tryParse(
        firstNonEmptyString(<Object?>[
              source['route_date'],
              source['date'],
              outer['route_date'],
              outer['date'],
            ]) ??
            '',
      ),
      collectorName: firstNonEmptyString(<Object?>[
            source['collector_name'],
            source['collector'],
            outer['collector_name'],
            outer['collector'],
          ]) ??
          'Collector',
      areas: rawAreas.isEmpty ? derivedAreas : rawAreas,
      entries: entries,
      expectedTotal: expected?.toDouble() ??
          entries.fold<double>(
            0,
            (total, entry) => total + entry.dailyAmount,
          ),
    );
  }
}

class CollectorRouteReceipt {
  const CollectorRouteReceipt({
    required this.transactionId,
    required this.receiptNumber,
    required this.amount,
    required this.entryType,
    required this.collectorUserId,
    required this.collectorName,
    required this.isLocked,
    this.note = '',
    this.coveredDates = const <DateTime>[],
    this.acceptedAt,
  });

  final String transactionId;
  final String receiptNumber;
  final double amount;
  final String entryType;
  final String collectorUserId;
  final String collectorName;
  final bool isLocked;
  final String note;
  final List<DateTime> coveredDates;
  final DateTime? acceptedAt;

  Map<String, Object?> toJson() {
    return <String, Object?>{
      'transaction_id': transactionId,
      'receipt_number': receiptNumber,
      'amount': amount,
      'entry_type': entryType,
      'collector_user_id': collectorUserId,
      'collector_name': collectorName,
      'is_locked': isLocked,
      'note': note,
      'covered_dates': coveredDates
          .map((value) => value.toIso8601String())
          .toList(growable: false),
      'accepted_at': acceptedAt?.toIso8601String(),
    };
  }

  static CollectorRouteReceipt? fromPayload(Object? value) {
    final data = stringMap(value);
    if (data.isEmpty) {
      return null;
    }
    final transactionId = firstNonEmptyString(<Object?>[
      data['transaction_id'],
      data['id'],
    ]);
    final receiptNumber = firstNonEmptyString(<Object?>[
      data['receipt_number'],
      data['receipt'],
    ]);
    if (transactionId == null || receiptNumber == null) {
      return null;
    }
    return CollectorRouteReceipt(
      transactionId: transactionId,
      receiptNumber: receiptNumber,
      amount: firstNumber(<Object?>[data['amount']])?.toDouble() ?? 0,
      entryType: firstNonEmptyString(<Object?>[data['entry_type']]) ?? 'payment',
      collectorUserId:
          firstNonEmptyString(<Object?>[data['collector_user_id']]) ?? '',
      collectorName: firstNonEmptyString(<Object?>[
            data['collector_name'],
            data['recorded_by'],
          ]) ??
          'Collector',
      isLocked: _boolValue(data['is_locked'], fallback: false),
      note: firstNonEmptyString(<Object?>[data['note']]) ?? '',
      coveredDates: _dateList(data['covered_dates']),
      acceptedAt: DateTime.tryParse(
        firstNonEmptyString(<Object?>[data['accepted_at']]) ?? '',
      ),
    );
  }
}

class CollectorRouteEntry {
  const CollectorRouteEntry({
    required this.id,
    required this.clientId,
    required this.loanId,
    required this.clientName,
    required this.area,
    required this.loanType,
    required this.dailyAmount,
    required this.balance,
    required this.status,
    required this.passCount,
    this.lastPaymentDate,
    this.advanceUntil,
    this.coveredDates = const <DateTime>[],
    this.note = '',
    this.routeRevision,
    this.canCollectMobile = true,
    this.canEnterPayment = true,
    this.sevenBySevenMobileEnabled = false,
    this.collectionMessage = '',
    this.contractAllocationEnabled = false,
    this.contractScheduleVerified = false,
    this.contractDpdStatus = 'contract_schedule_required',
    this.contractPaymentFrequency = '',
    this.contractReference = '',
    this.contractScheduleVersion,
    this.contractGraceDays = 0,
    this.contractBalanceReconciled = false,
    this.contractScheduleReady = false,
    this.contractCollectionReady = false,
    this.contractDaysPastDue,
    this.contractTodayScheduledAmount = 0,
    this.contractTodayUnpaidAmount = 0,
    this.contractTodayAlreadyCovered = false,
    this.contractNextUnpaidDate,
    this.contractNextUnpaidAmount = 0,
    this.contractReadinessMessage = '',
    this.processedToday = false,
    this.todayEntryType = '',
    this.todayCollectorName = '',
    this.todayTransactionId,
    this.todayIsLocked = false,
    this.canEditToday = false,
    this.todayAmount = 0,
    this.todayNote = '',
    this.todayCoveredDates = const <DateTime>[],
    this.todayReceipts = const <CollectorRouteReceipt>[],
  });

  final String id;
  final String clientId;
  final String loanId;
  final String clientName;
  final String area;
  final String loanType;
  final double dailyAmount;
  final double balance;
  final String status;
  final int passCount;
  final DateTime? lastPaymentDate;
  final DateTime? advanceUntil;
  final List<DateTime> coveredDates;
  final String note;
  final String? routeRevision;
  final bool canCollectMobile;
  final bool canEnterPayment;
  final bool sevenBySevenMobileEnabled;
  final String collectionMessage;
  final bool contractAllocationEnabled;
  final bool contractScheduleVerified;
  final String contractDpdStatus;
  final String contractPaymentFrequency;
  final String contractReference;
  final int? contractScheduleVersion;
  final int contractGraceDays;
  final bool contractBalanceReconciled;
  final bool contractScheduleReady;
  final bool contractCollectionReady;
  final int? contractDaysPastDue;
  final double contractTodayScheduledAmount;
  final double contractTodayUnpaidAmount;
  final bool contractTodayAlreadyCovered;
  final DateTime? contractNextUnpaidDate;
  final double contractNextUnpaidAmount;
  final String contractReadinessMessage;
  final bool processedToday;
  final String todayEntryType;
  final String todayCollectorName;
  final String? todayTransactionId;
  final bool todayIsLocked;
  final bool canEditToday;
  final double todayAmount;
  final String todayNote;
  final List<DateTime> todayCoveredDates;
  final List<CollectorRouteReceipt> todayReceipts;

  Map<String, Object?> toJson() {
    return <String, Object?>{
      'id': id,
      'client_id': clientId,
      'loan_id': loanId,
      'client_name': clientName,
      'area': area,
      'loan_type': loanType,
      'daily_amount': dailyAmount,
      'balance': balance,
      'status': status,
      'pass_count': passCount,
      'last_payment_date': lastPaymentDate?.toIso8601String(),
      'advance_until': advanceUntil?.toIso8601String(),
      'covered_dates': coveredDates
          .map((value) => value.toIso8601String())
          .toList(growable: false),
      'note': note,
      'route_revision': routeRevision,
      'can_collect_mobile': canCollectMobile,
      'can_enter_payment': canEnterPayment,
      'seven_by_seven_mobile_enabled': sevenBySevenMobileEnabled,
      'collection_message': collectionMessage,
      'contract_allocation_enabled': contractAllocationEnabled,
      'contract_schedule_verified': contractScheduleVerified,
      'contract_dpd_status': contractDpdStatus,
      'contract_payment_frequency': contractPaymentFrequency,
      'contract_reference': contractReference,
      'contract_schedule_version': contractScheduleVersion,
      'contract_grace_days': contractGraceDays,
      'contract_balance_reconciled': contractBalanceReconciled,
      'contract_schedule_ready': contractScheduleReady,
      'contract_collection_ready': contractCollectionReady,
      'contract_days_past_due': contractDaysPastDue,
      'contract_today_scheduled_amount': contractTodayScheduledAmount,
      'contract_today_unpaid_amount': contractTodayUnpaidAmount,
      'contract_today_already_covered': contractTodayAlreadyCovered,
      'contract_next_unpaid_date': contractNextUnpaidDate?.toIso8601String(),
      'contract_next_unpaid_amount': contractNextUnpaidAmount,
      'contract_readiness_message': contractReadinessMessage,
      'processed_today': processedToday,
      'today_entry_type': todayEntryType,
      'today_collector_name': todayCollectorName,
      'today_transaction_id': todayTransactionId,
      'today_is_locked': todayIsLocked,
      'can_edit_today': canEditToday,
      'today_amount': todayAmount,
      'today_note': todayNote,
      'today_covered_dates': todayCoveredDates
          .map((value) => value.toIso8601String())
          .toList(growable: false),
      'today_receipts': todayReceipts
          .map((receipt) => receipt.toJson())
          .toList(growable: false),
    };
  }

  static CollectorRouteEntry? fromPayload(Object? value) {
    final data = stringMap(value);
    if (data.isEmpty) {
      return null;
    }
    final client = stringMap(data['client']);
    final loan = stringMap(data['loan']);
    final clientName = firstNonEmptyString(<Object?>[
      data['client_name'],
      data['full_name'],
      data['name'],
      client['full_name'],
      client['name'],
    ]);
    if (clientName == null) {
      return null;
    }

    final clientId = firstNonEmptyString(<Object?>[
          data['client_id'],
          data['client_uid'],
          client['id'],
          client['client_id'],
        ]) ??
        clientName;
    final loanId = firstNonEmptyString(<Object?>[
          data['loan_id'],
          data['loan_uid'],
          loan['id'],
          loan['loan_id'],
        ]) ??
        '';
    final id = firstNonEmptyString(<Object?>[
          data['id'],
          data['route_entry_id'],
          data['entry_id'],
        ]) ??
        '$clientId:$loanId';

    return CollectorRouteEntry(
      id: id,
      clientId: clientId,
      loanId: loanId,
      clientName: clientName,
      area: firstNonEmptyString(<Object?>[
            data['area'],
            data['client_area'],
            client['area'],
          ]) ??
          '',
      loanType: firstNonEmptyString(<Object?>[
            data['loan_type'],
            loan['loan_type'],
            loan['type'],
          ]) ??
          'Loan',
      dailyAmount: firstNumber(<Object?>[
            data['daily_amount'],
            data['payment_amount'],
            data['amount_due'],
            loan['daily_amount'],
            loan['payment_amount'],
          ])?.toDouble() ??
          0,
      balance: firstNumber(<Object?>[
            data['balance'],
            data['remaining_balance'],
            data['loan_balance'],
            loan['balance'],
            loan['remaining_balance'],
          ])?.toDouble() ??
          0,
      status: firstNonEmptyString(<Object?>[
            data['collection_status'],
            data['status'],
          ]) ??
          'Pending',
      passCount: firstNumber(<Object?>[
            data['pass_count'],
            data['passes'],
          ])?.toInt() ??
          0,
      lastPaymentDate: DateTime.tryParse(
        firstNonEmptyString(<Object?>[
              data['last_payment_date'],
              data['last_paid_at'],
            ]) ??
            '',
      ),
      advanceUntil: DateTime.tryParse(
        firstNonEmptyString(<Object?>[
              data['advance_until'],
              data['adv_until'],
              data['advance_covered_until'],
            ]) ??
            '',
      ),
      coveredDates: _dateList(data['covered_dates']),
      note: firstNonEmptyString(<Object?>[
            data['note'],
            data['route_note'],
            data['tomorrow_note'],
          ]) ??
          '',
      routeRevision: firstNonEmptyString(<Object?>[
        data['route_revision'],
        loan['route_revision'],
      ]),
      canCollectMobile: _boolValue(
        data['can_collect_mobile'],
        fallback: true,
      ),
      canEnterPayment: _boolValue(
        data['can_enter_payment'],
        fallback: true,
      ),
      sevenBySevenMobileEnabled: _boolValue(
        data['seven_by_seven_mobile_enabled'],
        fallback: false,
      ),
      collectionMessage: firstNonEmptyString(<Object?>[
            data['collection_message'],
            data['status_message'],
          ]) ??
          '',
      contractAllocationEnabled: _boolValue(
        data['contract_allocation_enabled'],
        fallback: false,
      ),
      contractScheduleVerified: _boolValue(
        data['contract_schedule_verified'],
        fallback: false,
      ),
      contractDpdStatus: firstNonEmptyString(<Object?>[
            data['contract_dpd_status'],
          ]) ??
          'contract_schedule_required',
      contractPaymentFrequency: firstNonEmptyString(<Object?>[
            data['contract_payment_frequency'],
          ]) ??
          '',
      contractReference: firstNonEmptyString(<Object?>[
            data['contract_reference'],
          ]) ??
          '',
      contractScheduleVersion: firstNumber(<Object?>[
        data['contract_schedule_version'],
      ])?.toInt(),
      contractGraceDays: firstNumber(<Object?>[
            data['contract_grace_days'],
          ])?.toInt() ??
          0,
      contractBalanceReconciled: _boolValue(
        data['contract_balance_reconciled'],
        fallback: false,
      ),
      contractScheduleReady: _boolValue(
        data['contract_schedule_ready'],
        fallback: false,
      ),
      contractCollectionReady: _boolValue(
        data['contract_collection_ready'],
        fallback: false,
      ),
      contractDaysPastDue: firstNumber(<Object?>[
        data['contract_days_past_due'],
      ])?.toInt(),
      contractTodayScheduledAmount: firstNumber(<Object?>[
            data['contract_today_scheduled_amount'],
          ])?.toDouble() ??
          0,
      contractTodayUnpaidAmount: firstNumber(<Object?>[
            data['contract_today_unpaid_amount'],
          ])?.toDouble() ??
          0,
      contractTodayAlreadyCovered: _boolValue(
        data['contract_today_already_covered'],
        fallback: false,
      ),
      contractNextUnpaidDate: DateTime.tryParse(
        firstNonEmptyString(<Object?>[
              data['contract_next_unpaid_date'],
            ]) ??
            '',
      ),
      contractNextUnpaidAmount: firstNumber(<Object?>[
            data['contract_next_unpaid_amount'],
          ])?.toDouble() ??
          0,
      contractReadinessMessage: firstNonEmptyString(<Object?>[
            data['contract_readiness_message'],
          ]) ??
          '',
      processedToday: _boolValue(
        data['processed_today'],
        fallback: false,
      ),
      todayEntryType: firstNonEmptyString(<Object?>[
            data['today_entry_type'],
            data['entry_type_today'],
          ]) ??
          '',
      todayCollectorName: firstNonEmptyString(<Object?>[
            data['today_collector_name'],
            data['recorded_by'],
            data['collector_name_today'],
          ]) ??
          '',
      todayTransactionId: firstNonEmptyString(<Object?>[
        data['today_transaction_id'],
        data['transaction_id_today'],
      ]),
      todayIsLocked: _boolValue(
        data['today_is_locked'],
        fallback: false,
      ),
      canEditToday: _boolValue(
        data['can_edit_today'],
        fallback: false,
      ),
      todayAmount: firstNumber(<Object?>[
            data['today_amount'],
            data['recorded_amount_today'],
          ])?.toDouble() ??
          0,
      todayNote: firstNonEmptyString(<Object?>[
            data['today_note'],
            data['recorded_note_today'],
          ]) ??
          '',
      todayCoveredDates: _dateList(data['today_covered_dates']),
      todayReceipts: _receiptList(data['today_receipts']),
    );
  }
}

List<CollectorRouteReceipt> _receiptList(Object? value) {
  if (value is! Iterable) {
    return const <CollectorRouteReceipt>[];
  }
  return value
      .map(CollectorRouteReceipt.fromPayload)
      .whereType<CollectorRouteReceipt>()
      .toList(growable: false);
}

List<DateTime> _dateList(Object? value) {
  if (value is! Iterable) {
    return const <DateTime>[];
  }
  final dates = value
      .map((item) => DateTime.tryParse(item.toString()))
      .whereType<DateTime>()
      .toSet()
      .toList(growable: false)
    ..sort((left, right) => left.compareTo(right));
  return dates;
}

bool _boolValue(Object? value, {required bool fallback}) {
  if (value is bool) {
    return value;
  }
  final normalized = value?.toString().trim().toLowerCase();
  if (normalized == 'true' || normalized == '1' || normalized == 'yes') {
    return true;
  }
  if (normalized == 'false' || normalized == '0' || normalized == 'no') {
    return false;
  }
  return fallback;
}
