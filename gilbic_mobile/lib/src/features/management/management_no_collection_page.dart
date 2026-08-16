import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_loan.dart';
import 'package:gilbic_mobile/src/core/management/management_loan_repository.dart';
import 'package:gilbic_mobile/src/core/management/management_no_collection.dart';
import 'package:gilbic_mobile/src/core/management/management_no_collection_preview.dart';
import 'package:gilbic_mobile/src/core/management/management_no_collection_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ManagementNoCollectionPage extends StatefulWidget {
  const ManagementNoCollectionPage({
    required this.session,
    this.loanRepository,
    this.repository,
    this.deviceIdentityProvider,
    super.key,
  });

  final UserSession session;
  final ManagementLoanRepository? loanRepository;
  final ManagementNoCollectionRepository? repository;
  final DeviceIdentityProvider? deviceIdentityProvider;

  @override
  State<ManagementNoCollectionPage> createState() =>
      _ManagementNoCollectionPageState();
}

class _ManagementNoCollectionPageState
    extends State<ManagementNoCollectionPage> {
  late final ManagementLoanRepository _loanRepository;
  late final ManagementNoCollectionRepository _repository;
  late final DeviceIdentityProvider _deviceIdentityProvider;

  final _searchController = TextEditingController();
  final _reasonController = TextEditingController();

  List<ManagementLoan> _searchResults = const <ManagementLoan>[];
  ManagementLoan? _selectedLoan;
  ManagementNoCollectionLoanState? _loanState;
  ManagementNoCollectionPreview? _preview;
  ManagementNoCollectionAdjustmentResult? _lastResult;
  DateTime? _selectedDate;
  String? _error;
  bool _searching = false;
  bool _loadingState = false;
  bool _previewing = false;
  bool _saving = false;

  bool get _hasPermission =>
      widget.session.permissions.contains('lending.no_collection.manage');

  @override
  void initState() {
    super.initState();
    _loanRepository = widget.loanRepository ?? SpinaManagementLoanRepository();
    _repository =
        widget.repository ?? SpinaManagementNoCollectionRepository();
    _deviceIdentityProvider =
        widget.deviceIdentityProvider ?? DeviceIdentityProvider();
  }

  @override
  void dispose() {
    _searchController.dispose();
    _reasonController.dispose();
    super.dispose();
  }

  Future<String> _deviceId() async {
    final identity = await _deviceIdentityProvider.load();
    return identity.installationId;
  }

  Future<void> _searchLoans() async {
    if (_searching || !_hasPermission) {
      return;
    }
    final query = _searchController.text.trim().toLowerCase();
    setState(() {
      _searching = true;
      _error = null;
      _searchResults = const <ManagementLoan>[];
    });
    try {
      final portfolio = await _loanRepository.loadPortfolio(widget.session);
      final results = portfolio.loans
          .where((loan) => loan.status.toLowerCase() == 'active')
          .where((loan) {
            if (query.isEmpty) {
              return true;
            }
            return <String>[
              loan.loanNumber,
              loan.clientName,
              loan.clientCode,
              loan.area,
              loan.loanType,
            ].any((value) => value.toLowerCase().contains(query));
          })
          .take(30)
          .toList(growable: false);
      if (mounted) {
        setState(() => _searchResults = results);
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _error = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() => _error = 'Loan search could not be completed.');
      }
    } finally {
      if (mounted) {
        setState(() => _searching = false);
      }
    }
  }

  Future<void> _selectLoan(ManagementLoan loan) async {
    if (_loadingState) {
      return;
    }
    setState(() {
      _selectedLoan = loan;
      _loanState = null;
      _preview = null;
      _lastResult = null;
      _selectedDate = null;
      _reasonController.clear();
      _loadingState = true;
      _error = null;
    });
    try {
      final state = await _repository.loadLoanState(
        widget.session,
        deviceId: await _deviceId(),
        loanId: loan.loanId,
      );
      if (mounted) {
        setState(() => _loanState = state);
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _error = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() => _error = 'The No Collection schedule could not be loaded.');
      }
    } finally {
      if (mounted) {
        setState(() => _loadingState = false);
      }
    }
  }

  Future<void> _reloadState() async {
    final loan = _selectedLoan;
    if (loan == null) {
      return;
    }
    await _selectLoan(loan);
  }

  Future<void> _chooseDate() async {
    final state = _loanState;
    if (state == null || _saving) {
      return;
    }
    final dueDates = state.installments
        .where((item) => !item.isPaid && !item.isPartlyPaid)
        .map((item) => item.effectiveDueDate)
        .toList(growable: false);
    if (dueDates.isEmpty) {
      setState(() => _error = 'This loan has no unpaid date that can be shifted.');
      return;
    }
    final initial = _selectedDate ?? dueDates.first;
    final selected = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: dueDates.first.subtract(const Duration(days: 365)),
      lastDate: dueDates.last.add(const Duration(days: 365)),
      selectableDayPredicate: (day) => dueDates.any((due) => _sameDate(due, day)),
      helpText: 'Choose No Collection date',
    );
    if (selected == null || !mounted) {
      return;
    }
    setState(() {
      _selectedDate = _dateOnly(selected);
      _preview = null;
      _lastResult = null;
      _error = null;
    });
  }

  Future<void> _previewShift() async {
    final state = _loanState;
    final selectedDate = _selectedDate;
    if (state == null || selectedDate == null || _previewing || _saving) {
      return;
    }
    setState(() {
      _previewing = true;
      _preview = null;
      _lastResult = null;
      _error = null;
    });
    try {
      final preview = await _repository.preview(
        widget.session,
        deviceId: await _deviceId(),
        loanId: state.loanId,
        expectedOperationalVersion: state.operationalVersion,
        noCollectionDate: selectedDate,
      );
      if (mounted) {
        setState(() => _preview = preview);
      }
    } on SpinaApiException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() => _error = error.message);
      if (error.statusCode == 409) {
        await _reloadState();
      }
    } on Object {
      if (mounted) {
        setState(() => _error = 'The No Collection preview could not be completed.');
      }
    } finally {
      if (mounted) {
        setState(() => _previewing = false);
      }
    }
  }

  Future<void> _saveNoCollection() async {
    final state = _loanState;
    final preview = _preview;
    final selectedDate = _selectedDate;
    final reason = _reasonController.text.trim();
    if (state == null || preview == null || selectedDate == null || _saving) {
      return;
    }
    if (reason.isEmpty) {
      setState(() => _error = 'Enter the Management reason for No Collection.');
      return;
    }
    if (preview.operationalVersion != state.operationalVersion) {
      setState(() => _error = 'The preview is stale. Refresh and preview again.');
      return;
    }

    setState(() {
      _saving = true;
      _error = null;
      _lastResult = null;
    });
    try {
      final result = await _repository.declare(
        widget.session,
        deviceId: await _deviceId(),
        loanId: state.loanId,
        expectedOperationalVersion: preview.operationalVersion,
        noCollectionDate: selectedDate,
        reason: reason,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _lastResult = result;
        _preview = null;
        _selectedDate = null;
        _reasonController.clear();
      });
      await _reloadState();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('No Collection schedule saved.')),
        );
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _error = error.message);
      }
      if (error.statusCode == 409 && mounted) {
        await _reloadState();
      }
    } on Object {
      if (mounted) {
        setState(() => _error = 'No Collection could not be saved.');
      }
    } finally {
      if (mounted) {
        setState(() => _saving = false);
      }
    }
  }

  Future<void> _reverse(ManagementNoCollectionActiveAdjustment adjustment) async {
    final state = _loanState;
    if (state == null || _saving) {
      return;
    }
    final controller = TextEditingController();
    final reason = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Reverse No Collection'),
        content: TextField(
          key: const Key('no-collection-reversal-reason'),
          controller: controller,
          autofocus: true,
          maxLines: 3,
          decoration: const InputDecoration(
            labelText: 'Management reversal reason',
            alignLabelWithHint: true,
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: const Key('confirm-no-collection-reversal'),
            onPressed: () {
              final value = controller.text.trim();
              if (value.isNotEmpty) {
                Navigator.of(dialogContext).pop(value);
              }
            },
            child: const Text('Reverse'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (reason == null || !mounted) {
      return;
    }

    setState(() {
      _saving = true;
      _error = null;
      _lastResult = null;
    });
    try {
      final result = await _repository.reverse(
        widget.session,
        deviceId: await _deviceId(),
        adjustmentId: adjustment.adjustmentId,
        expectedOperationalVersion: state.operationalVersion,
        reason: reason,
      );
      if (!mounted) {
        return;
      }
      setState(() => _lastResult = result);
      await _reloadState();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('No Collection reversal saved.')),
        );
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _error = error.message);
      }
      if (error.statusCode == 409 && mounted) {
        await _reloadState();
      }
    } on Object {
      if (mounted) {
        setState(() => _error = 'The No Collection reversal could not be saved.');
      }
    } finally {
      if (mounted) {
        setState(() => _saving = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('No Collection')),
      body: SafeArea(
        child: !_hasPermission
            ? const _Notice(
                icon: Icons.lock_outline,
                message: 'Management No Collection permission is required.',
              )
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  const _Notice(
                    icon: Icons.event_busy_outlined,
                    message:
                        'Management No Collection changes only the selected loan’s operational collection dates. Signed contractual due dates and payment history remain unchanged.',
                  ),
                  const SizedBox(height: 12),
                  _buildSearch(),
                  if (_searchResults.isNotEmpty) ...[
                    const SizedBox(height: 10),
                    _buildSearchResults(),
                  ],
                  if (_loadingState) ...[
                    const SizedBox(height: 18),
                    const Center(child: CircularProgressIndicator()),
                  ],
                  if (_loanState != null) ...[
                    const SizedBox(height: 14),
                    _buildLoanState(_loanState!),
                  ],
                  if (_error != null) ...[
                    const SizedBox(height: 12),
                    _Notice(icon: Icons.warning_amber, message: _error!),
                  ],
                ],
              ),
      ),
    );
  }

  Widget _buildSearch() {
    return Row(
      children: [
        Expanded(
          child: TextField(
            key: const Key('no-collection-loan-search'),
            controller: _searchController,
            textInputAction: TextInputAction.search,
            decoration: const InputDecoration(
              labelText: 'Search client or loan',
              prefixIcon: Icon(Icons.search),
            ),
            onSubmitted: (_) => _searchLoans(),
          ),
        ),
        const SizedBox(width: 8),
        FilledButton(
          key: const Key('search-no-collection-loans'),
          onPressed: _searching ? null : _searchLoans,
          child: _searching
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Search'),
        ),
      ],
    );
  }

  Widget _buildSearchResults() {
    return Card(
      child: Column(
        children: [
          for (final loan in _searchResults)
            ListTile(
              key: Key('no-collection-loan-${loan.loanId}'),
              selected: _selectedLoan?.loanId == loan.loanId,
              title: Text(loan.clientName),
              subtitle: Text(
                '${loan.loanNumber} • ${loan.loanType} • ${loan.area}',
              ),
              trailing: Text(_money(loan.remainingBalance)),
              onTap: _loadingState ? null : () => _selectLoan(loan),
            ),
        ],
      ),
    );
  }

  Widget _buildLoanState(ManagementNoCollectionLoanState state) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  state.clientName,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                ),
                const SizedBox(height: 3),
                Text('${state.loanNumber} • ${state.loanType}'),
                Text(
                  '${_frequencyLabel(state.paymentFrequency)} schedule • '
                  'Operational version ${state.operationalVersion}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                Text(
                  'Contract ${state.contractReference} • schedule v${state.scheduleVersion}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 10),
        Text(
          'Current schedule',
          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w800,
              ),
        ),
        const SizedBox(height: 6),
        _ScheduleTable(installments: state.installments),
        if (state.activeNoCollection.isNotEmpty) ...[
          const SizedBox(height: 12),
          Text(
            'Active No Collection adjustments',
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w800,
                ),
          ),
          const SizedBox(height: 6),
          for (final adjustment in state.activeNoCollection)
            Card(
              child: ListTile(
                title: Text('No Collection • ${_date(adjustment.noCollectionDate)}'),
                subtitle: Text(
                  '${adjustment.reason}\n'
                  '${adjustment.actorName} • version ${adjustment.resultingOperationalVersion}',
                ),
                isThreeLine: true,
                trailing: TextButton(
                  onPressed: _saving ? null : () => _reverse(adjustment),
                  child: const Text('Reverse'),
                ),
              ),
            ),
        ],
        const SizedBox(height: 12),
        OutlinedButton.icon(
          key: const Key('choose-no-collection-date'),
          onPressed: _saving ? null : _chooseDate,
          icon: const Icon(Icons.calendar_month_outlined),
          label: Text(
            _selectedDate == null
                ? 'Choose No Collection date'
                : 'No Collection: ${_date(_selectedDate!)}',
          ),
        ),
        if (_selectedDate != null) ...[
          const SizedBox(height: 8),
          FilledButton.icon(
            key: const Key('preview-no-collection'),
            onPressed: _previewing || _saving ? null : _previewShift,
            icon: _previewing
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.preview_outlined),
            label: Text(_previewing ? 'Checking...' : 'Preview date changes'),
          ),
        ],
        if (_preview != null) ...[
          const SizedBox(height: 12),
          _PreviewCard(preview: _preview!),
          const SizedBox(height: 10),
          TextField(
            key: const Key('no-collection-reason'),
            controller: _reasonController,
            enabled: !_saving,
            maxLines: 3,
            decoration: const InputDecoration(
              labelText: 'Management reason (required)',
              alignLabelWithHint: true,
            ),
          ),
          const SizedBox(height: 10),
          FilledButton.icon(
            key: const Key('save-no-collection'),
            onPressed: _saving ? null : _saveNoCollection,
            icon: _saving
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.event_busy_outlined),
            label: Text(_saving ? 'Saving...' : 'Save No Collection'),
          ),
          const SizedBox(height: 5),
          Text(
            'Saving is server-authoritative. If the schedule changed after this preview, SPINA rejects the write and requires refresh.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
        if (_lastResult != null) ...[
          const SizedBox(height: 12),
          _ResultCard(result: _lastResult!),
        ],
      ],
    );
  }
}

