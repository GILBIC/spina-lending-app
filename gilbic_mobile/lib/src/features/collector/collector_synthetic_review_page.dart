import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

/// Synthetic-only CA4 review screen.
///
/// This page intentionally contains no financial writes. It exists so
/// Management can review the Collector information hierarchy, old-ledger feel,
/// combined Regular + 7x7 entry concept, area ordering and master review before
/// we bind the approved design to authoritative server fields.
class CollectorSyntheticReviewPage extends StatefulWidget {
  const CollectorSyntheticReviewPage({super.key});

  @override
  State<CollectorSyntheticReviewPage> createState() =>
      _CollectorSyntheticReviewPageState();
}

class _CollectorSyntheticReviewPageState
    extends State<CollectorSyntheticReviewPage> {
  int _selectedIndex = 0;
  final Set<String> _expandedClients = <String>{};

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_selectedIndex == 0 ? 'Daily Collection' : 'Master Review'),
        actions: [
          Container(
            margin: const EdgeInsets.only(right: 12),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: SpinaTheme.brandPinkSoft,
              borderRadius: BorderRadius.circular(999),
            ),
            child: const Text(
              'SYNTHETIC',
              style: TextStyle(
                color: SpinaTheme.brandPinkDark,
                fontWeight: FontWeight.w800,
                fontSize: 11,
                letterSpacing: .4,
              ),
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: IndexedStack(
          index: _selectedIndex,
          children: [
            _RouteReview(
              expandedClients: _expandedClients,
              onToggleClient: (id) {
                setState(() {
                  if (!_expandedClients.add(id)) {
                    _expandedClients.remove(id);
                  }
                });
              },
              onCollect: _openCollectionPreview,
            ),
            const _MasterReview(),
          ],
        ),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: (index) {
          if (index <= 1) {
            setState(() => _selectedIndex = index);
            return;
          }
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text(
                'Synthetic review: remittance and extra tools will be wired after the Collector route UI is approved.',
              ),
            ),
          );
        },
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.route_outlined),
            selectedIcon: Icon(Icons.route_rounded),
            label: 'Route',
          ),
          NavigationDestination(
            icon: Icon(Icons.fact_check_outlined),
            selectedIcon: Icon(Icons.fact_check_rounded),
            label: 'Master review',
          ),
          NavigationDestination(
            icon: Icon(Icons.account_balance_outlined),
            label: 'Remit',
          ),
          NavigationDestination(
            icon: Icon(Icons.more_horiz_rounded),
            label: 'More',
          ),
        ],
      ),
    );
  }

  Future<void> _openCollectionPreview(_ReviewClient client) async {
    final controller = TextEditingController(
      text: client.amountNeededToday.toStringAsFixed(2),
    );
    var entered = client.amountNeededToday;

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) {
        return StatefulBuilder(
          builder: (context, setSheetState) {
            final split = _previewSplit(client, entered);
            final exact = (entered - client.amountNeededToday).abs() < 0.005;
            return SafeArea(
              child: Padding(
                padding: EdgeInsets.fromLTRB(
                  18,
                  6,
                  18,
                  18 + MediaQuery.viewInsetsOf(context).bottom,
                ),
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(
                        client.name,
                        style: Theme.of(context).textTheme.headlineSmall,
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${client.area} • ${client.paymentMethodLabel}',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 14),
                      Container(
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: SpinaTheme.brandPinkSoft,
                          borderRadius: BorderRadius.circular(18),
                        ),
                        child: Row(
                          children: [
                            const Icon(
                              Icons.auto_awesome_rounded,
                              color: SpinaTheme.brandPinkDark,
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Text(
                                'Today the server would recommend ${_money(client.amountNeededToday)} for this client.',
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 14),
                      TextField(
                        key: const Key('synthetic-client-payment-amount'),
                        controller: controller,
                        autofocus: true,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                        ),
                        decoration: const InputDecoration(
                          labelText: 'Amount received from client',
                          prefixText: '₱ ',
                        ),
                        onChanged: (value) {
                          final parsed = double.tryParse(
                            value.replaceAll(',', '').trim(),
                          );
                          setSheetState(() => entered = parsed ?? 0);
                        },
                      ),
                      const SizedBox(height: 16),
                      Text(
                        'Automatic split preview',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 8),
                      if (client.regularDue > 0)
                        _SplitLine(
                          label: 'Regular',
                          due: client.regularDue,
                          allocated: split.regular,
                        ),
                      if (client.sevenBySevenDue > 0) ...[
                        const SizedBox(height: 8),
                        _SplitLine(
                          label: '7x7',
                          due: client.sevenBySevenDue,
                          allocated: split.sevenBySeven,
                        ),
                      ],
                      const Divider(height: 24),
                      Row(
                        children: [
                          const Expanded(
                            child: Text(
                              'Total entered',
                              style: TextStyle(fontWeight: FontWeight.w700),
                            ),
                          ),
                          Text(
                            _money(entered),
                            style: Theme.of(context)
                                .textTheme
                                .titleMedium
                                ?.copyWith(fontWeight: FontWeight.w800),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: exact
                              ? const Color(0xFFE9F6F0)
                              : const Color(0xFFFFF1E2),
                          borderRadius: BorderRadius.circular(14),
                        ),
                        child: Text(
                          exact
                              ? 'Exact match. In the real app the server will re-check both loans atomically before saving.'
                              : 'Amount differs from today\'s recommended total. The real app will ask the server for the exact safe split instead of guessing on the phone.',
                        ),
                      ),
                      const SizedBox(height: 14),
                      FilledButton.icon(
                        key: const Key('synthetic-confirm-payment'),
                        onPressed: () {
                          Navigator.pop(sheetContext);
                          ScaffoldMessenger.of(this.context).showSnackBar(
                            const SnackBar(
                              content: Text(
                                'Synthetic review only — no payment was saved.',
                              ),
                            ),
                          );
                        },
                        icon: const Icon(Icons.check_circle_outline_rounded),
                        label: const Text('Review confirmation'),
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        );
      },
    );

    controller.dispose();
  }
}

class _RouteReview extends StatelessWidget {
  const _RouteReview({
    required this.expandedClients,
    required this.onToggleClient,
    required this.onCollect,
  });

  final Set<String> expandedClients;
  final ValueChanged<String> onToggleClient;
  final ValueChanged<_ReviewClient> onCollect;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 20),
      children: [
        const _RouteHeader(),
        const SizedBox(height: 10),
        const _AreaOrderStrip(),
        const SizedBox(height: 10),
        for (final area in _reviewAreas) ...[
          _AreaSection(
            area: area,
            expandedClients: expandedClients,
            onToggleClient: onToggleClient,
            onCollect: onCollect,
          ),
          const SizedBox(height: 10),
        ],
        Text(
          'Old-route structure, modern SPINA styling. Official catch-up amount, GCash terms and combined-loan split will come from the server in the production flow.',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ],
    );
  }
}

class _RouteHeader extends StatelessWidget {
  const _RouteHeader();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: SpinaTheme.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Collector: Myra Santos',
                      style: TextStyle(fontWeight: FontWeight.w800),
                    ),
                    SizedBox(height: 2),
                    Text('August 15, 2026 • Online route'),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: const Color(0xFFE9F6F0),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: const Text(
                  'LIVE',
                  style: TextStyle(
                    color: SpinaTheme.success,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          const Row(
            children: [
              Expanded(child: _HeaderStat(value: '18', label: 'Clients')),
              SizedBox(width: 8),
              Expanded(child: _HeaderStat(value: '10', label: 'Done')),
              SizedBox(width: 8),
              Expanded(child: _HeaderStat(value: '8', label: 'Review')),
            ],
          ),
          const SizedBox(height: 8),
          const Row(
            children: [
              Expanded(child: _HeaderStat(value: '₱2,700', label: 'Expected')),
              SizedBox(width: 8),
              Expanded(child: _HeaderStat(value: '₱1,600', label: 'Received')),
              SizedBox(width: 8),
              Expanded(child: _HeaderStat(value: '₱1,100', label: 'Remaining')),
            ],
          ),
        ],
      ),
    );
  }
}

