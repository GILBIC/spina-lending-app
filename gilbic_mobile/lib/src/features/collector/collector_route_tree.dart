import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_grouping.dart';
import 'package:gilbic_mobile/src/features/collector/collector_client_ledger.dart';

class CollectorRouteTree extends StatelessWidget {
  const CollectorRouteTree({
    required this.roots,
    required this.expandedAreaUids,
    required this.expandedClients,
    required this.directPayBlockedReasonFor,
    required this.payingLoanIds,
    required this.pendingDirectLoanIds,
    required this.onToggleArea,
    required this.onToggleClient,
    required this.onRecord,
    required this.onRecordCombined,
    required this.detailsBuilder,
    super.key,
  });

  final List<CollectorRouteTreeNode> roots;
  final Set<String> expandedAreaUids;
  final Set<String> expandedClients;
  final CollectorEntryReason directPayBlockedReasonFor;
  final Set<String> payingLoanIds;
  final Set<String> pendingDirectLoanIds;
  final void Function(String areaUid) onToggleArea;
  final void Function(String clientId) onToggleClient;
  final CollectorEntryAction onRecord;
  final CollectorClientAction onRecordCombined;
  final CollectorEntryDetailsBuilder detailsBuilder;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final root in roots)
          _CollectorAreaBranch(
            node: root,
            expandedAreaUids: expandedAreaUids,
            expandedClients: expandedClients,
            directPayBlockedReasonFor: directPayBlockedReasonFor,
            payingLoanIds: payingLoanIds,
            pendingDirectLoanIds: pendingDirectLoanIds,
            onToggleArea: onToggleArea,
            onToggleClient: onToggleClient,
            onRecord: onRecord,
            onRecordCombined: onRecordCombined,
            detailsBuilder: detailsBuilder,
          ),
      ],
    );
  }
}

class _CollectorAreaBranch extends StatelessWidget {
  const _CollectorAreaBranch({
    required this.node,
    required this.expandedAreaUids,
    required this.expandedClients,
    required this.directPayBlockedReasonFor,
    required this.payingLoanIds,
    required this.pendingDirectLoanIds,
    required this.onToggleArea,
    required this.onToggleClient,
    required this.onRecord,
    required this.onRecordCombined,
    required this.detailsBuilder,
  });

  final CollectorRouteTreeNode node;
  final Set<String> expandedAreaUids;
  final Set<String> expandedClients;
  final CollectorEntryReason directPayBlockedReasonFor;
  final Set<String> payingLoanIds;
  final Set<String> pendingDirectLoanIds;
  final void Function(String areaUid) onToggleArea;
  final void Function(String clientId) onToggleClient;
  final CollectorEntryAction onRecord;
  final CollectorClientAction onRecordCombined;
  final CollectorEntryDetailsBuilder detailsBuilder;

  @override
  Widget build(BuildContext context) {
    final areaUid = node.areaUid;
    final isExpandable = areaUid != null && node.children.isNotEmpty;
    final expanded = areaUid != null && expandedAreaUids.contains(areaUid);
    // City/Municipality roots keep their immediate route context visible.
    // Deeper descendants only appear when their parent branch is opened.
    final showChildren = node.depth == 0 || expanded;
    final indent = (node.depth.clamp(0, 6) * 12).toDouble();

    return Padding(
      padding: EdgeInsets.only(left: indent, bottom: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Material(
            color: Theme.of(context).colorScheme.surfaceContainerLowest,
            borderRadius: BorderRadius.circular(10),
            child: InkWell(
              key: areaUid == null ? null : Key('route-area-$areaUid'),
              borderRadius: BorderRadius.circular(10),
              onTap: isExpandable && node.depth > 0
                  ? () => onToggleArea(areaUid)
                  : null,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                child: Row(
                  children: [
                    Icon(
                      node.depth == 0
                          ? Icons.location_city_outlined
                          : Icons.place_outlined,
                      size: 18,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        node.name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.labelLarge?.copyWith(
                              fontWeight: FontWeight.w800,
                            ),
                      ),
                    ),
                    if (node.subtreeClientCount > 0)
                      Text(
                        '${node.subtreeClientCount}',
                        style: Theme.of(context).textTheme.labelSmall,
                      ),
                    if (isExpandable && node.depth > 0) ...[
                      const SizedBox(width: 4),
                      Icon(
                        expanded ? Icons.expand_less : Icons.expand_more,
                        size: 20,
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ),
          if (node.clients.isNotEmpty) ...[
            const SizedBox(height: 6),
            CollectorClientLedgerSection(
              group: CollectorRouteAreaGroup(
                area: node.fullPath,
                clients: node.clients,
              ),
              expandedClients: expandedClients,
              directPayBlockedReasonFor: directPayBlockedReasonFor,
              payingLoanIds: payingLoanIds,
              pendingDirectLoanIds: pendingDirectLoanIds,
              onToggleClient: onToggleClient,
              onRecord: onRecord,
              onRecordCombined: onRecordCombined,
              detailsBuilder: detailsBuilder,
            ),
          ],
          if (showChildren)
            for (final child in node.children)
              _CollectorAreaBranch(
                node: child,
                expandedAreaUids: expandedAreaUids,
                expandedClients: expandedClients,
                directPayBlockedReasonFor: directPayBlockedReasonFor,
                payingLoanIds: payingLoanIds,
                pendingDirectLoanIds: pendingDirectLoanIds,
                onToggleArea: onToggleArea,
                onToggleClient: onToggleClient,
                onRecord: onRecord,
                onRecordCombined: onRecordCombined,
                detailsBuilder: detailsBuilder,
              ),
        ],
      ),
    );
  }
}