class _ScheduleTable extends StatelessWidget {
  const _ScheduleTable({required this.installments});

  final List<ManagementNoCollectionInstallment> installments;

  @override
  Widget build(BuildContext context) {
    final visible = installments.where((item) => item.remainingAmount > 0).take(12);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          children: [
            const Row(
              children: [
                SizedBox(width: 38, child: Text('#')),
                Expanded(child: Text('Contract')),
                Expanded(child: Text('Effective')),
                SizedBox(width: 82, child: Text('Remaining')),
              ],
            ),
            const Divider(),
            for (final item in visible)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  children: [
                    SizedBox(width: 38, child: Text('${item.installmentNumber}')),
                    Expanded(child: Text(_date(item.contractualDueDate))),
                    Expanded(
                      child: Text(
                        _date(item.effectiveDueDate),
                        style: item.isShifted
                            ? const TextStyle(fontWeight: FontWeight.w800)
                            : null,
                      ),
                    ),
                    SizedBox(
                      width: 82,
                      child: Text(
                        _money(item.remainingAmount),
                        textAlign: TextAlign.end,
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _PreviewCard extends StatelessWidget {
  const _PreviewCard({required this.preview});

  final ManagementNoCollectionPreview preview;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: const Key('no-collection-preview-card'),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Server preview • ${_date(preview.noCollectionDate)}',
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
            ),
            Text(
              '${_frequencyLabel(preview.paymentFrequency)} • version ${preview.operationalVersion}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 8),
            for (final shift in preview.shifts)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: Row(
                  children: [
                    SizedBox(width: 44, child: Text('#${shift.installmentNumber}')),
                    Expanded(
                      child: Text(
                        '${_date(shift.priorEffectiveDueDate)} → '
                        '${_date(shift.newEffectiveDueDate)}',
                      ),
                    ),
                    Text(_money(shift.contractualAmount)),
                  ],
                ),
              ),
            const SizedBox(height: 6),
            Text(
              'Signed contract dates are not rewritten.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}

class _ResultCard extends StatelessWidget {
  const _ResultCard({required this.result});

  final ManagementNoCollectionAdjustmentResult result;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              result.adjustmentType == 'reversal'
                  ? 'Reversal saved'
                  : 'No Collection saved',
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
            ),
            Text('Operational version ${result.resultingOperationalVersion}'),
            for (final shift in result.shifts)
              Text(
                '#${shift.installmentNumber}: '
                '${_date(shift.priorEffectiveDueDate)} → '
                '${_date(shift.newEffectiveDueDate)}',
              ),
          ],
        ),
      ),
    );
  }
}

class _Notice extends StatelessWidget {
  const _Notice({required this.icon, required this.message});

  final IconData icon;
  final String message;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon),
            const SizedBox(width: 10),
            Expanded(child: Text(message)),
          ],
        ),
      ),
    );
  }
}

DateTime _dateOnly(DateTime value) => DateTime(value.year, value.month, value.day);

bool _sameDate(DateTime first, DateTime second) =>
    first.year == second.year &&
    first.month == second.month &&
    first.day == second.day;

String _date(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}

String _money(double value) => '₱${value.toStringAsFixed(2)}';

String _frequencyLabel(String value) {
  return value
      .split('_')
      .where((part) => part.isNotEmpty)
      .map((part) => '${part[0].toUpperCase()}${part.substring(1)}')
      .join(' ');
}
