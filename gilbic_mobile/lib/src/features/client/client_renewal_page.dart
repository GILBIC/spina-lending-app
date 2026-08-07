import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/renewals/renewal_repository.dart';
import 'package:gilbic_mobile/src/core/renewals/renewal_request.dart';

class ClientRenewalPage extends StatefulWidget {
  const ClientRenewalPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ClientRenewalRepository? repository;

  @override
  State<ClientRenewalPage> createState() => _ClientRenewalPageState();
}

class _ClientRenewalPageState extends State<ClientRenewalPage> {
  late final ClientRenewalRepository _repository;
  ClientRenewalPortal? _portal;
  String? _deviceId;
  String? _errorMessage;
  bool _loading = true;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaRenewalRepository();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final portal = await _repository.loadPortal(
        widget.session,
        deviceId: identity.installationId,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _deviceId = identity.installationId;
        _portal = portal;
      });
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() => _errorMessage = 'Renewal could not be loaded.');
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _requestRenewal(RenewalLoanOption loan) async {
    final draft = await showDialog<_RenewalDraft>(
      context: context,
      builder: (context) => _RenewalRequestDialog(loan: loan),
    );
    if (draft == null || _deviceId == null) {
      return;
    }
    setState(() => _submitting = true);
    try {
      await _repository.submit(
        widget.session,
        deviceId: _deviceId!,
        loanId: loan.loanId,
        requestedAmount: draft.amount,
        message: draft.message,
      );
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Renewal request submitted for Management review.'),
        ),
      );
      await _load();
    } on SpinaApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.message)),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  Future<void> _cancelRequest(RenewalRequestItem request) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Cancel renewal request?'),
        content: Text(
          'Cancel the ${_money(request.requestedAmount)} request for '
          '${request.loanNumber}?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Keep request'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Cancel request'),
          ),
        ],
      ),
    );
    if (confirmed != true || _deviceId == null) {
      return;
    }
    setState(() => _submitting = true);
    try {
      await _repository.cancel(
        widget.session,
        deviceId: _deviceId!,
        requestId: request.requestId,
      );
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Renewal request cancelled.')),
      );
      await _load();
    } on SpinaApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.message)),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Renewal'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _loading || _submitting ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(child: _buildBody(context)),
    );
  }

  Widget _buildBody(BuildContext context) {
    final portal = _portal;
    if (_loading && portal == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_errorMessage != null && portal == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.autorenew, size: 48),
              const SizedBox(height: 12),
              Text(_errorMessage!, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: _load,
                icon: const Icon(Icons.refresh),
                label: const Text('Try again'),
              ),
            ],
          ),
        ),
      );
    }
    if (portal == null) {
      return const SizedBox.shrink();
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
        children: [
          if (_errorMessage != null)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(_errorMessage!),
              ),
            ),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    portal.clientName,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 2),
                  Text(portal.clientCode),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.info_outline),
                  const SizedBox(width: 12),
                  Expanded(child: Text(portal.notice)),
                ],
              ),
            ),
          ),
          const SizedBox(height: 18),
          Text(
            'Loans available for request',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          if (portal.loans.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'No active or fully paid loan is available for renewal.',
                  textAlign: TextAlign.center,
                ),
              ),
            )
          else
            for (final loan in portal.loans) ...[
              _RenewalLoanCard(
                loan: loan,
                busy: _submitting,
                onRequest: () => _requestRenewal(loan),
              ),
              const SizedBox(height: 10),
            ],
          const SizedBox(height: 18),
          Row(
            children: [
              Text(
                'Request history',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const Spacer(),
              Text('${portal.requests.length} requests'),
            ],
          ),
          const SizedBox(height: 8),
          if (portal.requests.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'No renewal request has been submitted yet.',
                  textAlign: TextAlign.center,
                ),
              ),
            )
          else
            for (final request in portal.requests) ...[
              _RenewalRequestCard(
                request: request,
                busy: _submitting,
                onCancel: () => _cancelRequest(request),
              ),
              const SizedBox(height: 10),
            ],
        ],
      ),
    );
  }
}

class _RenewalLoanCard extends StatelessWidget {
  const _RenewalLoanCard({
    required this.loan,
    required this.busy,
    required this.onRequest,
  });

