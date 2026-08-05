import 'package:gilbic_mobile/src/core/collector/collector_route.dart';

class CollectorRouteAreaGroup {
  const CollectorRouteAreaGroup({
    required this.area,
    required this.clients,
  });

  final String area;
  final List<CollectorRouteClientGroup> clients;

  int get clientCount => clients.length;

  int get loanCount => clients.fold<int>(
        0,
        (total, client) => total + client.loans.length,
      );

  double get expectedTotal => clients.fold<double>(
        0,
        (total, client) => total + client.expectedTotal,
      );
}

class CollectorRouteClientGroup {
  const CollectorRouteClientGroup({
    required this.clientId,
    required this.clientName,
    required this.area,
    required this.loans,
  });

  final String clientId;
  final String clientName;
  final String area;
  final List<CollectorRouteEntry> loans;

  double get expectedTotal => loans.fold<double>(
        0,
        (total, loan) => total + loan.dailyAmount,
      );

  int get processedLoanCount =>
      loans.where((loan) => loan.processedToday).length;
}

List<CollectorRouteAreaGroup> groupCollectorRoute(CollectorRoute route) {
  final orderedAreaKeys = <String>[];
  final areaLabels = <String, String>{};
  final areaClients = <String, LinkedClientGroups>{};

  void rememberArea(String rawArea) {
    final label = rawArea.trim().isEmpty ? 'Unassigned area' : rawArea.trim();
    final key = label.toLowerCase();
    if (!areaLabels.containsKey(key)) {
      orderedAreaKeys.add(key);
      areaLabels[key] = label;
      areaClients[key] = LinkedClientGroups();
    }
  }

  for (final area in route.areas) {
    rememberArea(area);
  }

  for (final entry in route.entries) {
    rememberArea(entry.area);
    final areaLabel = entry.area.trim().isEmpty
        ? 'Unassigned area'
        : entry.area.trim();
    final areaKey = areaLabel.toLowerCase();
    areaClients[areaKey]!.add(entry);
  }

  return orderedAreaKeys
      .where((key) => areaClients[key]!.isNotEmpty)
      .map(
        (key) => CollectorRouteAreaGroup(
          area: areaLabels[key]!,
          clients: areaClients[key]!.build(),
        ),
      )
      .toList(growable: false);
}

class LinkedClientGroups {
  final List<String> _orderedKeys = <String>[];
  final Map<String, _ClientGroupBuilder> _builders =
      <String, _ClientGroupBuilder>{};

  bool get isNotEmpty => _orderedKeys.isNotEmpty;

  void add(CollectorRouteEntry entry) {
    final clientKey = entry.clientId.trim().isNotEmpty
        ? 'id:${entry.clientId.trim()}'
        : 'name:${entry.clientName.trim().toLowerCase()}';
    final builder = _builders.putIfAbsent(clientKey, () {
      _orderedKeys.add(clientKey);
      return _ClientGroupBuilder(entry);
    });
    builder.loans.add(entry);
  }

  List<CollectorRouteClientGroup> build() {
    return _orderedKeys.map((key) {
      final builder = _builders[key]!;
      final loans = List<CollectorRouteEntry>.of(builder.loans)
        ..sort(_compareLoans);
      return CollectorRouteClientGroup(
        clientId: builder.clientId,
        clientName: builder.clientName,
        area: builder.area,
        loans: loans,
      );
    }).toList(growable: false);
  }
}

class _ClientGroupBuilder {
  _ClientGroupBuilder(CollectorRouteEntry entry)
      : clientId = entry.clientId,
        clientName = entry.clientName,
        area = entry.area;

  final String clientId;
  final String clientName;
  final String area;
  final List<CollectorRouteEntry> loans = <CollectorRouteEntry>[];
}

int _compareLoans(CollectorRouteEntry left, CollectorRouteEntry right) {
  final rankComparison = _loanRank(left.loanType).compareTo(
    _loanRank(right.loanType),
  );
  if (rankComparison != 0) {
    return rankComparison;
  }
  return left.loanType.toLowerCase().compareTo(right.loanType.toLowerCase());
}

int _loanRank(String loanType) {
  final normalized = loanType.toLowerCase().replaceAll(' ', '');
  if (normalized.contains('regular')) {
    return 0;
  }
  if (normalized.contains('7x7') || normalized.contains('7×7')) {
    return 1;
  }
  return 2;
}
