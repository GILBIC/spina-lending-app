import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

/// Controlled CA4 visual fixture shown only from a real authenticated Collector
/// session in debug/review builds. Nothing on this page writes financial data.
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
            padding: EdgeInsets.only(right: 12),
            child: Center(child: _SyntheticBadge()),
          ),
        ],
      ),
      body: SafeArea(
        child: IndexedStack(
          index: _selectedIndex,
          children: const [_SyntheticRouteView(), _SyntheticMasterReview()],
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
                'Synthetic review only. Real remittance and tools remain in the authenticated Collector app.',
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
}

class _SyntheticRouteView extends StatefulWidget {
  const _SyntheticRouteView();

  @override
  State<_SyntheticRouteView> createState() => _SyntheticRouteViewState();
}

class _SyntheticRouteViewState extends State<_SyntheticRouteView> {
  final Set<String> _expanded = <String>{};

  Future<void> _openSplitPreview(_SyntheticClient client) async {
    final reviewed = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _SyntheticSplitSheet(client: client),
    );
    if (reviewed == true && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Synthetic review only — no payment was saved.'),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
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
          'This fixture shows the approved Collector information hierarchy. '
          'The finished route uses real authenticated backend data.',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ],
    );
  }

  Widget _areaCard(BuildContext context, _SyntheticArea area) {
    final remaining = area.clients.where((client) => !client.completed).length;
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
            padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 9),
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
                Text('${area.clients.length} clients • $remaining left'),
              ],
            ),
          ),
          const _LedgerHeader(),
          for (var index = 0; index < area.clients.length; index++) ...[
            if (index > 0) const Divider(height: 1),
            _clientRow(context, area.clients[index], index + 1),
          ],
        ],
      ),
    );
  }

  Widget _clientRow(
    BuildContext context,
    _SyntheticClient client,
    int sequence,
  ) {
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
                  child: Text(
                    '$sequence.',
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
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
                            _StatusChip(
                              label: 'MISSED ${client.missed}',
                              tone: _Tone.danger,
                            ),
                          if (client.gcashTerm != null)
                            const _StatusChip(
                              label: 'GCASH',
                              tone: _Tone.info,
                            ),
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
                      Icon(
                        expanded ? Icons.expand_less : Icons.expand_more,
                        size: 18,
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
                      Icon(
                        Icons.check_circle_rounded,
                        color: SpinaTheme.success,
                        size: 20,
                      ),
                      SizedBox(width: 7),
                      Expanded(
                        child: Text(
                          'Collection complete for today',
                          style: TextStyle(fontWeight: FontWeight.w700),
                        ),
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

class _SyntheticSplitSheet extends StatefulWidget {
  const _SyntheticSplitSheet({required this.client});

  final _SyntheticClient client;

  @override
  State<_SyntheticSplitSheet> createState() => _SyntheticSplitSheetState();
}

class _SyntheticSplitSheetState extends State<_SyntheticSplitSheet> {
  late final TextEditingController _controller;
  late double _entered;

  @override
  void initState() {
    super.initState();
    _entered = widget.client.today;
    _controller = TextEditingController(
      text: widget.client.today.toStringAsFixed(2),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final client = widget.client;
    final regular = _entered < client.regularDue
        ? _entered
        : client.regularDue;
    final remainder = (_entered - regular).clamp(0, double.infinity);
    final seven = remainder < client.sevenBySevenDue
        ? remainder
        : client.sevenBySevenDue;
    final exact = (_entered - client.today).abs() < 0.005;

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
              Text(
                '${client.area} • ${client.gcashTerm == null ? 'Cash' : 'GCash'}',
              ),
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
                controller: _controller,
                autofocus: true,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(
                  labelText: 'Amount received from client',
                  prefixText: '₱ ',
                ),
                onChanged: (value) {
                  final parsed = double.tryParse(
                    value.replaceAll(',', '').trim(),
                  );
                  setState(() => _entered = parsed ?? 0);
                },
              ),
              const SizedBox(height: 14),
              Text(
                'Automatic split preview',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 8),
              if (client.regularDue > 0)
                _SplitLine(
                  label: 'Regular',
                  due: client.regularDue,
                  allocated: regular,
                ),
              if (client.sevenBySevenDue > 0) ...[
                const SizedBox(height: 8),
                _SplitLine(
                  label: '7x7',
                  due: client.sevenBySevenDue,
                  allocated: seven,
                ),
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
                onPressed: () => Navigator.pop(context, true),
                icon: const Icon(Icons.check_circle_outline_rounded),
                label: const Text('Review confirmation'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SyntheticMasterReview extends StatelessWidget {
  const _SyntheticMasterReview();

  @override
  Widget build(BuildContext context) {
    final clients = _areas.expand((area) => area.clients).toList(growable: false);
    final open = clients.where((client) => !client.completed).toList(growable: false);
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
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      color: SpinaTheme.brandPinkDark,
                    ),
              ),
              const SizedBox(height: 5),
              const Text(
                'Before leaving the route, review everyone who is not complete across every assigned area.',
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
            Expanded(
              child: Text(
                'Who still needs action',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
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
      decoration: BoxDecoration(
        color: SpinaTheme.brandPinkSoft,
        borderRadius: BorderRadius.circular(999),
      ),
      child: const Text(
        'SYNTHETIC',
        style: TextStyle(
          color: SpinaTheme.brandPinkDark,
          fontWeight: FontWeight.w900,
          fontSize: 10,
        ),
      ),
    );
  }
}

class _RouteSummary extends StatelessWidget {
  const _RouteSummary();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: SpinaTheme.line),
      ),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Collector: Myra Santos',
            style: TextStyle(fontWeight: FontWeight.w900),
          ),
          Text('August 15, 2026 • Online route'),
          SizedBox(height: 10),
          Row(
            children: [
              Expanded(child: _SummaryTile(value: '7', label: 'Clients')),
              SizedBox(width: 6),
              Expanded(child: _SummaryTile(value: '2', label: 'Done')),
              SizedBox(width: 6),
              Expanded(child: _SummaryTile(value: '5', label: 'Review')),
            ],
          ),
        ],
      ),
    );
  }
}

class _AreaOrder extends StatelessWidget {
  const _AreaOrder();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: SpinaTheme.line),
      ),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Area arrangement', style: TextStyle(fontWeight: FontWeight.w900)),
          SizedBox(height: 5),
          Text('1  BALAYONG'),
          Text('2  CALAHAN'),
          Text('3  SAN ROQUE'),
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
          fontWeight: FontWeight.w900,
        );
    return Container(
      color: const Color(0xFFFFFAFC),
      padding: const EdgeInsets.fromLTRB(38, 6, 7, 6),
      child: Row(
        children: [
          Expanded(child: Text('CLIENT / STATUS', style: style)),
          SizedBox(
            width: 58,
            child: Text('REG', style: style, textAlign: TextAlign.center),
          ),
          SizedBox(
            width: 50,
            child: Text('7x7', style: style, textAlign: TextAlign.center),
          ),
          SizedBox(
            width: 62,
            child: Text('TODAY', style: style, textAlign: TextAlign.center),
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
      padding: const EdgeInsets.symmetric(vertical: 8),
      decoration: BoxDecoration(
        color: SpinaTheme.blush,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: [
          Text(value, style: const TextStyle(fontWeight: FontWeight.w900)),
          Text(label, style: Theme.of(context).textTheme.labelSmall),
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
      child: Text(
        value <= 0 ? '—' : _shortMoney(value),
        textAlign: TextAlign.center,
        style: const TextStyle(fontWeight: FontWeight.w700),
      ),
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

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.label, required this.tone});

  final String label;
  final _Tone tone;

  @override
  Widget build(BuildContext context) {
    final background = switch (tone) {
      _Tone.good => const Color(0xFFE8F6EF),
      _Tone.warning => const Color(0xFFFFF0DE),
      _Tone.danger => const Color(0xFFFFE7E4),
      _Tone.info => const Color(0xFFE9F1FF),
    };
    final foreground = switch (tone) {
      _Tone.good => SpinaTheme.success,
      _Tone.warning => const Color(0xFF97510D),
      _Tone.danger => Theme.of(context).colorScheme.error,
      _Tone.info => const Color(0xFF315C9B),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: foreground,
          fontWeight: FontWeight.w900,
          fontSize: 10,
        ),
      ),
    );
  }
}

class _AreaProgress extends StatelessWidget {
  const _AreaProgress({required this.area});

  final _SyntheticArea area;

  @override
  Widget build(BuildContext context) {
    final done = area.clients.where((client) => client.completed).length;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    area.name,
                    style: const TextStyle(fontWeight: FontWeight.w900),
                  ),
                ),
                Text('$done/${area.clients.length} done • ${area.clients.length - done} left'),
              ],
            ),
            const SizedBox(height: 8),
            LinearProgressIndicator(
              value: area.clients.isEmpty ? 0 : done / area.clients.length,
            ),
          ],
        ),
      ),
    );
  }
}

