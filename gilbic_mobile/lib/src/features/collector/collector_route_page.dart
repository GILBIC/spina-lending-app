import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_repository.dart';

class CollectorRoutePage extends StatefulWidget {
  const CollectorRoutePage({
    required this.session,
    required this.repository,
    super.key,
  });

  final UserSession session;
  final CollectorRouteRepository repository;

  @override
  State<CollectorRoutePage> createState() => _CollectorRoutePageState();
}

class _CollectorRoutePageState extends State<CollectorRoutePage> {
  CollectorRoute? _route;
  Object? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadRoute();
  }

  Future<void> _loadRoute() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final route = await widget.repository.fetchToday(widget.session);
      if (!mounted) {
        return;
      }
      setState(() => _route = route);
    } on Object catch (error) {
      if (!mounted) {
        return;
      }
      setState(() => _error = error);
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Daily Route'),
        actions: [
          IconButton(
            tooltip: 'Refresh route',
            onPressed: _loading ? null : _loadRoute,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(child: _buildBody(context)),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_loading && _route == null) {
      return const Center(child: CircularProgressIndicator());
    }

    final error = _error;
    if (error != null && _route == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off, size: 48),
              const SizedBox(height: 12),
              Text(
                error.toString(),
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyLarge,
              ),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: _loadRoute,
                icon: const Icon(Icons.refresh),
                label: const Text('Try again'),
              ),
            ],
          ),
        ),
      );
    }

    final route = _route!;
    return RefreshIndicator(
      onRefresh: _loadRoute,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [
          _RouteHeader(route: route),
          if (error != null) ...[
            const SizedBox(height: 12),
            MaterialBanner(
              content: Text('The last refresh failed: $error'),
              actions: [
                TextButton(onPressed: _loadRoute, child: const Text('Retry')),
              ],
            ),
          ],
          const SizedBox(height: 16),
          if (route.entries.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'No clients are assigned to this route today.',
                  textAlign: TextAlign.center,
                ),
              ),
            )
          else
            ...route.entries.map(
              (entry) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: _RouteEntryCard(entry: entry),
              ),
            ),
          const SizedBox(height: 8),
          Text(
            'Read-only route. Official balances and collection permissions are controlled by the SPINA server.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _RouteHeader extends StatelessWidget {
  const _RouteHeader({required this.route});

  final CollectorRoute route;

  @override
  Widget build(BuildContext context) {
    final routeDate = route.routeDate;
    final dateText = routeDate == null
        ? 'Today'
        : '${routeDate.year.toString().padLeft(4, '0')}-'
            '${routeDate.month.toString().padLeft(2, '0')}-'
            '${routeDate.day.toString().padLeft(2, '0')}';

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              route.collectorName,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 4),
            Text('$dateText • ${route.entries.length} clients'),
            if (route.areas.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text('Areas: ${route.areas.join(', ')}'),
            ],
            const Divider(height: 24),
            Text(
              'Expected collection: ${_money(route.expectedTotal)}',
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ],
        ),
      ),
    );
  }
}

class _RouteEntryCard extends StatelessWidget {
  const _RouteEntryCard({required this.entry});

  final CollectorRouteEntry entry;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Text(
                    entry.clientName,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                const SizedBox(width: 8),
                Chip(label: Text(entry.status)),
              ],
            ),
            Text(
              [entry.area, entry.loanType]
                  .where((value) => value.isNotEmpty)
                  .join(' • '),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 18,
              runSpacing: 8,
              children: [
                _AmountLabel(label: 'Daily', value: entry.dailyAmount),
                _AmountLabel(label: 'Balance', value: entry.balance),
                Text('PASS: ${entry.passCount}'),
              ],
            ),
            if (entry.advanceUntil != null) ...[
              const SizedBox(height: 8),
              Text('Advance covered until ${_date(entry.advanceUntil!)}'),
            ],
            if (entry.lastPaymentDate != null) ...[
              const SizedBox(height: 4),
              Text('Last payment: ${_date(entry.lastPaymentDate!)}'),
            ],
            if (entry.note.isNotEmpty) ...[
              const Divider(height: 20),
              Text('Note: ${entry.note}'),
            ],
          ],
        ),
      ),
    );
  }
}

class _AmountLabel extends StatelessWidget {
  const _AmountLabel({required this.label, required this.value});

  final String label;
  final double value;

  @override
  Widget build(BuildContext context) {
    return Text('$label: ${_money(value)}');
  }
}

String _date(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}

String _money(double value) {
  final fixed = value.toStringAsFixed(2);
  final parts = fixed.split('.');
  final digits = parts.first;
  final buffer = StringBuffer();
  for (var index = 0; index < digits.length; index += 1) {
    if (index > 0 && (digits.length - index) % 3 == 0) {
      buffer.write(',');
    }
    buffer.write(digits[index]);
  }
  return '₱${buffer.toString()}.${parts.last}';
}
