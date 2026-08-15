import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

/// Synthetic-only CA4 review screen shown behind a real authenticated Collector
/// session. No action on this page writes financial data.
class CollectorSyntheticReviewPage extends StatefulWidget {
  const CollectorSyntheticReviewPage({super.key});

  @override
  State<CollectorSyntheticReviewPage> createState() =>
      _CollectorSyntheticReviewPageState();
}

class _CollectorSyntheticReviewPageState
    extends State<CollectorSyntheticReviewPage> {
  int _selectedIndex = 0;
  final Set<String> _expanded = <String>{};

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_selectedIndex == 0 ? 'Daily Collection' : 'Master Review'),
        actions: const [
          Padding(
            padding: EdgeInsets.only(right: 14),
            child: Center(child: _SyntheticBadge()),
          ),
        ],
      ),
      body: SafeArea(
        child: IndexedStack(
          index: _selectedIndex,
          children: [
            _routeView(context),
            _masterReview(context),
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
                'Synthetic review only. Real remittance and tools stay in the authenticated Collector app.',
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

  Widget _routeView(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 24),
      children: [
        const _RouteSummary(),
        const SizedBox(height: 10),
        const _AreaOrder(),
        const SizedBox(height: 10),
        for (final area in _areas) ...[
          _areaCard(context, area),
          const SizedBox(height: 10),
        ],
        Text(
          'Old ledger structure + modern SPINA styling. Production amounts, catch-up requirements, notes and GCash terms will come from the authoritative backend.',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ],
    );
  }

  Widget _areaCard(BuildContext context, _Area area) {
    final left = area.clients.where((client) => !client.completed).length;
    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: SpinaTheme.line),
      ),
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
                Text('${area.clients.length} clients • $left left'),
              ],
            ),
          ),
          const _LedgerHeader(),
          for (var i = 0; i < area.clients.length; i++) ...[
            if (i > 0) const Divider(height: 1),
            _clientRow(context, area.clients[i], i + 1),
          ],
        ],
      ),
    );
  }

  Widget _clientRow(BuildContext context, _Client client, int sequence) {
    final expanded = _expanded.contains(client.id);
    return Column(
      children: [
        InkWell(
          key: Key('synthetic-client-${client.id}'),
          onTap: () {
            setState(() {
              if (!_expanded.add(client.id)) {
                _expanded.remove(client.id);
              }
            });
          },
          child: Padding(
            padding: const EdgeInsets.fromLTRB(8, 9, 7, 8),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  width: 30,
                  child: Text('$sequence.', style: const TextStyle(fontWeight: FontWeight.w700)),
                ),
                Expanded(
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
                          _StatusChip(label: client.status, tone: client.tone),
                          if (client.missed > 0)
                            _StatusChip(label: 'MISSED ${client.missed}', tone: _Tone.danger),
                          if (client.gcashTerm != null)
                            const _StatusChip(label: 'GCASH', tone: _Tone.info),
                        ],
                      ),
                    ],
                  ),
                ),
                _AmountColumn(value: client.regularDue),
                _AmountColumn(value: client.sevenBySevenDue, width: 50),
                SizedBox(
                  width: 62,
                  child: Column(
                    children: [
                      Text(
                        _shortMoney(client.today),
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontWeight: FontWeight.w900,
                          color: client.completed
                              ? SpinaTheme.success
                              : SpinaTheme.brandPinkDark,
                        ),
                      ),
                      Icon(expanded ? Icons.expand_less : Icons.expand_more, size: 18),
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
                _Detail(label: 'Term', value: client.term),
                _Detail(label: 'Due', value: client.due),
                if (client.gcashTerm != null)
                  _Detail(label: 'GCash term', value: client.gcashTerm!),
                if (client.note.isNotEmpty)
                  _Detail(label: 'Note', value: client.note),
                if (client.catchUp != null)
                  _Detail(label: 'Catch-up', value: client.catchUp!),
                if (client.advance != null)
                  _Detail(label: 'Advance', value: client.advance!),
                const SizedBox(height: 8),
                if (!client.completed)
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                      key: Key('synthetic-collect-${client.id}'),
                      onPressed: () => _openSplitPreview(client),
                      icon: const Icon(Icons.payments_outlined, size: 18),
                      label: Text('Collect ${_money(client.today)}'),
                    ),
                  )
                else
                  const Row(
                    children: [
                      Icon(Icons.check_circle_rounded, color: SpinaTheme.success, size: 20),
                      SizedBox(width: 7),
                      Text('Collection complete for today', style: TextStyle(fontWeight: FontWeight.w700)),
                    ],
                  ),
              ],
            ),
          ),
      ],
    );
  }

  Future<void> _openSplitPreview(_Client client) async {
    final controller = TextEditingController(text: client.today.toStringAsFixed(2));
    var entered = client.today;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) {
        return StatefulBuilder(
          builder: (context, setSheetState) {
            final regular = entered < client.regularDue ? entered : client.regularDue;
            final remaining = entered - regular > 0 ? entered - regular : 0.0;
            final seven = remaining < client.sevenBySevenDue
                ? remaining
                : client.sevenBySevenDue;
            final exact = (entered - client.today).abs() < 0.005;
            return SafeArea(
              child: Padding(
                padding: EdgeInsets.fromLTRB(
                  18,
                  8,
                  18,
                  18 + MediaQuery.viewInsetsOf(context).bottom,
                ),
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(client.name, style: Theme.of(context).textTheme.headlineSmall),
                      const SizedBox(height: 4),
                      Text('${client.area} • ${client.gcashTerm == null ? 'Cash' : 'GCash'}'),
                      const SizedBox(height: 12),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: SpinaTheme.brandPinkSoft,
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: Text(
                          'Today the server would recommend ${_money(client.today)} for this client.',
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        key: const Key('synthetic-client-payment-amount'),
                        controller: controller,
                        autofocus: true,
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        decoration: const InputDecoration(
                          labelText: 'Amount received from client',
                          prefixText: '₱ ',
                        ),
                        onChanged: (value) {
                          final parsed = double.tryParse(value.replaceAll(',', '').trim());
                          setSheetState(() => entered = parsed ?? 0);
                        },
                      ),
                      const SizedBox(height: 14),
                      Text('Automatic split preview', style: Theme.of(context).textTheme.titleMedium),
                      const SizedBox(height: 8),
                      if (client.regularDue > 0)
                        _SplitLine(label: 'Regular', due: client.regularDue, allocated: regular),
                      if (client.sevenBySevenDue > 0) ...[
                        const SizedBox(height: 8),
                        _SplitLine(label: '7x7', due: client.sevenBySevenDue, allocated: seven),
                      ],
                      const SizedBox(height: 10),
                      Text(
                        exact
                            ? 'Exact match. Production will re-check both loans atomically on the server before saving.'
                            : 'Different amount. Production will ask the server for the exact safe allocation instead of guessing on the phone.',
                      ),
                      const SizedBox(height: 12),
                      FilledButton.icon(
                        key: const Key('synthetic-confirm-payment'),
                        onPressed: () {
                          Navigator.pop(sheetContext);
                          ScaffoldMessenger.of(this.context).showSnackBar(
                            const SnackBar(content: Text('Synthetic review only — no payment was saved.')),
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

  Widget _masterReview(BuildContext context) {
    final clients = _areas.expand((area) => area.clients).toList(growable: false);
    final open = clients.where((client) => !client.completed).toList(growable: false);
    final attention = open.where((client) => client.missed > 0 || client.gcashTerm != null).length;
    return ListView(
      padding: const EdgeInsets.fromLTRB(14, 10, 14, 24),
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
                style: Theme.of(context).textTheme.titleLarge?.copyWith(color: SpinaTheme.brandPinkDark),
              ),
              const SizedBox(height: 5),
              const Text('Before leaving the route, review everyone who is not complete across every assigned area.'),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(child: _MasterStat(value: '${open.length}', label: 'Not complete')),
                  const SizedBox(width: 8),
                  Expanded(child: _MasterStat(value: '$attention', label: 'Needs attention')),
                  const SizedBox(width: 8),
                  const Expanded(child: _MasterStat(value: '2', label: 'GCash pending')),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 14),
        Text('Area completion', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        for (final area in _areas) ...[
          _AreaProgress(area: area),
          const SizedBox(height: 8),
        ],
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(child: Text('Who still needs action', style: Theme.of(context).textTheme.titleMedium)),
            Text('${open.length} clients'),
          ],
        ),
        const SizedBox(height: 8),
        for (final client in open) ...[
          _Outstanding(client: client),
          const SizedBox(height: 8),
        ],
      ],
    );
  }
}

class _SyntheticBadge extends StatelessWidget {
  const _SyntheticBadge();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(color: SpinaTheme.brandPinkSoft, borderRadius: BorderRadius.circular(999)),
      child: const Text('SYNTHETIC', style: TextStyle(color: SpinaTheme.brandPinkDark, fontWeight: FontWeight.w900, fontSize: 10)),
    );
  }
}

class _RouteSummary extends StatelessWidget {
  const _RouteSummary();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18), border: Border.all(color: SpinaTheme.line)),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Collector: Myra Santos', style: TextStyle(fontWeight: FontWeight.w900)),
          Text('August 15, 2026 • Online route'),
          SizedBox(height: 10),
          Row(
            children: [
              Expanded(child: _SummaryTile(value: '18', label: 'Clients')),
              SizedBox(width: 6),
              Expanded(child: _SummaryTile(value: '10', label: 'Done')),
              SizedBox(width: 6),
              Expanded(child: _SummaryTile(value: '8', label: 'Review')),
            ],
          ),
          SizedBox(height: 6),
          Row(
            children: [
              Expanded(child: _SummaryTile(value: '₱2,700', label: 'Expected')),
              SizedBox(width: 6),
              Expanded(child: _SummaryTile(value: '₱1,600', label: 'Received')),
              SizedBox(width: 6),
              Expanded(child: _SummaryTile(value: '₱1,100', label: 'Remaining')),
            ],
          ),
        ],
      ),
    );
  }
}

