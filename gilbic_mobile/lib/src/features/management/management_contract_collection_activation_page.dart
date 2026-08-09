import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/contract_collection_activation.dart';
import 'package:gilbic_mobile/src/core/management/contract_collection_activation_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ManagementContractCollectionActivationPage extends StatefulWidget {
  const ManagementContractCollectionActivationPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ContractCollectionActivationRepository? repository;

  @override
  State<ManagementContractCollectionActivationPage> createState() =>
      _ManagementContractCollectionActivationPageState();
}

class _ManagementContractCollectionActivationPageState
    extends State<ManagementContractCollectionActivationPage> {
  late final ContractCollectionActivationRepository _repository;
  ContractCollectionActivationData? _data;
  bool _loading = true;
  bool _submitting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _repository =
        widget.repository ?? SpinaContractCollectionActivationRepository();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final data = await _repository.load(
        widget.session,
        deviceId: identity.installationId,
      );
      if (!mounted) return;
      setState(() => _data = data);
    } on SpinaApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) {
        setState(
          () => _error = 'Contract collection readiness could not be loaded.',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _changeState(
    ContractCollectionActivationLoan loan, {
    required bool activate,
  }) async {
    if (_submitting) return;
    final draft = await showDialog<_ActivationDraft>(
      context: context,
      barrierDismissible: false,
      builder: (context) => _ActivationDialog(
        loan: loan,
        activate: activate,
      ),
    );
    if (draft == null) return;

    setState(() => _submitting = true);
    try {
      final identity = await widget.deviceIdentityProvider.load();
      if (activate) {
        await _repository.activate(
          widget.session,
          deviceId: identity.installationId,
          loanId: loan.loanId,
          activationNote: draft.note,
        );
      } else {
        await _repository.deactivate(
          widget.session,
          deviceId: identity.installationId,
          loanId: loan.loanId,
          activationNote: draft.note,
        );
      }
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            activate
                ? 'Contract collection activated for ${loan.clientName} only.'
                : 'Contract collection deactivated for ${loan.clientName}. Mobile collection stays blocked until reactivated.',
          ),
        ),
      );
      await _load();
    } on SpinaApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.message)),
        );
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              activate
                  ? 'Contract collection could not be activated.'
                  : 'Contract collection could not be deactivated.',
            ),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Contract Collection'),
        actions: [
          IconButton(
            tooltip: 'Refresh contract collection readiness',
            onPressed: _loading || _submitting ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(child: _body()),
    );
  }

  Widget _body() {
    final data = _data;
    if (_loading && data == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null && data == null) {
      return _ErrorState(message: _error!, onRetry: _load);
    }
    if (data == null) return const SizedBox.shrink();

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          Card(
            key: const Key('contract-collection-notice'),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.shield_outlined),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      data.notice.isEmpty
                          ? 'One loan at a time. No automatic activation.'
                          : data.notice,
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          _SummaryCard(data: data),
          const SizedBox(height: 12),
          if (!data.permission)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(14),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.lock_outline),
                    SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'You can review readiness, but per-loan contract collection permission is required to activate or deactivate a loan.',
                      ),
                    ),
                  ],
                ),
              ),
            ),
          if (!data.permission) const SizedBox(height: 12),
          if (data.loans.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(20),
                child: Center(child: Text('No active loans found.')),
              ),
            )
          else
            for (final loan in data.loans) ...[
              _LoanCard(
                loan: loan,
                permission: data.permission,
                submitting: _submitting,
                onActivate: () => _changeState(loan, activate: true),
                onDeactivate: () => _changeState(loan, activate: false),
              ),
              const SizedBox(height: 10),
            ],
          if (_error != null) ...[
            const SizedBox(height: 4),
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ],
        ],
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({required this.data});

  final ContractCollectionActivationData data;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: const Key('contract-collection-summary'),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Per-loan activation',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                _Metric(label: 'Active', value: '${data.activeCount}'),
                _Metric(
                  label: 'Ready to activate',
                  value: '${data.readyToActivateCount}',
                ),
                _Metric(label: 'Active loans', value: '${data.loans.length}'),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minWidth: 100),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        border: Border.all(color: Theme.of(context).dividerColor),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(value, style: Theme.of(context).textTheme.titleLarge),
          Text(label),
        ],
      ),
    );
  }
}

class _LoanCard extends StatelessWidget {
  const _LoanCard({
    required this.loan,
    required this.permission,
    required this.submitting,
    required this.onActivate,
    required this.onDeactivate,
  });

  final ContractCollectionActivationLoan loan;
  final bool permission;
  final bool submitting;
  final VoidCallback onActivate;
  final VoidCallback onDeactivate;