class _Outstanding extends StatelessWidget {
  const _Outstanding({required this.client});

  final _SyntheticClient client;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(
              client.missed > 0
                  ? Icons.priority_high_rounded
                  : Icons.person_outline_rounded,
              color: client.missed > 0
                  ? Theme.of(context).colorScheme.error
                  : SpinaTheme.brandPinkDark,
            ),
            const SizedBox(width: 9),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    client.name,
                    style: const TextStyle(fontWeight: FontWeight.w900),
                  ),
                  Text('${client.area} • ${client.status}'),
                  if (client.missed > 0)
                    Text(
                      'Missed ${client.missed} payment${client.missed == 1 ? '' : 's'}',
                      style: const TextStyle(fontWeight: FontWeight.w800),
                    ),
                  if (client.catchUp != null) Text(client.catchUp!),
                  if (client.gcashTerm != null)
                    Text('GCash: ${client.gcashTerm}'),
                  if (client.note.isNotEmpty) Text('Note: ${client.note}'),
                ],
              ),
            ),
            Text(
              _money(client.today),
              style: const TextStyle(
                color: SpinaTheme.brandPinkDark,
                fontWeight: FontWeight.w900,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SyntheticArea {
  const _SyntheticArea(this.name, this.clients);

  final String name;
  final List<_SyntheticClient> clients;
}

class _SyntheticClient {
  const _SyntheticClient({
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

const List<_SyntheticArea> _areas = [
  _SyntheticArea('BALAYONG', [
    _SyntheticClient(
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
    _SyntheticClient(
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
      catchUp: 'Needs the server-reviewed catch-up amount today.',
      note: 'Ask about yesterday before collecting.',
    ),
    _SyntheticClient(
      id: 'bal-ben',
      name: 'Ben Santos',
      area: 'BALAYONG',
      regularDue: 100,
      sevenBySevenDue: 0,
      today: 100,
      status: 'COLLECTED',
      tone: _Tone.good,
      term: 'Regular 120 days',
      due: 'Regular due Dec 08',
      completed: true,
    ),
  ]),
  _SyntheticArea('CALAHAN', [
    _SyntheticClient(
      id: 'cal-joy',
      name: 'Joy Villanueva',
      area: 'CALAHAN',
      regularDue: 100,
      sevenBySevenDue: 0,
      today: 300,
      status: 'CATCH-UP',
      tone: _Tone.danger,
      term: 'Regular 120 days',
      due: 'Regular due Nov 22',
      missed: 2,
      catchUp: 'Needs triple-day review before collection.',
    ),
    _SyntheticClient(
      id: 'cal-cora',
      name: 'Cora Garcia',
      area: 'CALAHAN',
      regularDue: 100,
      sevenBySevenDue: 50,
      today: 150,
      status: 'GCASH PENDING',
      tone: _Tone.info,
      term: 'Regular 120 days • 7x7 active',
      due: 'Regular due Dec 11 • 7x7 ongoing',
      gcashTerm: 'Pays every collection day by GCash.',
      note: 'Pays every collection day after 4 PM.',
    ),
  ]),
  _SyntheticArea('SAN ROQUE', [
    _SyntheticClient(
      id: 'sr-liza',
      name: 'Liza Ramos',
      area: 'SAN ROQUE',
      regularDue: 100,
      sevenBySevenDue: 0,
      today: 0,
      status: 'ADV',
      tone: _Tone.good,
      term: 'Regular 120 days',
      due: 'Regular due Dec 05',
      completed: true,
      advance: 'ADV covers today through Aug 17.',
    ),
    _SyntheticClient(
      id: 'sr-nina',
      name: 'Nina Reyes',
      area: 'SAN ROQUE',
      regularDue: 100,
      sevenBySevenDue: 0,
      today: 100,
      status: 'PASS / REVIEWED',
      tone: _Tone.warning,
      term: 'Regular 120 days',
      due: 'Regular due Dec 01',
      completed: true,
      note: 'Unable-to-pay reason recorded today.',
    ),
  ]),
];