class _SummaryTile extends StatelessWidget {
  const _SummaryTile({required this.value, required this.label});
  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 5),
      decoration: BoxDecoration(color: SpinaTheme.blush, borderRadius: BorderRadius.circular(12)),
      child: Column(children: [Text(value, maxLines: 1, style: const TextStyle(fontWeight: FontWeight.w900)), Text(label, style: Theme.of(context).textTheme.labelSmall)]),
    );
  }
}

class _AreaOrder extends StatelessWidget {
  const _AreaOrder();

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Area arrangement', style: TextStyle(fontWeight: FontWeight.w900)),
        const SizedBox(height: 6),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: _areas.indexed.map((entry) {
              return Padding(
                padding: const EdgeInsets.only(right: 6),
                child: Chip(label: Text('${entry.$1 + 1}  ${entry.$2.name}')),
              );
            }).toList(growable: false),
          ),
        ),
      ],
    );
  }
}

class _LedgerHeader extends StatelessWidget {
  const _LedgerHeader();

  @override
  Widget build(BuildContext context) {
    final style = Theme.of(context).textTheme.labelSmall?.copyWith(fontWeight: FontWeight.w900);
    return Container(
      color: const Color(0xFFFFFAFC),
      padding: const EdgeInsets.fromLTRB(38, 6, 7, 6),
      child: Row(
        children: [
          Expanded(child: Text('CLIENT / STATUS', style: style)),
          SizedBox(width: 58, child: Text('REG', style: style, textAlign: TextAlign.center)),
          SizedBox(width: 50, child: Text('7x7', style: style, textAlign: TextAlign.center)),
          SizedBox(width: 62, child: Text('TODAY', style: style, textAlign: TextAlign.center)),
        ],
      ),
    );
  }
}

