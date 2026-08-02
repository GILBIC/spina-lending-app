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
    this.note = '',
    this.routeRevision,
    this.canCollectMobile = true,
    this.canEnterPayment = true,
    this.collectionMessage = '',
    this.processedToday = false,
    this.todayEntryType = '',
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
  final String note;
  final String? routeRevision;
  final bool canCollectMobile;
  final bool canEnterPayment;
  final String collectionMessage;
  final bool processedToday;
  final String todayEntryType;

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
      'note': note,
      'route_revision': routeRevision,
      'can_collect_mobile': canCollectMobile,
      'can_enter_payment': canEnterPayment,
      'collection_message': collectionMessage,
      'processed_today': processedToday,
      'today_entry_type': todayEntryType,
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
      collectionMessage: firstNonEmptyString(<Object?>[
            data['collection_message'],
            data['status_message'],
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
    );
  }
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