class _HeaderStat extends StatelessWidget {
  const _HeaderStat({required this.value, required this.label});

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 9),
      decoration: BoxDecoration(
        color: SpinaTheme.blush,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        children: [
          Text(
            value,
            maxLines: 1,
            style: const TextStyle(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: Theme.of(context).textTheme.labelSmall,
          ),
        ],
      ),
    );
  }
}

class _AreaOrderStrip extends StatelessWidget {
  const _AreaOrderStrip();

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(
              Icons.format_list_numbered_rounded,
              size: 18,
              color: SpinaTheme.brandPinkDark,
            ),
            const SizedBox(width: 6),
            Text(
              'Area arrangement',
              style: Theme.of(context)
                  .textTheme
                  .labelLarge
                  ?.copyWith(fontWeight: FontWeight.w800),
            ),
          ],
        ),
        const SizedBox(height: 7),
        const SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              _OrderChip(number: 1, label: 'BALAYONG'),
              SizedBox(width: 6),
              _OrderChip(number: 2, label: 'CALAHAN'),
              SizedBox(width: 6),
              _OrderChip(number: 3, label: 'SAN ROQUE'),
            ],
          ),
        ),
      ],
    );
  }
}

class _OrderChip extends StatelessWidget {
  const _OrderChip({required this.number, required this.label});