class _AmountColumn extends StatelessWidget {
  const _AmountColumn({required this.value, this.width = 58});
  final double value;
  final double width;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      child: Text(value <= 0 ? '—' : _shortMoney(value), textAlign: TextAlign.center, style: const TextStyle(fontWeight: FontWeight.w700)),
    );
  }
}

class _Detail extends StatelessWidget {
  const _Detail({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 3),
      child: Text('$label: $value', style: Theme.of(context).textTheme.bodySmall),
    );
  }
}

class _SplitLine extends StatelessWidget {
  const _SplitLine({required this.label, required this.due, required this.allocated});
  final String label;
  final double due;
  final double allocated;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(color: const Color(0xFFFFFAFC), borderRadius: BorderRadius.circular(14), border: Border.all(color: SpinaTheme.line)),
      child: Row(
        children: [
          Expanded(child: Text('$label due ${_money(due)}', style: const TextStyle(fontWeight: FontWeight.w700))),
          Text(_money(allocated), style: const TextStyle(color: SpinaTheme.brandPinkDark, fontWeight: FontWeight.w900)),
        ],
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.label, required this.tone});
  final String label;
  final _Tone tone;

  @override
  Widget build(BuildContext context) {
    final bg = switch (tone) {
      _Tone.good => const Color(0xFFE8F6EF),
      _Tone.warning => const Color(0xFFFFF0DE),
      _Tone.danger => const Color(0xFFFFE7E4),
      _Tone.info => const Color(0xFFE9F1FF),
    };
    final fg = switch (tone) {
      _Tone.good => SpinaTheme.success,
      _Tone.warning => const Color(0xFF97510D),
      _Tone.danger => Theme.of(context).colorScheme.error,
      _Tone.info => const Color(0xFF315C9B),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(999)),
      child: Text(label, style: TextStyle(color: fg, fontWeight: FontWeight.w900, fontSize: 10)),
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
      padding: const EdgeInsets.symmetric(vertical: 9, horizontal: 4),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(14)),
      child: Column(children: [Text(value, style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 20)), Text(label, textAlign: TextAlign.center, style: Theme.of(context).textTheme.labelSmall)]),
    );
  }
}

