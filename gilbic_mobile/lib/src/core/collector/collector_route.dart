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
    );
  }
}