  final RenewalLoanOption loan;
  final bool busy;
  final VoidCallback onRequest;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: Key('renewal-loan-${loan.loanId}'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.account_balance_wallet_outlined),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        loan.loanTypeName,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      Text(loan.loanNumber),
                    ],
                  ),
                ),
                Text('${loan.paidPercent.toStringAsFixed(1)}% paid'),
              ],
            ),
            const Divider(height: 24),
            _LabelValue('Current principal', _money(loan.principal)),
            _LabelValue('Remaining balance', _money(loan.remainingBalance)),
            _LabelValue('Daily amount', _money(loan.dailyAmount)),
            _LabelValue('Due date', _date(loan.dueDate)),
            const SizedBox(height: 8),
            LinearProgressIndicator(
              value: (loan.paidPercent / 100).clamp(0.0, 1.0),
            ),
            const SizedBox(height: 10),
            Text(loan.eligibilityMessage),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                key: Key('request-renewal-${loan.loanId}'),
                onPressed: loan.canRequest && !busy ? onRequest : null,
                icon: const Icon(Icons.autorenew),
                label: Text(
                  loan.pendingRequestId != null
                      ? 'Request pending'
                      : loan.eligible
                          ? 'Request renewal'
                          : 'Contact SPINA office',
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _RenewalRequestCard extends StatelessWidget {
  const _RenewalRequestCard({
    required this.request,
    required this.busy,
    required this.onCancel,
  });

  final RenewalRequestItem request;
  final bool busy;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final statusColor = switch (request.status.toLowerCase()) {
      'approved' => scheme.primaryContainer,
      'rejected' => scheme.errorContainer,
      'cancelled' => scheme.surfaceContainerHighest,
      _ => scheme.secondaryContainer,
    };
    return Card(
      key: Key('renewal-request-${request.requestId}'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.description_outlined),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        request.loanTypeName,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      Text(request.loanNumber),
                    ],
                  ),
                ),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: statusColor,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(request.statusLabel),
                ),
              ],
            ),
            const SizedBox(height: 12),
            _LabelValue('Requested amount', _money(request.requestedAmount)),
            _LabelValue('Current balance', _money(request.remainingBalance)),
            _LabelValue('Submitted', _dateTime(request.submittedAt)),
            if (request.clientMessage.isNotEmpty) ...[
              const Divider(height: 22),
              Text('Your message: ${request.clientMessage}'),
            ],
            if (request.reviewedAt != null) ...[
              const Divider(height: 22),
              Text(
                'Reviewed by: ${request.reviewedByName ?? 'Management'}',
              ),
              Text('Reviewed at: ${_dateTime(request.reviewedAt!)}'),
              if (request.reviewNote.isNotEmpty)
                Text('Management note: ${request.reviewNote}'),
            ],
            if (request.isPending) ...[
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerRight,
                child: TextButton.icon(
                  onPressed: busy ? null : onCancel,
                  icon: const Icon(Icons.cancel_outlined),
                  label: const Text('Cancel request'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _RenewalRequestDialog extends StatefulWidget {
  const _RenewalRequestDialog({required this.loan});

  final RenewalLoanOption loan;

  @override
  State<_RenewalRequestDialog> createState() => _RenewalRequestDialogState();
}

class _RenewalRequestDialogState extends State<_RenewalRequestDialog> {
  late final TextEditingController _amountController;
  final TextEditingController _messageController = TextEditingController();
  String? _error;

  @override
  void initState() {
    super.initState();
    _amountController = TextEditingController(
      text: widget.loan.principal.toStringAsFixed(2),
    );
  }

  @override
  void dispose() {
    _amountController.dispose();
    _messageController.dispose();
    super.dispose();
  }

  void _submit() {
    final amount = double.tryParse(
      _amountController.text.trim().replaceAll(',', ''),
    );
    if (amount == null || amount <= 0) {
      setState(() => _error = 'Enter a valid requested amount.');
      return;
    }
    Navigator.pop(
      context,
      _RenewalDraft(amount: amount, message: _messageController.text.trim()),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Request loan renewal'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('${widget.loan.loanTypeName} • ${widget.loan.loanNumber}'),
            const SizedBox(height: 12),
            TextField(
              key: const Key('renewal-request-amount'),
              controller: _amountController,
              keyboardType:
                  const TextInputType.numberWithOptions(decimal: true),
              decoration: InputDecoration(
                labelText: 'Requested amount',
                prefixText: '₱',
                errorText: _error,
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('renewal-request-message'),
              controller: _messageController,
              maxLength: 1000,
              maxLines: 4,
              decoration: const InputDecoration(
                labelText: 'Message to Management (optional)',
                alignLabelWithHint: true,
              ),
            ),
            const SizedBox(height: 4),
            const Text(
              'This sends a request only. It does not create or release a new loan.',
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Back'),
        ),
        FilledButton(
          key: const Key('submit-renewal-request'),
          onPressed: _submit,
          child: const Text('Submit request'),
        ),
      ],
    );
  }
}

class _RenewalDraft {
  const _RenewalDraft({required this.amount, required this.message});

  final double amount;
  final String message;
}

class _LabelValue extends StatelessWidget {
  const _LabelValue(this.label, this.value);

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: Text(label)),
          const SizedBox(width: 12),
          Text(value, textAlign: TextAlign.right),
        ],
      ),
    );
  }
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
  return '₱$buffer.${parts.last}';
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