  final int number;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: SpinaTheme.line),
      ),
      child: Text(
        '$number  $label',
        style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12),
      ),
    );
  }
}

class _AreaSection extends StatelessWidget {
  const _AreaSection({
    required this.area,
    required this.expandedClients,
    required this.onToggleClient,
    required this.onCollect,
  });

  final _ReviewArea area;
  final Set<String> expandedClients;
  final ValueChanged<String> onToggleClient;
  final ValueChanged<_ReviewClient> onCollect;

  @override
  Widget build(BuildContext context) {
    final outstanding = area.clients.where((client) => !client.completed).length;
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: SpinaTheme.line),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          Container(
            color: SpinaTheme.brandPinkSoft,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    'AREA: ${area.name}',
                    style: const TextStyle(
                      color: SpinaTheme.brandPinkDark,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
                Text(
                  '${area.clients.length} clients • $outstanding left',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
          const _LedgerHeader(),
          for (var index = 0; index < area.clients.length; index++) ...[
            if (index > 0) const Divider(height: 1),
            _ClientLedgerRow(
              sequence: index + 1,
              client: area.clients[index],
              expanded: expandedClients.contains(area.clients[index].id),
              onToggle: () => onToggleClient(area.clients[index].id),
              onCollect: () => onCollect(area.clients[index]),
            ),
          ],
        ],
      ),
    );
  }
}

class _LedgerHeader extends StatelessWidget {
  const _LedgerHeader();

  @override
  Widget build(BuildContext context) {
    final style = Theme.of(context).textTheme.labelSmall?.copyWith(
          fontWeight: FontWeight.w800,
        );
    return Container(
      padding: const EdgeInsets.fromLTRB(38, 6, 7, 6),
      color: const Color(0xFFFFFAFC),
      child: Row(
        children: [
          Expanded(flex: 3, child: Text('CLIENT / STATUS', style: style)),
          SizedBox(
            width: 58,
            child: Text('REG', style: style, textAlign: TextAlign.center),
          ),
          SizedBox(
            width: 50,
            child: Text('7x7', style: style, textAlign: TextAlign.center),
          ),
          SizedBox(
            width: 58,
            child: Text('TODAY', style: style, textAlign: TextAlign.center),
          ),
        ],
      ),
    );
  }
}

class _ClientLedgerRow extends StatelessWidget {
  const _ClientLedgerRow({
    required this.sequence,
    required this.client,
    required this.expanded,
    required this.onToggle,
    required this.onCollect,
  });

