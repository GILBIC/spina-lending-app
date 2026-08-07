import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_operations.dart';
import 'package:gilbic_mobile/src/core/management/management_operations_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ManagementLoanOperationsPage extends StatefulWidget {
  const ManagementLoanOperationsPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ManagementOperationsRepository? repository;

  @override
  State<ManagementLoanOperationsPage> createState() =>
      _ManagementLoanOperationsPageState();
}

class _ManagementLoanOperationsPageState
    extends State<ManagementLoanOperationsPage> {
  late final ManagementOperationsRepository _repository;
  final TextEditingController _searchController = TextEditingController();
  ManagementOperationsOverview? _overview;
  String _status = 'all';
  String? _errorMessage;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaManagementOperationsRepository();
    _load();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final overview = await _repository.loadOverview(
        widget.session,
        deviceId: identity.installationId,
        query: _searchController.text,
        status: _status,
      );
      if (!mounted) {
        return;
      }
      setState(() => _overview = overview);
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() => _errorMessage = 'Loan Operations could not be loaded.');
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  void _clearSearch() {
    _searchController.clear();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Loan Operations'),
        actions: [
          IconButton(
            tooltip: 'Refresh operations',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(child: _buildBody()),
    );
  }

  Widget _buildBody() {
    final overview = _overview;
    if (_loading && overview == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_errorMessage != null && overview == null) {
      return _ErrorPanel(message: _errorMessage!, onRetry: _load);
    }
    if (overview == null) {
      return const SizedBox.shrink();
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.visibility_outlined),
                  const SizedBox(width: 12),
                  Expanded(child: Text(overview.notice)),
                ],
              ),
            ),
          ),
          if (_errorMessage != null) ...[
            const SizedBox(height: 10),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(
                  _errorMessage!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            ),
          ],
          const SizedBox(height: 12),
          _SummaryGrid(summary: overview.summary),
          const SizedBox(height: 16),
          TextField(
            key: const Key('management-operations-search'),
            controller: _searchController,
            textInputAction: TextInputAction.search,
            onSubmitted: (_) => _load(),
            decoration: InputDecoration(
              labelText: 'Search client, receipt, loan, or collector',
              prefixIcon: const Icon(Icons.search),
              suffixIcon: _searchController.text.trim().isEmpty
                  ? IconButton(
                      tooltip: 'Search',
                      onPressed: _loading ? null : _load,
                      icon: const Icon(Icons.arrow_forward),
                    )
                  : IconButton(
                      tooltip: 'Clear search',
                      onPressed: _loading ? null : _clearSearch,
                      icon: const Icon(Icons.clear),
                    ),
            ),
          ),
          const SizedBox(height: 10),
          DropdownButtonFormField<String>(
            key: const Key('management-operations-status-filter'),
            initialValue: _status,
            decoration: const InputDecoration(labelText: 'Collection status'),
            items: const [
              DropdownMenuItem(value: 'all', child: Text('All entries')),
              DropdownMenuItem(value: 'unremitted', child: Text('Unremitted')),
              DropdownMenuItem(
                value: 'submitted',
                child: Text('Remittance submitted'),
              ),
              DropdownMenuItem(value: 'received', child: Text('Received')),
              DropdownMenuItem(value: 'voided', child: Text('Voided')),
            ],
            onChanged: _loading
                ? null
                : (value) {
                    if (value != null && value != _status) {
                      setState(() => _status = value);
                      _load();
                    }
                  },
          ),
          const SizedBox(height: 18),
          Row(
            children: [
              Text(
                'Collection activity',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const Spacer(),
              Text('${overview.entries.length} shown'),
            ],
          ),
          const SizedBox(height: 8),
          if (overview.entries.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'No collection activity matches the selected filter.',
                  textAlign: TextAlign.center,
                ),
              ),
            )
          else
            for (final entry in overview.entries) ...[
              _OperationEntryCard(entry: entry),
              const SizedBox(height: 10),
            ],
          const SizedBox(height: 18),
          Row(
            children: [
              Text(
                'Corrections & voids',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const Spacer(),
              Text('${overview.audits.length} recent'),
            ],
          ),
          const SizedBox(height: 8),
          if (overview.audits.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(20),
                child: Text(
                  'No correction or void audit activity has been recorded.',
                  textAlign: TextAlign.center,
                ),
              ),
            )
          else
            for (final event in overview.audits) ...[
              _AuditCard(event: event),
              const SizedBox(height: 8),
            ],
        ],
      ),
    );
  }
}

class _SummaryGrid extends StatelessWidget {
  const _SummaryGrid({required this.summary});

  final ManagementOperationsSummary summary;

