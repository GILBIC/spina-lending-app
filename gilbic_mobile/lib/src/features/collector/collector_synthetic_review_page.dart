import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

/// Controlled CA4 visual fixture shown only behind real authenticated Collector
/// access in debug/review builds. It never writes financial data.
class CollectorSyntheticReviewPage extends StatefulWidget {
  const CollectorSyntheticReviewPage({super.key});

  @override
  State<CollectorSyntheticReviewPage> createState() =>
      _CollectorSyntheticReviewPageState();
}

class _CollectorSyntheticReviewPageState
    extends State<CollectorSyntheticReviewPage> {
  int _tab = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_tab == 0 ? 'Daily Collection' : 'Master Review'),
        actions: const [
          Padding(
            padding: EdgeInsets.only(right: 12),
            child: Center(
              child: Chip(
                label: Text('SYNTHETIC'),
                visualDensity: VisualDensity.compact,
              ),
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: IndexedStack(
          index: _tab,
          children: const [_RouteFixture(), _MasterFixture()],
        ),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (index) {
          if (index < 2) {
            setState(() => _tab = index);
          }
        },
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.route_outlined),
            label: 'Route',
          ),
          NavigationDestination(
            icon: Icon(Icons.fact_check_outlined),
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

class _RouteFixture extends StatefulWidget {
  const _RouteFixture();

  @override
  State<_RouteFixture> createState() => _RouteFixtureState();
}

class _RouteFixtureState extends State<_RouteFixture> {
  final Set<String> _expanded = <String>{};

  Future<void> _reviewPayment(_Client client) async {
    final confirmed = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _SplitSheet(client: client),
    );
    if (confirmed == true && mounted) {
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
        const _HeaderCard(),
        const SizedBox(height: 10),
        const _AreaOrderCard(),
        const SizedBox(height: 10),
        for (final area in _areas) ...[
          _areaCard(area),
          const SizedBox(height: 10),
        ],
      ],
    );
  }

  Widget _areaCard(_Area area) {
    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: SpinaTheme.line),
      ),
      child: Column(
        children: [
          Container(
            color: SpinaTheme.brandPinkSoft,
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
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
                Text('${area.clients.length} clients'),
              ],
            ),
          ),
          const _Columns(),
          for (var i = 0; i < area.clients.length; i++) ...[
            if (i > 0) const Divider(height: 1),
            _client(area.clients[i], i + 1),
          ],
        ],
      ),
    );
  }

  Widget _client(_Client client, int number) {
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
            padding: const EdgeInsets.fromLTRB(8, 9, 6, 8),
            child: Row(
              children: [
                SizedBox(width: 28, child: Text('$number.')),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        client.name,
                        style: const TextStyle(fontWeight: FontWeight.w900),
                      ),
                      const SizedBox(height: 3),
                      Wrap(
                        spacing: 4,
                        children: [
                          _MiniChip(client.status),
                          if (client.missed > 0)
                            _MiniChip('MISSED ${client.missed}'),
                          if (client.gcash != null) const _MiniChip('GCASH'),
                        ],
                      ),
                    ],
                  ),
                ),
                SizedBox(
                  width: 56,
                  child: Text(
                    client.regular == 0 ? '—' : _short(client.regular),
                    textAlign: TextAlign.center,
                  ),
                ),
                SizedBox(
                  width: 46,
                  child: Text(
                    client.seven == 0 ? '—' : _short(client.seven),
                    textAlign: TextAlign.center,
                  ),
                ),
                SizedBox(
                  width: 58,
                  child: Text(
                    _short(client.today),
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      color: SpinaTheme.brandPinkDark,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
        if (expanded)
          Container(
            width: double.infinity,
            margin: const EdgeInsets.fromLTRB(36, 0, 8, 8),
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: const Color(0xFFFFFAFC),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: SpinaTheme.line),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Term: ${client.term}'),
                Text('Due: ${client.due}'),
                if (client.gcash != null) Text('GCash term: ${client.gcash}'),
                if (client.note.isNotEmpty) Text('Note: ${client.note}'),
                if (client.catchUp != null) Text('Catch-up: ${client.catchUp}'),
                if (client.advance != null) Text('Advance: ${client.advance}'),
                if (!client.completed) ...[
                  const SizedBox(height: 8),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      key: Key('synthetic-collect-${client.id}'),
                      onPressed: () => _reviewPayment(client),
                      child: Text('Collect ${_money(client.today)}'),
                    ),
                  ),
                ],
              ],
            ),
          ),
      ],
    );
  }
}

