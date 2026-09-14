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

class CollectorRouteTreeNode {
  const CollectorRouteTreeNode({
    required this.areaUid,
    required this.name,
    required this.fullPath,
    required this.depth,
    required this.sortOrder,
    required this.isLegacyUnmapped,
    required this.clients,
    required this.children,
  });

  final String? areaUid;
  final String name;
  final String fullPath;
  final int depth;
  final int sortOrder;
  final bool isLegacyUnmapped;
  final List<CollectorRouteClientGroup> clients;
  final List<CollectorRouteTreeNode> children;

  int get directClientCount => clients.length;

  int get subtreeClientCount => clients.length +
      children.fold<int>(
        0,
        (total, child) => total + child.subtreeClientCount,
      );

  int get loanCount => clients.fold<int>(
        0,
        (total, client) => total + client.loans.length,
      ) +
      children.fold<int>(
        0,
        (total, child) => total + child.loanCount,
      );

  double get expectedTotal => clients.fold<double>(
        0,
        (total, client) => total + client.expectedTotal,
      ) +
      children.fold<double>(
        0,
        (total, child) => total + child.expectedTotal,
      );
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

List<CollectorRouteTreeNode> buildCollectorRouteTree(CollectorRoute route) {
  if (route.areaNodes.isEmpty) {
    return _buildLegacyTree(route);
  }

  final orderedBuilders = <_CollectorRouteTreeNodeBuilder>[];
  final buildersByUid = <String, _CollectorRouteTreeNodeBuilder>{};
  for (final node in route.areaNodes) {
    final areaUid = node.areaUid.trim();
    if (areaUid.isEmpty || buildersByUid.containsKey(areaUid)) {
      continue;
    }
    final builder = _CollectorRouteTreeNodeBuilder(node);
    orderedBuilders.add(builder);
    buildersByUid[areaUid] = builder;
  }

  if (orderedBuilders.isEmpty) {
    return _buildLegacyTree(route);
  }

  final legacyEntries = <CollectorRouteEntry>[];
  for (final entry in route.entries) {
    final areaUid = entry.areaUid?.trim();
    final builder = areaUid == null || areaUid.isEmpty
        ? null
        : buildersByUid[areaUid];
    if (builder == null) {
      legacyEntries.add(entry);
      continue;
    }
    builder.clients.add(entry);
  }

  final roots = <_CollectorRouteTreeNodeBuilder>[];
  for (final builder in orderedBuilders) {
    final parentAreaUid = builder.node.parentAreaUid?.trim();
    final parent = parentAreaUid == null || parentAreaUid.isEmpty
        ? null
        : buildersByUid[parentAreaUid];
    if (parent == null || identical(parent, builder)) {
      roots.add(builder);
      continue;
    }
    parent.children.add(builder);
  }

  final tree = roots.map((builder) => builder.build()).toList(growable: true);
  if (legacyEntries.isNotEmpty) {
    final legacyRoute = CollectorRoute(
      routeDate: route.routeDate,
      collectorName: route.collectorName,
      areas: route.areas,
      entries: legacyEntries,
      expectedTotal: legacyEntries.fold<double>(
        0,
        (total, entry) => total + entry.dailyAmount,
      ),
    );
    tree.addAll(_buildLegacyTree(legacyRoute));
  }
  return List<CollectorRouteTreeNode>.unmodifiable(tree);
}

List<CollectorRouteTreeNode> _buildLegacyTree(CollectorRoute route) {
  final groups = groupCollectorRoute(route);
  return List<CollectorRouteTreeNode>.generate(
    groups.length,
    (index) {
      final group = groups[index];
      return CollectorRouteTreeNode(
        areaUid: null,
        name: group.area,
        fullPath: group.area,
        depth: 0,
        sortOrder: index,
        isLegacyUnmapped: true,
        clients: group.clients,
        children: const <CollectorRouteTreeNode>[],
      );
    },
    growable: false,
  );
}

class _CollectorRouteTreeNodeBuilder {
  _CollectorRouteTreeNodeBuilder(this.node);

  final CollectorRouteAreaNode node;
  final LinkedClientGroups clients = LinkedClientGroups();
  final List<_CollectorRouteTreeNodeBuilder> children =
      <_CollectorRouteTreeNodeBuilder>[];

  CollectorRouteTreeNode build() {
    return CollectorRouteTreeNode(
      areaUid: node.areaUid,
      name: node.name,
      fullPath: node.fullPath,
      depth: node.depth,
      sortOrder: node.sortOrder,
      isLegacyUnmapped: node.isLegacyUnmapped,
      clients: clients.build(),
      children: children.map((child) => child.build()).toList(growable: false),
    );
  }
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
