import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/remittance/cross_remittance.dart';
import 'package:gilbic_mobile/src/core/remittance/cross_remittance_repository.dart';
import 'package:gilbic_mobile/src/core/time/spina_business_time.dart';

class OtherAreaCollectionSummaryPage extends StatefulWidget {
  const OtherAreaCollectionSummaryPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final CrossRemittanceRepository? repository;

  @override
  State<OtherAreaCollectionSummaryPage> createState() =>
      _OtherAreaCollectionSummaryPageState();
}

class _OtherAreaCollectionSummaryPageState
    extends State<OtherAreaCollectionSummaryPage> {
  late final CrossRemittanceRepository _repository;
  late final TextEditingController _filterController;

  List<CrossCollectionStatus> _records = const <CrossCollectionStatus>[];
  CrossCollectionCustodyStatus? _statusFilter;
  String? _errorMessage;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaCrossRemittanceRepository();
    _filterController = TextEditingController();
    _load();
  }

  @override
  void dispose() {
    _filterController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final records = await _repository.loadCollectionHistory(
        widget.session,
        deviceId: identity.installationId,
      );
      if (mounted) {
        setState(() => _records = records);
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() {
          _errorMessage = 'Other-area collection history could not be loaded.';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  List<CrossCollectionStatus> get _visibleRecords {
    final query = _filterController.text.trim().toLowerCase();
    return _records.where((record) {
      if (_statusFilter != null && record.custodyStatus != _statusFilter) {
        return false;
      }
      if (query.isEmpty) {
        return true;
      }
      final haystack = <String>[
        record.clientName,
        record.receiptNumber,
        record.loanType,
        record.area,
        record.assignedCollectorName,
        record.remittanceNumber,
        record.remittanceRecipientName,
      ].join(' ').toLowerCase();
      return haystack.contains(query);
    }).toList(growable: false);
  }

  Map<String, List<CrossCollectionStatus>> _groups(
    List<CrossCollectionStatus> records,
  ) {
    final groups = <String, List<CrossCollectionStatus>>{};
    for (final record in records) {
      final key = '${record.assignedCollectorName}\u0000${record.area}';
      groups.putIfAbsent(key, () => <CrossCollectionStatus>[]).add(record);
    }
    return groups;
  }

  @override
  Widget build(BuildContext context) {
    final visible = _visibleRecords;
    final groups = _groups(visible);
    final notRemitted = _records
        .where((item) =>
            item.custodyStatus == CrossCollectionCustodyStatus.notRemitted)
        .length;
    final awaiting = _records
        .where((item) =>
            item.custodyStatus == CrossCollectionCustodyStatus.awaitingAcceptance)
        .length;
    final accepted = _records
        .where(
            (item) => item.custodyStatus == CrossCollectionCustodyStatus.accepted)
        .length;

    return Scaffold(
      appBar: AppBar(
        title: const Text('My Other-Area Collections'),
        actions: [
          IconButton(
            key: const Key('refresh-other-area-collection-summary'),
            tooltip: 'Refresh',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: _loading && _records.isEmpty
            ? const Center(child: CircularProgressIndicator())
            : RefreshIndicator(
                onRefresh: _load,
                child: ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.all(14),
                  children: [
                    const Card(
                      child: Padding(
                        padding: EdgeInsets.all(14),
                        child: Text(
                          'These are official collections you recorded for clients assigned to another collector. Your Daily Route remains unchanged.',
                        ),
                      ),
                    ),
                    const SizedBox(height: 10),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        _CountChip(
                          key: const Key('other-area-count-not-remitted'),
                          label: 'Not yet remitted',
                          count: notRemitted,
                        ),
                        _CountChip(
                          key: const Key('other-area-count-awaiting'),
                          label: 'Awaiting acceptance',
                          count: awaiting,
                        ),
                        _CountChip(
                          key: const Key('other-area-count-accepted'),
                          label: 'Accepted',
                          count: accepted,
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      key: const Key('other-area-summary-filter'),
                      controller: _filterController,
                      onChanged: (_) => setState(() {}),
                      decoration: const InputDecoration(
                        labelText: 'Filter collections',
                        hintText: 'Client, receipt, area, or assigned collector',
                        prefixIcon: Icon(Icons.search),
                      ),
                    ),
                    const SizedBox(height: 8),
                    DropdownButtonFormField<CrossCollectionCustodyStatus?>(
                      key: const Key('other-area-summary-status-filter'),
                      initialValue: _statusFilter,
                      decoration: const InputDecoration(
                        labelText: 'Remittance status',
                        prefixIcon: Icon(Icons.compare_arrows),
                      ),
                      items: [
                        const DropdownMenuItem<CrossCollectionCustodyStatus?>(
                          value: null,
                          child: Text('All statuses'),
                        ),
                        for (final status in CrossCollectionCustodyStatus.values)
                          DropdownMenuItem<CrossCollectionCustodyStatus?>(
                            value: status,
                            child: Text(status.label),
                          ),
                      ],
                      onChanged: (value) => setState(() => _statusFilter = value),
                    ),
                    if (_errorMessage != null) ...[
                      const SizedBox(height: 10),
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Text(
                            _errorMessage!,
                            style: TextStyle(
                              color: Theme.of(context).colorScheme.error,
                            ),
                          ),
                        ),
                      ),
                    ],
                    const SizedBox(height: 12),
                    if (_records.isEmpty)
                      const Padding(
                        padding: EdgeInsets.all(28),
                        child: Text(
                          'No other-area collection has been recorded by this account yet.',
                          textAlign: TextAlign.center,
                        ),
                      )
                    else if (visible.isEmpty)
                      const Padding(
                        padding: EdgeInsets.all(28),
                        child: Text(
                          'No other-area collection matches the current filters.',
                          textAlign: TextAlign.center,
                        ),
                      )
                    else
                      for (final group in groups.entries)
                        _CollectionGroup(records: group.value),
                  ],
                ),
              ),
      ),
    );
  }
}

class _CountChip extends StatelessWidget {
  const _CountChip({required this.label, required this.count, super.key});

  final String label;
  final int count;

  @override
  Widget build(BuildContext context) {
    return Chip(label: Text('$label: $count'));
  }
}

class _CollectionGroup extends StatelessWidget {
  const _CollectionGroup({required this.records});

  final List<CrossCollectionStatus> records;

  @override
  Widget build(BuildContext context) {
    final first = records.first;
    final area = first.area.trim().isEmpty ? 'No area' : first.area.trim();
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ExpansionTile(
        initiallyExpanded: true,
        title: Text(first.assignedCollectorName),
        subtitle: Text('$area • ${records.length} entr${records.length == 1 ? 'y' : 'ies'}'),
        childrenPadding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
        children: [
          for (final record in records) _CollectionStatusRow(record: record),
        ],
      ),
    );
  }
}