  final int sequence;
  final _ReviewClient client;
  final bool expanded;
  final VoidCallback onToggle;
  final VoidCallback onCollect;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        InkWell(
          key: Key('synthetic-client-${client.id}'),
          onTap: onToggle,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(8, 9, 7, 8),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  width: 30,
                  child: Text(
                    '$sequence.',
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
                Expanded(
                  flex: 3,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        client.name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontWeight: FontWeight.w900),
                      ),
                      const SizedBox(height: 4),
                      Wrap(
                        spacing: 4,
                        runSpacing: 4,
                        children: [
                          _StatusChip(
                            label: client.primaryStatus,
                            tone: client.statusTone,
                          ),
                          if (client.missedPayments > 0)
                            _StatusChip(
                              label: 'MISSED ${client.missedPayments}',
                              tone: _ChipTone.danger,
                            ),
                          if (client.gcashTerm != null)
                            const _StatusChip(
                              label: 'GCASH',
                              tone: _ChipTone.info,
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
                SizedBox(
                  width: 58,
                  child: Text(
                    client.regularDue <= 0 ? '—' : _moneyShort(client.regularDue),
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
                SizedBox(
                  width: 50,
                  child: Text(
                    client.sevenBySevenDue <= 0
                        ? '—'
                        : _moneyShort(client.sevenBySevenDue),
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
                SizedBox(
                  width: 58,
                  child: Column(
                    children: [
                      Text(
                        _moneyShort(client.amountNeededToday),
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontWeight: FontWeight.w900,
                          color: client.completed
                              ? SpinaTheme.success
                              : SpinaTheme.brandPinkDark,
                        ),
                      ),
                      Icon(
                        expanded ? Icons.expand_less : Icons.expand_more,
                        size: 19,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
        if (expanded)
          Container(
            width: double.infinity,
            margin: const EdgeInsets.fromLTRB(38, 0, 8, 9),
            padding: const EdgeInsets.all(11),
            decoration: BoxDecoration(
              color: const Color(0xFFFFFAFC),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: const Color(0xFFF3E5EB)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _DetailLine(label: 'Term', value: client.termLabel),
                _DetailLine(label: 'Due', value: client.dueLabel),
                if (client.gcashTerm != null)
                  _DetailLine(label: 'GCash term', value: client.gcashTerm!),
                if (client.note.isNotEmpty)
                  _DetailLine(label: 'Note', value: client.note),
                if (client.catchUpLabel != null)
                  _DetailLine(label: 'Catch-up', value: client.catchUpLabel!),
                if (client.advanceLabel != null)
                  _DetailLine(label: 'Advance', value: client.advanceLabel!),
                const SizedBox(height: 8),
                if (!client.completed)
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                      key: Key('synthetic-collect-${client.id}'),
                      onPressed: onCollect,
                      icon: const Icon(Icons.payments_outlined, size: 18),
                      label: Text(
                        'Collect ${_money(client.amountNeededToday)}',
                      ),
                    ),
                  )
                else
                  const Row(
                    children: [
                      Icon(
                        Icons.check_circle_rounded,
                        color: SpinaTheme.success,
                        size: 20,
                      ),
                      SizedBox(width: 7),
                      Text(
                        'Collection complete for today',
                        style: TextStyle(fontWeight: FontWeight.w700),
                      ),
                    ],
                  ),
              ],
            ),
          ),
      ],
    );
  }
}

class _DetailLine extends StatelessWidget {
  const _DetailLine({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: RichText(
        text: TextSpan(
          style: Theme.of(context).textTheme.bodySmall,
          children: [
            TextSpan(
              text: '$label: ',
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
            TextSpan(text: value),
          ],
        ),
      ),
    );
  }
}

class _MasterReview extends StatelessWidget {
  const _MasterReview();

  @override
  Widget build(BuildContext context) {
    final allClients = _reviewAreas
        .expand((area) => area.clients)
        .toList(growable: false);
    final notFinished = allClients
        .where((client) => !client.completed)
        .toList(growable: false);
    final attention = notFinished
        .where(
          (client) =>
              client.missedPayments > 0 ||
              client.gcashTerm != null ||
              client.statusTone == _ChipTone.danger ||
              client.statusTone == _ChipTone.warning,
        )
        .toList(growable: false);

    return ListView(
      padding: const EdgeInsets.fromLTRB(14, 8, 14, 20),
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: SpinaTheme.brandPinkSoft,
            borderRadius: BorderRadius.circular(20),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'All-area collection check',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      color: SpinaTheme.brandPinkDark,
                    ),
              ),
              const SizedBox(height: 5),
              const Text(
                'Before leaving the route, review everyone who is not complete across every assigned area.',
              ),
              const SizedBox(height: 14),
              Row(
                children: [
                  Expanded(
                    child: _MasterStat(
                      value: '${notFinished.length}',
                      label: 'Not complete',
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _MasterStat(
                      value: '${attention.length}',
                      label: 'Needs attention',
                    ),
                  ),
                  const SizedBox(width: 8),
                  const Expanded(
                    child: _MasterStat(value: '2', label: 'GCash pending'),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 14),
        Text(
          'Area completion',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 8),
        for (final area in _reviewAreas) ...[
          _AreaReviewCard(area: area),
          const SizedBox(height: 8),
        ],
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: Text(
                'Who still needs action',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            Text(
              '${notFinished.length} clients',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
        const SizedBox(height: 8),
        for (final client in notFinished) ...[
          _OutstandingClientCard(client: client),
          const SizedBox(height: 8),
        ],
      ],
    );
  }
}

class _MasterStat extends StatelessWidget {
  const _MasterStat({required this.value, required this.label});

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        children: [
          Text(
            value,
            style: Theme.of(context)
                .textTheme
                .titleLarge
                ?.copyWith(fontWeight: FontWeight.w900),
          ),
          Text(
            label,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.labelSmall,
          ),
        ],
      ),
    );
  }
}

class _AreaReviewCard extends StatelessWidget {
  const _AreaReviewCard({required this.area});

  final _ReviewArea area;

  @override
  Widget build(BuildContext context) {
    final done = area.clients.where((client) => client.completed).length;
    final remaining = area.clients.length - done;
    final progress = area.clients.isEmpty ? 0.0 : done / area.clients.length;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: SpinaTheme.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  area.name,
                  style: const TextStyle(fontWeight: FontWeight.w900),
                ),
              ),
              Text('$done/${area.clients.length} done • $remaining left'),
            ],
          ),
          const SizedBox(height: 8),
          LinearProgressIndicator(value: progress),
        ],
      ),
    );
  }
}