class _SplitSheet extends StatefulWidget {
  const _SplitSheet({required this.client});

  final _Client client;

  @override
  State<_SplitSheet> createState() => _SplitSheetState();
}

class _SplitSheetState extends State<_SplitSheet> {
  late final TextEditingController _controller;
  late double _entered;

  @override
  void initState() {
    super.initState();
    _entered = widget.client.today;
    _controller = TextEditingController(text: _entered.toStringAsFixed(2));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final client = widget.client;
    final regular = _entered < client.regular ? _entered : client.regular;
    final remainder = (_entered - regular).clamp(0.0, double.infinity).toDouble();
    final seven = remainder < client.seven ? remainder : client.seven;

    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(
          18,
          10,
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
              Text('${client.area} • expected ${_money(client.today)}'),
              const SizedBox(height: 12),
              TextField(
                key: const Key('synthetic-client-payment-amount'),
                controller: _controller,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(
                  labelText: 'Amount received from client',
                  prefixText: '₱ ',
                ),
                onChanged: (value) {
                  setState(() {
                    _entered = double.tryParse(value.replaceAll(',', '')) ?? 0;
                  });
                },
              ),
              const SizedBox(height: 14),
              Text(
                'Automatic split preview',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 8),
              if (client.regular > 0)
                _SplitRow(label: 'Regular', due: client.regular, amount: regular),
              if (client.seven > 0) ...[
                const SizedBox(height: 8),
                _SplitRow(label: '7x7', due: client.seven, amount: seven),
              ],
              const SizedBox(height: 10),
              Text(
                (_entered - client.today).abs() < 0.005
                    ? 'Exact match. Production re-checks both loans atomically on the server before saving.'
                    : 'Different amount. Production asks the server for the safe allocation instead of guessing on the phone.',
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

class _MasterFixture extends StatelessWidget {
  const _MasterFixture();

  @override
  Widget build(BuildContext context) {
    final clients = _areas.expand((area) => area.clients).toList();
    final open = clients.where((client) => !client.completed).toList();
    return ListView(
      padding: const EdgeInsets.fromLTRB(14, 10, 14, 24),
      children: [
        Container(
          padding: const EdgeInsets.all(15),
          decoration: BoxDecoration(
            color: SpinaTheme.brandPinkSoft,
            borderRadius: BorderRadius.circular(18),
          ),
          child: const Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'All-area collection check',
                style: TextStyle(
                  color: SpinaTheme.brandPinkDark,
                  fontWeight: FontWeight.w900,
                ),
              ),
              SizedBox(height: 5),
              Text('Review everyone who is not complete before leaving the route.'),
            ],
          ),
        ),
        const SizedBox(height: 14),
        Text('Area completion', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        for (final area in _areas) ...[
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Text(
                '${area.name}: ${area.clients.where((c) => c.completed).length}/${area.clients.length} done',
              ),
            ),
          ),
          const SizedBox(height: 6),
        ],
        const SizedBox(height: 8),
        Text(
          'Who still needs action',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 8),
        for (final client in open) ...[
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
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
                    ),
                  if (client.catchUp != null) Text(client.catchUp!),
                  if (client.gcash != null) Text('GCash: ${client.gcash}'),
                  if (client.note.isNotEmpty) Text('Note: ${client.note}'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 8),
        ],
      ],
    );
  }
}

class _HeaderCard extends StatelessWidget {
  const _HeaderCard();

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(13),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Collector: Myra Santos',
              style: TextStyle(fontWeight: FontWeight.w900),
            ),
            const Text('August 15, 2026 • Online route'),
            const SizedBox(height: 8),
            Text(
              'Old ledger structure + modern SPINA styling',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}

class _AreaOrderCard extends StatelessWidget {
  const _AreaOrderCard();

  @override
  Widget build(BuildContext context) {
    return const Card(
      child: Padding(
        padding: EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Area arrangement', style: TextStyle(fontWeight: FontWeight.w900)),
            SizedBox(height: 5),
            Text('1  BALAYONG'),
            Text('2  CALAHAN'),
            Text('3  SAN ROQUE'),
          ],
        ),
      ),
    );
  }
}

class _Columns extends StatelessWidget {
  const _Columns();

