import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collection_entry_page.dart';

class CollectorRoutePage extends StatefulWidget {
  const CollectorRoutePage({
    required this.session,
    required this.loader,
    this.paymentRepository,
    this.deviceIdentityProvider,
    this.deviceSequence,
    super.key,
  });

  final UserSession session;
  final CollectorRouteLoader loader;
  final PaymentSubmissionRepository? paymentRepository;
  final DeviceIdentityProvider? deviceIdentityProvider;
  final CollectionDeviceSequence? deviceSequence;

  @override
  State<CollectorRoutePage> createState() => _CollectorRoutePageState();
}

class _CollectorRoutePageState extends State<CollectorRoutePage> {
  late final PaymentSubmissionRepository _paymentRepository;
  late final DeviceIdentityProvider _deviceIdentityProvider;
  late final CollectionDeviceSequence _deviceSequence;

  CollectorRouteLoadResult? _result;
  Object? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _paymentRepository =
        widget.paymentRepository ?? SpinaPaymentSubmissionRepository();
    _deviceIdentityProvider =
        widget.deviceIdentityProvider ?? DeviceIdentityProvider();
    _deviceSequence =
        widget.deviceSequence ?? SecureCollectionDeviceSequence();
    _loadRoute();
  }

  Future<void> _loadRoute() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await widget.loader.loadToday(widget.session);
      if (!mounted) {
        return;
      }
      setState(() => _result = result);
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

  Future<void> _openCollection(
    CollectorRouteLoadResult loaded,
    CollectorRouteEntry entry,
  ) async {
    final blockedReason = _collectionBlockedReason(loaded, entry);
    if (blockedReason != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(blockedReason)),
      );
      return;
    }

    final saved = await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (context) => CollectionEntryPage(
          session: widget.session,
          entry: entry,
          repository: _paymentRepository,
          deviceIdentityProvider: _deviceIdentityProvider,
          deviceSequence: _deviceSequence,
          collectionDate: loaded.route.routeDate,
        ),
      ),
    );
    if (saved == true && mounted) {
      await _loadRoute();
    }
  }

  String? _collectionBlockedReason(
    CollectorRouteLoadResult loaded,
    CollectorRouteEntry entry,
  ) {
    if (loaded.isFromCache) {
      return 'Offline route copies are read-only. Reconnect and refresh before recording a collection.';
    }
    if (!widget.session.permissions.contains('collection.create')) {
      return 'This account does not have permission to record collections.';
    }
    if (_isSevenBySevenLoan(entry.loanType)) {
      return '7x7 mobile collection is disabled. Use SPINA desktop until the dedicated allocator is verified.';
    }
    if (!entry.canCollectMobile || !entry.canEnterPayment) {
      return entry.collectionMessage.isNotEmpty
          ? entry.collectionMessage
          : 'Use SPINA desktop for this loan.';
    }
    if (entry.loanId.trim().isEmpty || entry.routeRevision == null) {
      return 'Refresh the route before recording this collection.';
    }
    return null;
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
    final result = _result;
    if (_loading && result == null) {
      return const Center(child: CircularProgressIndicator());
    }

    final error = _error;
    if (error != null && result == null) {
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

    final loaded = result!;
    final route = loaded.route;
    return RefreshIndicator(
      onRefresh: _loadRoute,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [
          _RouteSyncStatus(result: loaded),
          const SizedBox(height: 12),
          _RouteHeader(route: route),
          if (loaded.warning != null) ...[
            const SizedBox(height: 12),
            MaterialBanner(
              content: Text(loaded.warning!),
              leading: Icon(
                loaded.isFromCache ? Icons.cloud_off : Icons.storage,
              ),
              actions: [
                TextButton(onPressed: _loadRoute, child: const Text('Retry')),
              ],
            ),
          ],
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
                  'No clients are assigned to this route.',
                  textAlign: TextAlign.center,
                ),
              ),
            )
          else
            ...route.entries.map((entry) {
              final blockedReason = _collectionBlockedReason(loaded, entry);
              return Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: _RouteEntryCard(
                  entry: entry,
                  blockedReason: blockedReason,
                  onRecord: () => _openCollection(loaded, entry),
                ),
              );
            }),
          const SizedBox(height: 8),
          Text(
            'Read-only route when offline. Online Payment, ADV, and PASS entries are sent directly to SPINA. Official balances and receipts remain server-controlled.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _RouteSyncStatus extends StatelessWidget {
  const _RouteSyncStatus({required this.result});

  final CollectorRouteLoadResult result;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final background = result.isFromCache
        ? scheme.tertiaryContainer
        : scheme.primaryContainer;
    final foreground = result.isFromCache
        ? scheme.onTertiaryContainer
        : scheme.onPrimaryContainer;

    return Semantics(
      label: result.isFromCache ? 'Offline route copy' : 'Online route',
      child: Card(
        color: background,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              Icon(
                result.isFromCache ? Icons.cloud_off : Icons.cloud_done,
                color: foreground,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      result.isFromCache ? 'Offline copy' : 'Online route',
                      style: Theme.of(context).textTheme.titleSmall?.copyWith(
                            color: foreground,
                            fontWeight: FontWeight.w700,
                          ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Last synchronized ${_dateTime(result.syncedAt)}',
                      style: TextStyle(color: foreground),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
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
    final dateText = routeDate == null ? 'Saved route' : _date(routeDate);

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
  const _RouteEntryCard({
    required this.entry,
    required this.blockedReason,
    required this.onRecord,
  });

  final CollectorRouteEntry entry;
  final String? blockedReason;
  final VoidCallback onRecord;

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
            const SizedBox(height: 14),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                key: Key('record-collection-${entry.id}'),
                onPressed: blockedReason == null ? onRecord : null,
                icon: const Icon(Icons.payments_outlined),
                label: const Text('Record Payment / ADV / PASS'),
              ),
            ),
            if (blockedReason != null) ...[
              const SizedBox(height: 8),
              Text(
                blockedReason!,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ] else if (entry.collectionMessage.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                entry.collectionMessage,
                style: Theme.of(context).textTheme.bodySmall,
              ),
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

bool _isSevenBySevenLoan(String value) {
  final normalized = value.toLowerCase().replaceAll(' ', '');
  return normalized.contains('7x7') || normalized.contains('7×7');
}

String _date(DateTime value) {
  final local = value.toLocal();
  return '${local.year.toString().padLeft(4, '0')}-'
      '${local.month.toString().padLeft(2, '0')}-'
      '${local.day.toString().padLeft(2, '0')}';
}

String _dateTime(DateTime value) {
  final local = value.toLocal();
  return '${_date(local)} '
      '${local.hour.toString().padLeft(2, '0')}:'
      '${local.minute.toString().padLeft(2, '0')}';
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