class _AreaProgress extends StatelessWidget {
  const _AreaProgress({required this.area});
  final _Area area;

  @override
  Widget build(BuildContext context) {
    final done = area.clients.where((client) => client.completed).length;
    final progress = area.clients.isEmpty ? 0.0 : done / area.clients.length;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            Row(children: [Expanded(child: Text(area.name, style: const TextStyle(fontWeight: FontWeight.w900))), Text('$done/${area.clients.length} done • ${area.clients.length - done} left')]),
            const SizedBox(height: 8),
            LinearProgressIndicator(value: progress),
          ],
        ),
      ),
    );
  }
}

class _Outstanding extends StatelessWidget {
  const _Outstanding({required this.client});
  final _Client client;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(client.missed > 0 ? Icons.priority_high_rounded : Icons.person_outline_rounded, color: client.missed > 0 ? Theme.of(context).colorScheme.error : SpinaTheme.brandPinkDark),
            const SizedBox(width: 9),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(client.name, style: const TextStyle(fontWeight: FontWeight.w900)),
                  Text('${client.area} • ${client.status}'),
                  if (client.catchUp != null) Text(client.catchUp!, style: const TextStyle(fontWeight: FontWeight.w800, color: Color(0xFF9A4D12))),
                  if (client.gcashTerm != null) Text('GCash: ${client.gcashTerm}', style: const TextStyle(fontWeight: FontWeight.w700)),
                  if (client.note.isNotEmpty) Text('Note: ${client.note}'),
                ],
              ),
            ),
            Text(_money(client.today), style: const TextStyle(color: SpinaTheme.brandPinkDark, fontWeight: FontWeight.w900)),
          ],
        ),
      ),
    );
  }
}

class _Area {
  const _Area(this.name, this.clients);
  final String name;
  final List<_Client> clients;
}

class _Client {
  const _Client({
    required this.id,
    required this.name,
    required this.area,
    required this.regularDue,
    required this.sevenBySevenDue,
    required this.today,
    required this.status,
    required this.tone,
    required this.term,
    required this.due,
    this.completed = false,
    this.missed = 0,
    this.gcashTerm,
    this.note = '',
    this.catchUp,
    this.advance,
  });

  final String id;
  final String name;
  final String area;
  final double regularDue;
  final double sevenBySevenDue;
  final double today;
  final String status;
  final _Tone tone;
  final String term;
  final String due;
  final bool completed;
  final int missed;
  final String? gcashTerm;
  final String note;
  final String? catchUp;
  final String? advance;
}

enum _Tone { good, warning, danger, info }

String _money(double value) => '₱${value.toStringAsFixed(2)}';
String _shortMoney(double value) => value == value.roundToDouble()
    ? '₱${value.toStringAsFixed(0)}'
    : _money(value);