  @override
  Widget build(BuildContext context) {
    return Container(
      color: const Color(0xFFFFFAFC),
      padding: const EdgeInsets.fromLTRB(36, 5, 6, 5),
      child: const Row(
        children: [
          Expanded(child: Text('CLIENT / STATUS')),
          SizedBox(width: 56, child: Text('REG', textAlign: TextAlign.center)),
          SizedBox(width: 46, child: Text('7x7', textAlign: TextAlign.center)),
          SizedBox(width: 58, child: Text('TODAY', textAlign: TextAlign.center)),
        ],
      ),
    );
  }
}

class _MiniChip extends StatelessWidget {
  const _MiniChip(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
      decoration: BoxDecoration(
        color: SpinaTheme.brandPinkSoft,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        style: const TextStyle(
          color: SpinaTheme.brandPinkDark,
          fontSize: 10,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}

class _SplitRow extends StatelessWidget {
  const _SplitRow({
    required this.label,
    required this.due,
    required this.amount,
  });

  final String label;
  final double due;
  final double amount;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        border: Border.all(color: SpinaTheme.line),
        borderRadius: BorderRadius.circular(12),
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
            _money(amount),
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
    required this.regular,
    required this.seven,
    required this.today,
    required this.status,
    required this.term,
    required this.due,
    this.completed = false,
    this.missed = 0,
    this.gcash,
    this.note = '',
    this.catchUp,
    this.advance,
  });

  final String id;
  final String name;
  final String area;
  final double regular;
  final double seven;
  final double today;
  final String status;
  final String term;
  final String due;
  final bool completed;
  final int missed;
  final String? gcash;
  final String note;
  final String? catchUp;
  final String? advance;
}

String _money(double value) => '₱${value.toStringAsFixed(2)}';
String _short(double value) => '₱${value.toStringAsFixed(0)}';

const _areas = <_Area>[
  _Area('BALAYONG', [
    _Client(
      id: 'bal-ana',
      name: 'Ana Dela Cruz',
      area: 'BALAYONG',
      regular: 100,
      seven: 50,
      today: 150,
      status: 'NOT COLLECTED',
      term: 'Regular 120 days • 7x7 active',
      due: 'Regular due Dec 02 • 7x7 ongoing',
      gcash: 'Pays at 5:30 PM after work',
      note: 'Usually sends exact ₱150 by GCash.',
    ),
    _Client(
      id: 'bal-maria',
      name: 'Maria Lopez',
      area: 'BALAYONG',
      regular: 200,
      seven: 50,
      today: 250,
      status: 'CATCH-UP',
      term: 'Regular 120 days • 7x7 active',
      due: 'Regular due Nov 26 • 7x7 ongoing',
      missed: 1,
      catchUp: 'Needs the server-reviewed catch-up amount today.',
    ),
    _Client(
      id: 'bal-ben',
      name: 'Ben Santos',
      area: 'BALAYONG',
      regular: 100,
      seven: 0,
      today: 100,
      status: 'COLLECTED',
      term: 'Regular 120 days',
      due: 'Regular due Dec 08',
      completed: true,
    ),
  ]),
  _Area('CALAHAN', [
    _Client(
      id: 'cal-joy',
      name: 'Joy Villanueva',
      area: 'CALAHAN',
      regular: 100,
      seven: 0,
      today: 300,
      status: 'CATCH-UP',
      term: 'Regular 120 days',
      due: 'Regular due Nov 22',
      missed: 2,
      catchUp: 'Needs triple-day review before collection.',
    ),
    _Client(
      id: 'cal-cora',
      name: 'Cora Garcia',
      area: 'CALAHAN',
      regular: 100,
      seven: 50,
      today: 150,
      status: 'GCASH PENDING',
      term: 'Regular 120 days • 7x7 active',
      due: 'Regular due Dec 11 • 7x7 ongoing',
      gcash: 'Pays every collection day by GCash.',
      note: 'Pays every collection day after 4 PM.',
    ),
  ]),
  _Area('SAN ROQUE', [
    _Client(
      id: 'sr-liza',
      name: 'Liza Ramos',
      area: 'SAN ROQUE',
      regular: 100,
      seven: 0,
      today: 0,
      status: 'ADV',
      term: 'Regular 120 days',
      due: 'Regular due Dec 05',
      completed: true,
      advance: 'ADV covers today through Aug 17.',
    ),
    _Client(
      id: 'sr-nina',
      name: 'Nina Reyes',
      area: 'SAN ROQUE',
      regular: 100,
      seven: 0,
      today: 100,
      status: 'PASS / REVIEWED',
      term: 'Regular 120 days',
      due: 'Regular due Dec 01',
      completed: true,
      note: 'Unable-to-pay reason recorded today.',
    ),
  ]),
];