class _OutstandingClientCard extends StatelessWidget {
  const _OutstandingClientCard({required this.client});

  final _ReviewClient client;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: SpinaTheme.line),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: client.missedPayments > 0
                  ? const Color(0xFFFFE7E4)
                  : SpinaTheme.brandPinkSoft,
              borderRadius: BorderRadius.circular(13),
            ),
            child: Icon(
              client.missedPayments > 0
                  ? Icons.priority_high_rounded
                  : Icons.person_outline_rounded,
              color: client.missedPayments > 0
                  ? Theme.of(context).colorScheme.error
                  : SpinaTheme.brandPinkDark,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  client.name,
                  style: const TextStyle(fontWeight: FontWeight.w900),
                ),
                const SizedBox(height: 2),
                Text(
                  '${client.area} • ${client.primaryStatus}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                if (client.catchUpLabel != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    client.catchUpLabel!,
                    style: const TextStyle(
                      fontWeight: FontWeight.w800,
                      color: Color(0xFF9A4D12),
                    ),
                  ),
                ],
                if (client.gcashTerm != null) ...[
                  const SizedBox(height: 3),
                  Text(
                    'GCash: ${client.gcashTerm}',
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ],
                if (client.note.isNotEmpty) ...[
                  const SizedBox(height: 3),
                  Text('Note: ${client.note}'),
                ],
              ],
            ),
          ),
          Text(
            _money(client.amountNeededToday),
            style: const TextStyle(
              color: SpinaTheme.brandPinkDark,
              fontWeight: FontWeight.w900,
            ),
          ),
        ],
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.label, required this.tone});

  final String label;
  final _ChipTone tone;

  @override
  Widget build(BuildContext context) {
    final colors = switch (tone) {
      _ChipTone.good => (const Color(0xFFE8F6EF), SpinaTheme.success),
      _ChipTone.warning => (const Color(0xFFFFF0DE), const Color(0xFF97510D)),
      _ChipTone.danger => (
          const Color(0xFFFFE7E4),
          Theme.of(context).colorScheme.error,
        ),
      _ChipTone.info => (const Color(0xFFE9F1FF), const Color(0xFF315C9B)),
      _ChipTone.neutral => (const Color(0xFFF2EDF0), SpinaTheme.inkMuted),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: colors.$1,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: colors.$2,
          fontWeight: FontWeight.w800,
          fontSize: 10,
        ),
      ),
    );
  }
}

