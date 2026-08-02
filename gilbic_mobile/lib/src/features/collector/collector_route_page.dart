import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_grouping.dart';
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
    if (entry.processedToday) {
      return "Today's collection has already been recorded.";
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
    final areaGroups = groupCollectorRoute(route);
    final clientCount = areaGroups.fold<int>(
      0,
      (total, group) => total + group.clientCount,
    );

    return RefreshIndicator(
      onRefresh: _loadRoute,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [
          _RouteSyncStatus(result: loaded),
          const SizedBox(height: 12),
          _RouteHeader(route: route, clientCount: clientCount),
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
            for (final group in areaGroups) ...[
              _AreaLedgerSection(
                group: group,
                blockedReasonFor: (entry) =>
                    _collectionBlockedReason(loaded, entry),
                onRecord: (entry) => _openCollection(loaded, entry),
              ),
              const SizedBox(height: 12),
            ],
          const SizedBox(height: 4),
          Text(
            'Offline routes are view-only. Online payments, covered dates, and unable-to-pay reasons are sent directly to SPINA. Official balances and receipts remain server-controlled.',
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
  const _RouteHeader({required this.route, required this.clientCount});

  final CollectorRoute route;
  final int clientCount;

  @override
  Widget build(BuildContext context) {
    final routeDate = route.routeDate;
    final dateText = routeDate == null ? 'Saved route' : _date(routeDate);
    final recordedCount =
        route.entries.where((entry) => entry.processedToday).length;

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
            Text(
              '$dateText • $clientCount clients • ${route.entries.length} loans',
            ),
            if (route.areas.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text('Areas: ${route.areas.join(', ')}'),
            ],
            const Divider(height: 24),
            Text(
              'Expected collection: ${_money(route.expectedTotal)}',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 4),
            Text('Recorded loan entries today: $recordedCount'),
          ],
        ),
      ),
    );
  }
}

class _AreaLedgerSection extends StatelessWidget {
  const _AreaLedgerSection({
    required this.group,
    required this.blockedReasonFor,
    required this.onRecord,
  });

  final CollectorRouteAreaGroup group;
  final String? Function(CollectorRouteEntry entry) blockedReasonFor;
  final void Function(CollectorRouteEntry entry) onRecord;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          Container(
            width: double.infinity,
            color: scheme.primaryContainer,
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    'AREA: ${group.area.toUpperCase()}',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          color: scheme.onPrimaryContainer,
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                ),
                Text(
                  '${group.clientCount} clients',
                  style: TextStyle(color: scheme.onPrimaryContainer),
                ),
              ],
            ),
          ),
          Container(
            width: double.infinity,
            color: scheme.surfaceContainerHighest,
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            child: Text(
              '${group.loanCount} loans • Expected ${_money(group.expectedTotal)}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
          for (var index = 0; index < group.clients.length; index++) ...[
            if (index > 0) const Divider(height: 1),
            _ClientLedgerBlock(
              sequence: index + 1,
              client: group.clients[index],
              blockedReasonFor: blockedReasonFor,
              onRecord: onRecord,
            ),
          ],
        ],
      ),
    );
  }
}

class _ClientLedgerBlock extends StatelessWidget {
  const _ClientLedgerBlock({
    required this.sequence,
    required this.client,
    required this.blockedReasonFor,
    required this.onRecord,
  });

  final int sequence;
  final CollectorRouteClientGroup client;
  final String? Function(CollectorRouteEntry entry) blockedReasonFor;
  final void Function(CollectorRouteEntry entry) onRecord;

  @override
  Widget build(BuildContext context) {
    return Padding(
      key: Key('route-client-${client.clientId}'),
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(
                width: 28,
                child: Text(
                  '$sequence.',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              Expanded(
                child: Text(
                  client.clientName,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                ),
              ),
              const SizedBox(width: 8),
              Text(
                '${client.processedLoanCount}/${client.loans.length} recorded',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
          const SizedBox(height: 8),
          for (var index = 0; index < client.loans.length; index++) ...[
            if (index > 0) const Divider(height: 18),
            _LoanLedgerRow(
              entry: client.loans[index],
              blockedReason: blockedReasonFor(client.loans[index]),
              onRecord: () => onRecord(client.loans[index]),
            ),
          ],
        ],
      ),
    );
  }
}

class _LoanLedgerRow extends StatelessWidget {
  const _LoanLedgerRow({
    required this.entry,
    required this.blockedReason,
    required this.onRecord,
  });

  final CollectorRouteEntry entry;
  final String? blockedReason;
  final VoidCallback onRecord;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Expanded(
                child: Text(
                  entry.loanType,
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                ),
              ),
              const SizedBox(width: 8),
              Chip(
                visualDensity: VisualDensity.compact,
                label: Text(entry.status),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Wrap(
            spacing: 16,
            runSpacing: 4,
            children: [
              Text('Daily ${_money(entry.dailyAmount)}'),
              Text('Balance ${_money(entry.balance)}'),
              Text('Missed ${entry.passCount}'),
            ],
          ),
          if (entry.advanceUntil != null) ...[
            const SizedBox(height: 4),
            Text('Covered through ${_date(entry.advanceUntil!)}'),
          ],
          if (entry.lastPaymentDate != null) ...[
            const SizedBox(height: 4),
            Text('Last payment ${_date(entry.lastPaymentDate!)}'),
          ],
          if (entry.processedToday) ...[
            const SizedBox(height: 4),
            Text(
              _todayResultLabel(entry.todayEntryType),
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
          if (entry.note.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text('Reason / note: ${entry.note}'),
          ],
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerLeft,
            child: FilledButton.tonalIcon(
              key: Key('record-collection-${entry.id}'),
              onPressed: blockedReason == null ? onRecord : null,
              icon: const Icon(Icons.payments_outlined),
              label: const Text('Record collection'),
            ),
          ),
          if (blockedReason != null) ...[
            const SizedBox(height: 6),
            Text(
              blockedReason!,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ] else if (entry.collectionMessage.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(
              entry.collectionMessage,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ],
      ),
    );
  }
}

String _todayResultLabel(String value) {
  return switch (value.trim().toLowerCase()) {
    'pass' => 'Unable-to-pay reason recorded today.',
    'advance' => 'Covered-date payment recorded today.',
    _ => 'Payment recorded today.',
  };
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