  @override
  Widget build(BuildContext context) {
    final dateLabel = summary.latestCollectionDate == null
        ? 'No collections yet'
        : 'Latest day ${_date(summary.latestCollectionDate!)}';
    final items = <_MetricData>[
      _MetricData(
        'Latest collections',
        _money(summary.latestDayAmount),
        dateLabel,
        Icons.payments_outlined,
      ),
      _MetricData(
        'Payments / unable',
        '${summary.latestDayPaymentCount} / ${summary.latestDayUnableToPayCount}',
        dateLabel,
        Icons.receipt_long,
      ),
      _MetricData(
        'Unremitted cash',
        _money(summary.unremittedAmount),
        '${summary.unremittedEntryCount} entries',
        Icons.account_balance_wallet_outlined,
      ),
      _MetricData(
        'Pending remittance',
        _money(summary.pendingRemittanceAmount),
        '${summary.pendingRemittanceCount} remittances',
        Icons.hourglass_top,
      ),
      _MetricData(
        'Received cash',
        _money(summary.receivedRemittanceAmount),
        '${summary.receivedRemittanceCount} remittances',
        Icons.verified_outlined,
      ),
      _MetricData(
        'Corrections / voids',
        '${summary.correctionCount} / ${summary.voidCount}',
        'Permanent audit records',
        Icons.fact_check_outlined,
      ),
    ];
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: items.length,
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        mainAxisExtent: 116,
        crossAxisSpacing: 10,
        mainAxisSpacing: 10,
      ),
      itemBuilder: (context, index) => _MetricCard(data: items[index]),
    );
  }
}

class _MetricData {
  const _MetricData(this.label, this.value, this.detail, this.icon);

  final String label;
  final String value;
  final String detail;
  final IconData icon;
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({required this.data});

  final _MetricData data;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(data.icon, size: 21),
            const Spacer(),
            Text(
              data.value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            Text(data.label, maxLines: 1, overflow: TextOverflow.ellipsis),
            Text(
              data.detail,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}

class _OperationEntryCard extends StatelessWidget {
  const _OperationEntryCard({required this.entry});

  final ManagementOperationEntry entry;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: Key('management-operation-${entry.transactionId}'),
      clipBehavior: Clip.antiAlias,
      child: ExpansionTile(
        leading: Icon(
          entry.entryType == 'pass' ? Icons.event_busy : Icons.receipt_long,
        ),
        title: Text(entry.clientName),
        subtitle: Text('${entry.clientCode} • ${entry.loanTypeName}'),
        trailing: Chip(label: Text(entry.statusLabel)),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        children: [
          _DetailRow(label: 'Receipt', value: entry.receiptNumber),
          _DetailRow(label: 'Loan', value: entry.loanNumber),
          _DetailRow(label: 'Collector', value: entry.collectorName),
          _DetailRow(label: 'Collection date', value: _date(entry.collectionDate)),
          _DetailRow(label: 'Entry type', value: _titleCase(entry.entryType)),
          _DetailRow(label: 'Amount', value: _money(entry.amount)),
          _DetailRow(
            label: 'Official balance',
            value: _money(entry.officialBalance),
          ),
          _DetailRow(
            label: 'Covered dates',
            value: entry.coveredDates.isEmpty
                ? 'None'
                : entry.coveredDates.map(_date).join(', '),
          ),
          _DetailRow(label: 'Edit version', value: '${entry.editVersion}'),
          if (entry.remittanceNumber != null)
            _DetailRow(
              label: 'Remittance',
              value: entry.remittanceNumber!,
            ),
          if (entry.voidReason != null)
            _DetailRow(label: 'Void reason', value: entry.voidReason!),
          _DetailRow(label: 'Recorded', value: _dateTime(entry.acceptedAt)),
        ],
      ),
    );
  }
}

class _AuditCard extends StatelessWidget {
  const _AuditCard({required this.event});

  final ManagementOperationAudit event;

  @override
  Widget build(BuildContext context) {
    final isVoid = event.eventType.toLowerCase() == 'void';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(isVoid ? Icons.block : Icons.edit_note),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    isVoid ? 'Voided collection' : 'Corrected collection',
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                ),
                Text(_dateTime(event.happenedAt)),
              ],
            ),
            const SizedBox(height: 8),
            Text('${event.clientName} • ${event.loanNumber}'),
            Text('Receipt: ${event.receiptNumber}'),
            Text('By: ${event.actorName}'),
            const SizedBox(height: 5),
            Text('Reason: ${event.reason}'),
          ],
        ),
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(width: 112, child: Text(label)),
          Expanded(child: Text(value, textAlign: TextAlign.right)),
        ],
      ),
    );
  }
}

class _ErrorPanel extends StatelessWidget {
  const _ErrorPanel({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.error_outline,
              size: 48,
              color: Theme.of(context).colorScheme.error,
            ),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Try again'),
            ),
          ],
        ),
      ),
    );
  }
}

String _money(double value) {
  final parts = value.toStringAsFixed(2).split('.');
  final whole = parts.first.replaceAllMapped(
    RegExp(r'\B(?=(\d{3})+(?!\d))'),
    (_) => ',',
  );
  return '₱$whole.${parts.last}';
}

String _date(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}

String _dateTime(DateTime value) {
  final local = value.toLocal();
  return '${_date(local)} '
      '${local.hour.toString().padLeft(2, '0')}:'
      '${local.minute.toString().padLeft(2, '0')}';
}

String _titleCase(String value) {
  final normalized = value.trim();
  if (normalized.isEmpty) {
    return 'Unknown';
  }
  return normalized
      .split(RegExp(r'\s+'))
      .map((part) => '${part[0].toUpperCase()}${part.substring(1)}')
      .join(' ');
}