class _SplitLine extends StatelessWidget {
  const _SplitLine({
    required this.label,
    required this.due,
    required this.allocated,
  });

  final String label;
  final double due;
  final double allocated;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFAFC),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: SpinaTheme.line),
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              '$label due ${_money(due)}',
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
          ),
          Text(
            _money(allocated),
            style: const TextStyle(
              color: SpinaTheme.brandPinkDark,
              fontWeight: FontWeight.w900,
            ),
          ),
        ],
      ),
    );
  }
}

class _ReviewArea {
  const _ReviewArea({required this.name, required this.clients});

  final String name;
  final List<_ReviewClient> clients;
}

class _ReviewClient {
  const _ReviewClient({
    required this.id,
    required this.name,
    required this.area,
    required this.regularDue,
    required this.sevenBySevenDue,
    required this.amountNeededToday,
    required this.primaryStatus,
    required this.statusTone,
    required this.termLabel,
    required this.dueLabel,
    this.completed = false,
    this.missedPayments = 0,
    this.gcashTerm,
    this.note = '',
    this.catchUpLabel,
    this.advanceLabel,
  });

  final String id;
  final String name;
  final String area;
  final double regularDue;
  final double sevenBySevenDue;
  final double amountNeededToday;
  final String primaryStatus;
  final _ChipTone statusTone;
  final String termLabel;
  final String dueLabel;
  final bool completed;
  final int missedPayments;
  final String? gcashTerm;
  final String note;
  final String? catchUpLabel;
  final String? advanceLabel;

  String get paymentMethodLabel => gcashTerm == null ? 'Cash' : 'GCash';
}

enum _ChipTone { good, warning, danger, info, neutral }

class _PreviewSplit {
  const _PreviewSplit({required this.regular, required this.sevenBySeven});

  final double regular;
  final double sevenBySeven;
}

_PreviewSplit _previewSplit(_ReviewClient client, double amount) {
  if (amount <= 0) {
    return const _PreviewSplit(regular: 0, sevenBySeven: 0);
  }
  final regular = math.min(amount, client.regularDue);
  final remaining = math.max(0, amount - regular);
  final seven = math.min(remaining, client.sevenBySevenDue);
  return _PreviewSplit(regular: regular, sevenBySeven: seven);
}

String _money(double value) => '₱${value.toStringAsFixed(2)}';

String _moneyShort(double value) {
  if ((value - value.roundToDouble()).abs() < 0.005) {
    return '₱${value.toStringAsFixed(0)}';
  }
  return _money(value);
}