class _CollectionStatusRow extends StatelessWidget {
  const _CollectionStatusRow({required this.record});

  final CrossCollectionStatus record;

  @override
  Widget build(BuildContext context) {
    final isPass = record.entryType.trim().toLowerCase() == 'pass';
    final eventLabel = isPass ? 'Unable to pay' : _money(record.amount);
    final collectionDate = record.collectionDate == null
        ? 'Unknown date'
        : _dateOnly(record.collectionDate!);
    return Container(
      key: Key('other-area-summary-${record.transactionId}'),
      width: double.infinity,
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(
                  record.clientName,
                  style: Theme.of(context).textTheme.titleSmall,
                ),
              ),
              Text(
                eventLabel,
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
            ],
          ),
          const SizedBox(height: 3),
          Text('${record.receiptNumber} • ${record.loanType} • $collectionDate'),
          const SizedBox(height: 6),
          Text(
            record.custodyStatus.label,
            key: Key('other-area-custody-${record.transactionId}'),
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
          Text(_custodyDetail(record, isPass: isPass)),
          if (record.remittanceNumber.isNotEmpty)
            Text('Remittance: ${record.remittanceNumber}'),
          if (record.acceptedAt != null)
            Text('Recorded: ${formatSpinaBusinessDateTime(record.acceptedAt)}'),
          if (record.submittedAt != null)
            Text('Submitted: ${formatSpinaBusinessDateTime(record.submittedAt)}'),
          if (record.receivedAt != null)
            Text('Accepted: ${formatSpinaBusinessDateTime(record.receivedAt)}'),
        ],
      ),
    );
  }
}

String _custodyDetail(CrossCollectionStatus record, {required bool isPass}) {
  if (isPass) {
    return switch (record.custodyStatus) {
      CrossCollectionCustodyStatus.notRemitted =>
        'Unable-to-pay record is still waiting for remittance.',
      CrossCollectionCustodyStatus.awaitingAcceptance =>
        'Record sent to ${_recipient(record)} and waiting for acceptance.',
      CrossCollectionCustodyStatus.accepted =>
        'Record accepted by ${_recipient(record)}.',
    };
  }
  return switch (record.custodyStatus) {
    CrossCollectionCustodyStatus.notRemitted =>
      'Cash remains under your custody.',
    CrossCollectionCustodyStatus.awaitingAcceptance =>
      'Cash remains under your custody until ${_recipient(record)} accepts.',
    CrossCollectionCustodyStatus.accepted =>
      'Cash custody transferred to ${_recipient(record)}.',
  };
}

String _recipient(CrossCollectionStatus record) {
  final name = record.remittanceRecipientName.trim();
  return name.isEmpty ? 'the remittance recipient' : name;
}

String _dateOnly(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}

String _money(double value) => '₱${value.toStringAsFixed(2)}';