const List<_Area> _areas = [
  _Area('BALAYONG', [
    _Client(
      id: 'bal-ana',
      name: 'Ana Dela Cruz',
      area: 'BALAYONG',
      regularDue: 100,
      sevenBySevenDue: 50,
      today: 150,
      status: 'NOT COLLECTED',
      tone: _Tone.warning,
      term: 'Regular 120 days • 7x7 active',
      due: 'Regular due Dec 02 • 7x7 ongoing',
      gcashTerm: 'Pays at 5:30 PM after work',
      note: 'Usually sends exact ₱150 by GCash.',
    ),
    _Client(
      id: 'bal-maria',
      name: 'Maria Lopez',
      area: 'BALAYONG',
      regularDue: 200,
      sevenBySevenDue: 50,
      today: 250,
      status: 'CATCH-UP',
      tone: _Tone.danger,
      term: 'Regular 120 days • 7x7 active',
      due: 'Regular due Nov 26 • 7x7 ongoing',
      missed: 1,
      catchUp: 'Missed 1 payment — server recommends ₱250 today.',
      note: 'Ask about yesterday before collecting.',
    ),
    _Client(
      id: 'bal-liza',
      name: 'Liza Ramos',
      area: 'BALAYONG',
      regularDue: 0,
      sevenBySevenDue: 0,
      today: 0,
      status: 'ADV',
      tone: _Tone.good,
      term: 'Regular 120 days',
      due: 'Due Nov 30',
      completed: true,
      advance: 'Covered through Aug 18, 2026.',
      note: 'Do not collect today unless coverage changes.',
    ),
  ]),
  _Area('CALAHAN', [
    _Client(
      id: 'cal-rosa',
      name: 'Rosa Mendoza',
      area: 'CALAHAN',
      regularDue: 100,
      sevenBySevenDue: 50,
      today: 150,
      status: 'DONE',
      tone: _Tone.good,
      term: 'Regular 120 days • 7x7 active',
      due: 'Regular due Dec 05 • 7x7 ongoing',
      completed: true,
      note: 'Collected cash at 9:12 AM.',
    ),
    _Client(
      id: 'cal-joy',
      name: 'Joy Villanueva',
      area: 'CALAHAN',
      regularDue: 300,
      sevenBySevenDue: 50,
      today: 350,
      status: 'CATCH-UP',
      tone: _Tone.danger,
      term: 'Regular 120 days • 7x7 active',
      due: 'Regular due Nov 18 • 7x7 ongoing',
      missed: 2,
      catchUp: 'Missed 2 payments — server recommends triple Regular + today 7x7.',
      gcashTerm: 'Pays by GCash before 8:00 PM',
      note: 'Confirm GCash before marking complete.',
    ),
    _Client(
      id: 'cal-nena',
      name: 'Nena Flores',
      area: 'CALAHAN',
      regularDue: 100,
      sevenBySevenDue: 0,
      today: 100,
      status: 'PASS 1',
      tone: _Tone.warning,
      term: 'Regular 120 days',
      due: 'Due Dec 10',
      note: 'Yesterday: hospital. Revisit today.',
    ),
  ]),
  _Area('SAN ROQUE', [
    _Client(
      id: 'sr-ellen',
      name: 'Ellen Santos',
      area: 'SAN ROQUE',
      regularDue: 100,
      sevenBySevenDue: 50,
      today: 150,
      status: 'NOT COLLECTED',
      tone: _Tone.warning,
      term: 'Regular 120 days • 7x7 active',
      due: 'Regular due Dec 14 • 7x7 ongoing',
      note: 'Collect after lunch.',
    ),
    _Client(
      id: 'sr-cora',
      name: 'Cora Garcia',
      area: 'SAN ROQUE',
      regularDue: 100,
      sevenBySevenDue: 0,
      today: 100,
      status: 'GCASH PENDING',
      tone: _Tone.info,
      term: 'Regular 120 days',
      due: 'Due Dec 01',
      gcashTerm: 'Pays every collection day at 6:00 PM',
      note: 'Wait for proof before end-of-day review.',
    ),
    _Client(
      id: 'sr-beth',
      name: 'Beth Navarro',
      area: 'SAN ROQUE',
      regularDue: 100,
      sevenBySevenDue: 50,
      today: 150,
      status: 'DONE',
      tone: _Tone.good,
      term: 'Regular 120 days • 7x7 active',
      due: 'Regular due Dec 08 • 7x7 ongoing',
      completed: true,
      note: 'Collected cash at 11:05 AM.',
    ),
  ]),
];