const List<_ReviewArea> _reviewAreas = [
  _ReviewArea(
    name: 'BALAYONG',
    clients: [
      _ReviewClient(
        id: 'bal-ana',
        name: 'Ana Dela Cruz',
        area: 'BALAYONG',
        regularDue: 100,
        sevenBySevenDue: 50,
        amountNeededToday: 150,
        primaryStatus: 'NOT COLLECTED',
        statusTone: _ChipTone.warning,
        termLabel: 'Regular 120 days • 7x7 active',
        dueLabel: 'Regular due Dec 02 • 7x7 ongoing',
        gcashTerm: 'Pays at 5:30 PM after work',
        note: 'Usually sends exact ₱150 by GCash.',
      ),
      _ReviewClient(
        id: 'bal-maria',
        name: 'Maria Lopez',
        area: 'BALAYONG',
        regularDue: 200,
        sevenBySevenDue: 50,
        amountNeededToday: 250,
        primaryStatus: 'CATCH-UP',
        statusTone: _ChipTone.danger,
        termLabel: 'Regular 120 days • 7x7 active',
        dueLabel: 'Regular due Nov 26 • 7x7 ongoing',
        missedPayments: 1,
        catchUpLabel: 'Missed 1 payment — server recommends ₱250 today.',
        note: 'Ask about yesterday before collecting.',
      ),
      _ReviewClient(
        id: 'bal-liza',
        name: 'Liza Ramos',
        area: 'BALAYONG',
        regularDue: 0,
        sevenBySevenDue: 0,
        amountNeededToday: 0,
        primaryStatus: 'ADV',
        statusTone: _ChipTone.good,
        termLabel: 'Regular 120 days',
        dueLabel: 'Due Nov 30',
        completed: true,
        advanceLabel: 'Covered through Aug 18, 2026.',
        note: 'Do not collect today unless coverage changes.',
      ),
    ],
  ),
  _ReviewArea(
    name: 'CALAHAN',
    clients: [
      _ReviewClient(
        id: 'cal-rosa',
        name: 'Rosa Mendoza',
        area: 'CALAHAN',
        regularDue: 100,
        sevenBySevenDue: 50,
        amountNeededToday: 150,
        primaryStatus: 'DONE',
        statusTone: _ChipTone.good,
        termLabel: 'Regular 120 days • 7x7 active',
        dueLabel: 'Regular due Dec 05 • 7x7 ongoing',
        completed: true,
        note: 'Collected cash at 9:12 AM.',
      ),
      _ReviewClient(
        id: 'cal-joy',
        name: 'Joy Villanueva',
        area: 'CALAHAN',
        regularDue: 300,
        sevenBySevenDue: 50,
        amountNeededToday: 350,
        primaryStatus: 'CATCH-UP',
        statusTone: _ChipTone.danger,
        termLabel: 'Regular 120 days • 7x7 active',
        dueLabel: 'Regular due Nov 18 • 7x7 ongoing',
        missedPayments: 2,
        catchUpLabel: 'Missed 2 payments — server recommends triple Regular + today 7x7.',
        gcashTerm: 'Pays by GCash before 8:00 PM',
        note: 'Confirm GCash before marking complete.',
      ),
      _ReviewClient(
        id: 'cal-nena',
        name: 'Nena Flores',
        area: 'CALAHAN',
        regularDue: 100,
        sevenBySevenDue: 0,
        amountNeededToday: 100,
        primaryStatus: 'PASS 1',
        statusTone: _ChipTone.warning,
        termLabel: 'Regular 120 days',
        dueLabel: 'Due Dec 10',
        note: 'Yesterday: hospital. Revisit today.',
      ),
    ],
  ),
  _ReviewArea(
    name: 'SAN ROQUE',
    clients: [
      _ReviewClient(
        id: 'sr-ellen',
        name: 'Ellen Santos',
        area: 'SAN ROQUE',
        regularDue: 100,
        sevenBySevenDue: 50,
        amountNeededToday: 150,
        primaryStatus: 'NOT COLLECTED',
        statusTone: _ChipTone.warning,
        termLabel: 'Regular 120 days • 7x7 active',
        dueLabel: 'Regular due Dec 14 • 7x7 ongoing',
        note: 'Collect after lunch.',
      ),
      _ReviewClient(
        id: 'sr-cora',
        name: 'Cora Garcia',
        area: 'SAN ROQUE',
        regularDue: 100,
        sevenBySevenDue: 0,
        amountNeededToday: 100,
        primaryStatus: 'GCASH PENDING',
        statusTone: _ChipTone.info,
        termLabel: 'Regular 120 days',
        dueLabel: 'Due Dec 01',
        gcashTerm: 'Pays every collection day at 6:00 PM',
        note: 'Wait for proof before end-of-day review.',
      ),
      _ReviewClient(
        id: 'sr-beth',
        name: 'Beth Navarro',
        area: 'SAN ROQUE',
        regularDue: 100,
        sevenBySevenDue: 50,
        amountNeededToday: 150,
        primaryStatus: 'DONE',
        statusTone: _ChipTone.good,
        termLabel: 'Regular 120 days • 7x7 active',
        dueLabel: 'Regular due Dec 08 • 7x7 ongoing',
        completed: true,
        note: 'Collected cash at 11:05 AM.',
      ),
    ],
  ),
];
