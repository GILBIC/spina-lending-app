import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_grouping.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/payments/collection_correction_repository.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collection_correction_page.dart';
import 'package:gilbic_mobile/src/features/collector/collection_entry_page.dart';

class CollectorRoutePage extends StatefulWidget {
  const CollectorRoutePage({
    required this.session,
    required this.loader,
    this.paymentRepository,
    this.correctionRepository,
    this.deviceIdentityProvider,
    this.deviceSequence,
    super.key,
  });

  final UserSession session;
  final CollectorRouteLoader loader;
  final PaymentSubmissionRepository? paymentRepository;
  final CollectionCorrectionRepository? correctionRepository;
  final DeviceIdentityProvider? deviceIdentityProvider;
  final CollectionDeviceSequence? deviceSequence;

  @override
  State<CollectorRoutePage> createState() => _CollectorRoutePageState();
}

class _CollectorRoutePageState extends State<CollectorRoutePage> {
  late final PaymentSubmissionRepository _paymentRepository;
  late final CollectionCorrectionRepository _correctionRepository;
  late final DeviceIdentityProvider _deviceIdentityProvider;
  late final CollectionDeviceSequence _deviceSequence;

  final Set<String> _expandedClients = <String>{};
  CollectorRouteLoadResult? _result;
  Object? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _paymentRepository =
        widget.paymentRepository ?? SpinaPaymentSubmissionRepository();
    _correctionRepository =
        widget.correctionRepository ?? SpinaCollectionCorrectionRepository();
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
      if (mounted) {
        setState(() => _result = result);
      }
    } on Object catch (error) {
      if (mounted) {
        setState(() => _error = error);
      }
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

  Future<void> _openCorrection(
    CollectorRouteLoadResult loaded,
    CollectorRouteEntry entry,
  ) async {
    final blockedReason = _correctionBlockedReason(loaded, entry);
    if (blockedReason != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(blockedReason)),
      );
      return;
    }

    final saved = await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (context) => CollectionCorrectionPage(
          session: widget.session,
          entry: entry,
          collectionDate: loaded.route.routeDate ?? DateTime.now(),
          repository: _correctionRepository,
          deviceIdentityProvider: _deviceIdentityProvider,
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
    if (_isSevenBySevenLoan(entry.loanType) &&
        !entry.sevenBySevenMobileEnabled) {
      return '7x7 mobile collection is disabled. Use SPINA desktop until the protected server allocator explicitly enables this route entry.';
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

  String? _correctionBlockedReason(
    CollectorRouteLoadResult loaded,
    CollectorRouteEntry entry,
  ) {
    if (loaded.isFromCache) {
      return 'Offline route copies are read-only. Reconnect and refresh before editing.';
    }
    if (!widget.session.permissions
        .contains('collection.correct.own_unremitted')) {
      return 'This account does not have collection correction permission.';
    }
    if (!entry.processedToday || entry.todayTransactionId == null) {
      return 'There is no collection entry to edit.';
    }
    if (entry.todayIsLocked) {
      return 'This collection is already remitted and permanently locked.';
    }
    if (!entry.canEditToday) {
      return 'Only the collector who recorded this entry may edit it before remittance.';
    }
    return null;
  }

  void _toggleClient(String clientId) {
    setState(() {
      if (!_expandedClients.add(clientId)) {
        _expandedClients.remove(clientId);
      }
    });
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
        padding: const EdgeInsets.fromLTRB(10, 8, 10, 16),
        children: [
          _CompactRouteSummary(
            result: loaded,
            route: route,
            clientCount: clientCount,
          ),
          if (loaded.warning != null) ...[
            const SizedBox(height: 8),
            MaterialBanner(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
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
            const SizedBox(height: 8),
            MaterialBanner(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              content: Text('The last refresh failed: $error'),
              actions: [
                TextButton(onPressed: _loadRoute, child: const Text('Retry')),
              ],
            ),
          ],
          const SizedBox(height: 8),
          if (route.entries.isEmpty)
            const Padding(
              padding: EdgeInsets.all(24),
              child: Text(
                'No clients are assigned to this route.',
                textAlign: TextAlign.center,
              ),
            )
          else
            for (final group in areaGroups) ...[
              _AreaLedgerSection(
                group: group,
                expandedClients: _expandedClients,
                blockedReasonFor: (entry) =>
                    _collectionBlockedReason(loaded, entry),
                correctionBlockedReasonFor: (entry) =>
                    _correctionBlockedReason(loaded, entry),
                onToggleClient: _toggleClient,
                onRecord: (entry) => _openCollection(loaded, entry),
                onEdit: (entry) => _openCorrection(loaded, entry),
              ),
              const SizedBox(height: 8),
            ],
          const SizedBox(height: 4),
          Text(
            'Tap a client to show notes, exact covered dates, recorder, and Edit access. Offline routes remain view-only.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _CompactRouteSummary extends StatelessWidget {
  const _CompactRouteSummary({
    required this.result,
    required this.route,
    required this.clientCount,
  });

  final CollectorRouteLoadResult result;
  final CollectorRoute route;
  final int clientCount;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final dateText = route.routeDate == null ? 'Saved route' : _date(route.routeDate!);
    final recorded = route.entries.where((entry) => entry.processedToday).length;

    return Container(
      decoration: BoxDecoration(
        color: result.isFromCache
            ? scheme.tertiaryContainer
            : scheme.primaryContainer,
        borderRadius: BorderRadius.circular(10),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                result.isFromCache ? Icons.cloud_off : Icons.cloud_done,
                size: 17,
              ),
              const SizedBox(width: 6),
              Text(
                result.isFromCache ? 'Offline copy' : 'Online route',
                style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
              ),
              const Spacer(),
              Text(dateText, style: Theme.of(context).textTheme.bodySmall),
            ],
          ),
          const SizedBox(height: 5),
          Row(
            children: [
              Expanded(
                child: Text(
                  '${route.collectorName} • $clientCount clients • '
                  '${route.entries.length} loans',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
              Text(
                _money(route.expectedTotal),
                style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
              ),
            ],
          ),
          const SizedBox(height: 2),
          Text(
            '$recorded recorded • Last sync ${_time(result.syncedAt)}',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _AreaLedgerSection extends StatelessWidget {
  const _AreaLedgerSection({
    required this.group,
    required this.expandedClients,
    required this.blockedReasonFor,
    required this.correctionBlockedReasonFor,
    required this.onToggleClient,
    required this.onRecord,
    required this.onEdit,
  });

  final CollectorRouteAreaGroup group;
  final Set<String> expandedClients;
  final String? Function(CollectorRouteEntry entry) blockedReasonFor;
  final String? Function(CollectorRouteEntry entry) correctionBlockedReasonFor;
  final void Function(String clientId) onToggleClient;
  final void Function(CollectorRouteEntry entry) onRecord;
  final void Function(CollectorRouteEntry entry) onEdit;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      decoration: BoxDecoration(
        border: Border.all(color: scheme.outlineVariant),
        borderRadius: BorderRadius.circular(8),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          Container(
            width: double.infinity,
            color: scheme.primaryContainer,
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    'AREA: ${group.area.toUpperCase()}',
                    style: Theme.of(context).textTheme.labelLarge?.copyWith(
                          fontWeight: FontWeight.w900,
                        ),
                  ),
                ),
                Text(
                  '${group.clientCount} clients • ${group.loanCount} loans • '
                  '${_money(group.expectedTotal)}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
          const _LedgerColumnHeader(),
          for (var index = 0; index < group.clients.length; index++) ...[
            if (index > 0) const Divider(height: 1),
            _ClientLedgerBlock(
              sequence: index + 1,
              client: group.clients[index],
              expanded: expandedClients.contains(group.clients[index].clientId),
              blockedReasonFor: blockedReasonFor,
              correctionBlockedReasonFor: correctionBlockedReasonFor,
              onToggle: () => onToggleClient(group.clients[index].clientId),
              onRecord: onRecord,
              onEdit: onEdit,
            ),
          ],
        ],
      ),
    );
  }
}

class _LedgerColumnHeader extends StatelessWidget {
  const _LedgerColumnHeader();

  @override
  Widget build(BuildContext context) {
    final style = Theme.of(context).textTheme.labelSmall?.copyWith(
          fontWeight: FontWeight.w700,
        );
    return Container(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      padding: const EdgeInsets.fromLTRB(38, 5, 8, 5),
      child: Row(
        children: [
          SizedBox(width: 62, child: Text('LOAN', style: style)),
          SizedBox(width: 62, child: Text('DAILY', style: style)),
          Expanded(child: Text('BALANCE', style: style)),
          SizedBox(
            width: 62,
            child: Text('ACTION', style: style, textAlign: TextAlign.center),
          ),
        ],
      ),
    );
  }
}

class _ClientLedgerBlock extends StatelessWidget {
  const _ClientLedgerBlock({
    required this.sequence,
    required this.client,
    required this.expanded,
    required this.blockedReasonFor,
    required this.correctionBlockedReasonFor,
    required this.onToggle,
    required this.onRecord,
    required this.onEdit,
  });

  final int sequence;
  final CollectorRouteClientGroup client;
  final bool expanded;
  final String? Function(CollectorRouteEntry entry) blockedReasonFor;
  final String? Function(CollectorRouteEntry entry) correctionBlockedReasonFor;
  final VoidCallback onToggle;
  final void Function(CollectorRouteEntry entry) onRecord;
  final void Function(CollectorRouteEntry entry) onEdit;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        InkWell(
          key: Key('route-client-${client.clientId}'),
          onTap: onToggle,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(9, 8, 7, 6),
            child: Row(
              children: [
                SizedBox(
                  width: 28,
                  child: Text(
                    '$sequence.',
                    style: Theme.of(context).textTheme.labelLarge,
                  ),
                ),
                Expanded(
                  child: Text(
                    client.clientName,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.labelLarge?.copyWith(
                          fontWeight: FontWeight.w900,
                        ),
                  ),
                ),
                Text(
                  '${client.processedLoanCount}/${client.loans.length}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                Icon(
                  expanded ? Icons.expand_less : Icons.expand_more,
                  size: 20,
                ),
              ],
            ),
          ),
        ),
        for (final loan in client.loans)
          _CompactLoanRow(
            entry: loan,
            expanded: expanded,
            blockedReason: blockedReasonFor(loan),
            correctionBlockedReason: correctionBlockedReasonFor(loan),
            onRecord: () => onRecord(loan),
            onEdit: () => onEdit(loan),
          ),
      ],
    );
  }
}

class _CompactLoanRow extends StatelessWidget {
  const _CompactLoanRow({
    required this.entry,
    required this.expanded,
    required this.blockedReason,
    required this.correctionBlockedReason,
    required this.onRecord,
    required this.onEdit,
  });

  final CollectorRouteEntry entry;
  final bool expanded;
  final String? blockedReason;
  final String? correctionBlockedReason;
  final VoidCallback onRecord;
  final VoidCallback onEdit;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      decoration: BoxDecoration(
        border: Border(top: BorderSide(color: scheme.outlineVariant)),
      ),
      padding: const EdgeInsets.fromLTRB(38, 6, 7, 7),
      child: Column(
        children: [
          Row(
            children: [
              SizedBox(
                width: 62,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _shortLoanName(entry.loanType),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.labelMedium?.copyWith(
                            fontWeight: FontWeight.w800,
                          ),
                    ),
                    Text(
                      _shortStatus(entry),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.labelSmall,
                    ),
                  ],
                ),
              ),
              SizedBox(
                width: 62,
                child: Text(
                  _moneyCompact(entry.dailyAmount),
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
              Expanded(
                child: Text(
                  _moneyCompact(entry.balance),
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                ),
              ),
              SizedBox(
                width: 62,
                height: 34,
                child: FilledButton(
                  key: Key('record-collection-${entry.id}'),
                  onPressed: blockedReason == null ? onRecord : null,
                  style: FilledButton.styleFrom(
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                    minimumSize: const Size(56, 34),
                    textStyle: Theme.of(context).textTheme.labelMedium,
                  ),
                  child: Text(_actionLabel(entry, blockedReason)),
                ),
              ),
            ],
          ),
          if (expanded) ...[
            const SizedBox(height: 7),
            Container(
              width: double.infinity,
              color: scheme.surfaceContainerHighest,
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 7),
              child: _LoanDetails(
                entry: entry,
                blockedReason: blockedReason,
                correctionBlockedReason: correctionBlockedReason,
                onEdit: onEdit,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _LoanDetails extends StatelessWidget {
  const _LoanDetails({
    required this.entry,
    required this.blockedReason,
    required this.correctionBlockedReason,
    required this.onEdit,
  });

  final CollectorRouteEntry entry;
  final String? blockedReason;
  final String? correctionBlockedReason;
  final VoidCallback onEdit;

  @override
  Widget build(BuildContext context) {
    final lines = <String>[
      'Status: ${entry.status}',
      'Missed payments: ${entry.passCount}',
      if (entry.lastPaymentDate != null)
        'Last payment: ${_date(entry.lastPaymentDate!)}',
      if (entry.processedToday && entry.todayAmount > 0)
        'Recorded amount: ${_moneyCompact(entry.todayAmount)}',
      if (entry.todayCoveredDates.isNotEmpty)
        'Exact covered dates: ${entry.todayCoveredDates.map(_date).join(', ')}',
      if (!entry.processedToday && entry.coveredDates.isNotEmpty)
        'Upcoming covered dates: ${entry.coveredDates.map(_date).join(', ')}',
      if (entry.processedToday) _todayResultLabel(entry.todayEntryType),
      if (entry.processedToday && entry.todayCollectorName.isNotEmpty)
        'Recorded by: ${entry.todayCollectorName}',
      if (entry.processedToday && entry.todayIsLocked)
        'Remittance status: Locked',
      if (entry.processedToday && entry.todayNote.isNotEmpty)
        'Entry note: ${entry.todayNote}',
      if (!entry.processedToday && entry.note.isNotEmpty)
        'Reason / note: ${entry.note}',
      if (blockedReason != null && !entry.processedToday) blockedReason!,
      if (blockedReason == null && entry.collectionMessage.isNotEmpty)
        entry.collectionMessage,
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var index = 0; index < lines.length; index++) ...[
          if (index > 0) const SizedBox(height: 3),
          Text(lines[index], style: Theme.of(context).textTheme.bodySmall),
        ],
        if (entry.processedToday) ...[
          const SizedBox(height: 8),
          if (correctionBlockedReason == null)
            OutlinedButton.icon(
              key: Key('edit-collection-${entry.todayTransactionId}'),
              onPressed: onEdit,
              icon: const Icon(Icons.edit_outlined, size: 18),
              label: const Text('Edit before remittance'),
            )
          else
            Text(
              correctionBlockedReason!,
              style: Theme.of(context).textTheme.bodySmall,
            ),
        ],
      ],
    );
  }
}

String _shortLoanName(String value) {
  return _isSevenBySevenLoan(value) ? '7x7' : value;
}

String _shortStatus(CollectorRouteEntry entry) {
  if (entry.processedToday) {
    if (entry.todayIsLocked) {
      return 'Remitted';
    }
    return switch (entry.todayEntryType.trim().toLowerCase()) {
      'pass' => 'Unable',
      'advance' => 'Covered',
      _ => 'Paid',
    };
  }
  if (_isSevenBySevenLoan(entry.loanType) &&
      !entry.sevenBySevenMobileEnabled) {
    return 'Desktop';
  }
  return entry.status;
}

String _actionLabel(CollectorRouteEntry entry, String? blockedReason) {
  if (entry.processedToday) {
    return entry.todayIsLocked ? 'Locked' : 'Done';
  }
  if (_isSevenBySevenLoan(entry.loanType) &&
      !entry.sevenBySevenMobileEnabled) {
    return 'Desk';
  }
  if (blockedReason != null) {
    return 'Locked';
  }
  return 'Pay';
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

String _time(DateTime value) {
  final local = value.toLocal();
  return '${local.hour.toString().padLeft(2, '0')}:'
      '${local.minute.toString().padLeft(2, '0')}';
}

String _money(double value) {
  final fixed = value.toStringAsFixed(2);
  final parts = fixed.split('.');
  return '${_groupDigits(parts.first)}.${parts.last}';
}

String _moneyCompact(double value) {
  final fixed = value.toStringAsFixed(2);
  final parts = fixed.split('.');
  return '₱${_groupDigits(parts.first)}.${parts.last}';
}

String _groupDigits(String digits) {
  final buffer = StringBuffer();
  for (var index = 0; index < digits.length; index += 1) {
    if (index > 0 && (digits.length - index) % 3 == 0) {
      buffer.write(',');
    }
    buffer.write(digits[index]);
  }
  return buffer.toString();
}