  @override
  Widget build(BuildContext context) {
    final canActivate = permission && loan.canActivate && !submitting;
    final canDeactivate = permission && loan.canDeactivate && !submitting;
    return Card(
      key: Key('contract-collection-loan-${loan.loanId}'),
      child: ExpansionTile(
        initiallyExpanded: loan.canActivate || loan.isActive,
        leading: Icon(
          loan.activeForCurrentSchedule
              ? Icons.verified_outlined
              : loan.canActivate
                  ? Icons.check_circle_outline
                  : Icons.pending_actions_outlined,
        ),
        title: Text(loan.clientName),
        subtitle: Text(
          '${loan.loanNumber} • ${loan.loanTypeName} • ${_money(loan.remainingBalance)}',
        ),
        trailing: _StatusChip(label: loan.readinessLabel),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        expandedCrossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _DetailRow(label: 'Contract', value: _contractLabel(loan)),
          _DetailRow(
            label: 'DPD readiness',
            value: loan.dpdDataStatus.replaceAll('_', ' '),
          ),
          _DetailRow(
            label: 'Unpaid contract',
            value: _money(loan.unpaidContractualAmount),
          ),
          _DetailRow(
            label: 'Balance match',
            value: loan.balanceReconciled ? 'Matched' : 'Not matched',
          ),
          _DetailRow(
            label: 'Accounting guard',
            value: loan.accountingSafe ? 'Safe' : 'Blocked',
          ),
          if (loan.activationNote.isNotEmpty)
            _DetailRow(label: 'Last action note', value: loan.activationNote),
          if (loan.blockers.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              'Before activation:',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 4),
            for (final blocker in loan.blockers)
              Padding(
                padding: const EdgeInsets.only(bottom: 3),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('• '),
                    Expanded(child: Text(blocker)),
                  ],
                ),
              ),
          ],
          const SizedBox(height: 12),
          if (loan.canActivate)
            FilledButton.icon(
              key: Key('activate-contract-collection-${loan.loanId}'),
              onPressed: canActivate ? onActivate : null,
              icon: const Icon(Icons.play_circle_outline),
              label: const Text('Activate for Collection'),
            ),
          if (loan.canDeactivate)
            OutlinedButton.icon(
              key: Key('deactivate-contract-collection-${loan.loanId}'),
              onPressed: canDeactivate ? onDeactivate : null,
              icon: const Icon(Icons.pause_circle_outline),
              label: const Text('Deactivate'),
            ),
        ],
      ),
    );
  }

  static String _contractLabel(ContractCollectionActivationLoan loan) {
    if (!loan.scheduleVerified) return 'Signed contract required';
    final pieces = <String>[
      if (loan.contractReference.isNotEmpty) loan.contractReference,
      if (loan.paymentFrequency.isNotEmpty)
        loan.paymentFrequency.replaceAll('_', ' '),
      if (loan.scheduleVersion != null) 'v${loan.scheduleVersion}',
    ];
    return pieces.isEmpty ? 'Verified' : pieces.join(' • ');
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Chip(
      visualDensity: VisualDensity.compact,
      label: Text(label),
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
      padding: const EdgeInsets.only(top: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(width: 120, child: Text(label)),
          const SizedBox(width: 8),
          Expanded(child: Text(value)),
        ],
      ),
    );
  }
}

class _ActivationDraft {
  const _ActivationDraft(this.note);

  final String note;
}

class _ActivationDialog extends StatefulWidget {
  const _ActivationDialog({required this.loan, required this.activate});

  final ContractCollectionActivationLoan loan;
  final bool activate;

  @override
  State<_ActivationDialog> createState() => _ActivationDialogState();
}

class _ActivationDialogState extends State<_ActivationDialog> {
  final _controller = TextEditingController();
  bool _confirmed = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  bool get _valid => _controller.text.trim().isNotEmpty && _confirmed;

  @override
  Widget build(BuildContext context) {
    final action = widget.activate ? 'Activate' : 'Deactivate';
    return AlertDialog(
      title: Text('$action Contract Collection'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('${widget.loan.clientName} • ${widget.loan.loanNumber}'),
            const SizedBox(height: 8),
            Text(
              widget.activate
                  ? 'This affects only this loan and its current verified contract schedule.'
                  : 'Mobile collection will stay blocked for this loan until Management reactivates it.',
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('contract-activation-note'),
              controller: _controller,
              maxLength: 1000,
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(
                labelText: 'Management note',
                hintText: 'Reason / verification reference',
                border: OutlineInputBorder(),
              ),
              onChanged: (_) => setState(() {}),
            ),
            CheckboxListTile(
              key: const Key('contract-activation-confirm'),
              contentPadding: EdgeInsets.zero,
              value: _confirmed,
              onChanged: (value) => setState(() => _confirmed = value ?? false),
              title: Text(
                widget.activate
                    ? 'I confirm this exact loan is ready for contractual mobile collection.'
                    : 'I confirm mobile contractual collection should be stopped for this loan.',
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          key: const Key('confirm-contract-activation-action'),
          onPressed: _valid
              ? () => Navigator.of(context).pop(
                    _ActivationDraft(_controller.text.trim()),
                  )
              : null,
          child: Text(action),
        ),
      ],
    );
  }
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.message, required this.onRetry});

  final String message;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, size: 36),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: onRetry,
              child: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}

String _money(double value) => '₱${value.toStringAsFixed(2)}';
