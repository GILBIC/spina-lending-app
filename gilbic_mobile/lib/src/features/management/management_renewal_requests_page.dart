import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/renewals/renewal_repository.dart';
import 'package:gilbic_mobile/src/core/renewals/renewal_request.dart';

class ManagementRenewalRequestsPage extends StatefulWidget {
  const ManagementRenewalRequestsPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ManagementRenewalRepository? repository;

  @override
  State<ManagementRenewalRequestsPage> createState() =>
      _ManagementRenewalRequestsPageState();
}

class _ManagementRenewalRequestsPageState
    extends State<ManagementRenewalRequestsPage> {
  late final ManagementRenewalRepository _repository;
  List<RenewalRequestItem> _requests = const [];
  String _status = 'pending';
  String? _deviceId;
  String? _errorMessage;
  bool _loading = true;
  bool _reviewing = false;

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
      final requests = await _repository.loadRequests(
        widget.session,
        deviceId: identity.installationId,
        status: _status,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _deviceId = identity.installationId;
        _requests = requests;
      });
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() => _errorMessage = 'Renewal requests could not be loaded.');
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _review(
    RenewalRequestItem request,
    String decision,
  ) async {
    final note = await showDialog<String>(
      context: context,
      builder: (context) => _RenewalReviewDialog(
        request: request,
        decision: decision,
      ),
    );
    if (note == null || _deviceId == null) {
      return;
    }
    setState(() => _reviewing = true);
    try {
      await _repository.review(
        widget.session,
        deviceId: _deviceId!,
        requestId: request.requestId,
        decision: decision,
        reviewNote: note,
      );
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            decision == 'approved'
                ? 'Renewal approved for office processing.'
                : 'Renewal request rejected.',
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
    } finally {
      if (mounted) {
        setState(() => _reviewing = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Renewal Requests'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _loading || _reviewing ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
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
                      const Icon(Icons.fact_check_outlined),
                      const SizedBox(width: 12),
                      const Expanded(
                        child: Text(
                          'Approval here records Management’s decision only. '
                          'It does not create, release, or change a loan. The '
                          'SPINA office completes approved renewals separately.',
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                key: const Key('renewal-status-filter'),
                initialValue: _status,
                decoration: const InputDecoration(labelText: 'Request status'),
                items: const [
                  DropdownMenuItem(value: 'pending', child: Text('Pending')),
                  DropdownMenuItem(value: 'approved', child: Text('Approved')),
                  DropdownMenuItem(value: 'rejected', child: Text('Rejected')),
                  DropdownMenuItem(value: 'cancelled', child: Text('Cancelled')),
                ],
                onChanged: _loading || _reviewing
                    ? null
                    : (value) {
                        if (value == null || value == _status) {
                          return;
                        }
                        setState(() => _status = value);
                        _load();
                      },
              ),
              const SizedBox(height: 16),
              if (_loading && _requests.isEmpty)
                const Padding(
                  padding: EdgeInsets.all(32),
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (_errorMessage != null && _requests.isEmpty)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      children: [
                        Text(_errorMessage!, textAlign: TextAlign.center),
                        const SizedBox(height: 12),
                        FilledButton.icon(
                          onPressed: _load,
                          icon: const Icon(Icons.refresh),
                          label: const Text('Try again'),
                        ),
                      ],
                    ),
                  ),
                )
              else if (_requests.isEmpty)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Text(
                      'No $_status renewal requests.',
                      textAlign: TextAlign.center,
                    ),
                  ),
                )
              else
                for (final request in _requests) ...[
                  _ManagementRenewalCard(
                    request: request,
                    busy: _reviewing,
                    onApprove: () => _review(request, 'approved'),
                    onReject: () => _review(request, 'rejected'),
                  ),
                  const SizedBox(height: 10),
                ],
            ],
          ),
        ),
      ),
    );
  }
}

class _ManagementRenewalCard extends StatelessWidget {
  const _ManagementRenewalCard({
    required this.request,
    required this.busy,
    required this.onApprove,
    required this.onReject,
  });

  final RenewalRequestItem request;
  final bool busy;
  final VoidCallback onApprove;
  final VoidCallback onReject;

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
      key: Key('management-renewal-${request.requestId}'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.autorenew),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        request.clientName,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      Text(request.clientCode),
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
            const Divider(height: 24),
            _LabelValue('Loan', '${request.loanTypeName} • ${request.loanNumber}'),
            _LabelValue('Current principal', _money(request.currentPrincipal)),
            _LabelValue('Current balance', _money(request.remainingBalance)),
            _LabelValue('Requested amount', _money(request.requestedAmount)),
            _LabelValue('Submitted', _dateTime(request.submittedAt)),
            if (request.clientMessage.isNotEmpty) ...[
              const Divider(height: 22),
              Text('Client message: ${request.clientMessage}'),
            ],
            if (request.reviewedAt != null) ...[
              const Divider(height: 22),
              Text('Reviewed by: ${request.reviewedByName ?? 'Management'}'),
              Text('Reviewed at: ${_dateTime(request.reviewedAt!)}'),
              if (request.reviewNote.isNotEmpty)
                Text('Review note: ${request.reviewNote}'),
            ],
            if (request.isPending) ...[
              const SizedBox(height: 14),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      key: Key('reject-renewal-${request.requestId}'),
                      onPressed: busy ? null : onReject,
                      icon: const Icon(Icons.close),
                      label: const Text('Reject'),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: FilledButton.icon(
                      key: Key('approve-renewal-${request.requestId}'),
                      onPressed: busy ? null : onApprove,
                      icon: const Icon(Icons.check),
                      label: const Text('Approve'),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _RenewalReviewDialog extends StatefulWidget {
  const _RenewalReviewDialog({
    required this.request,
    required this.decision,
  });

  final RenewalRequestItem request;
  final String decision;

  @override
  State<_RenewalReviewDialog> createState() => _RenewalReviewDialogState();
}

class _RenewalReviewDialogState extends State<_RenewalReviewDialog> {
  final TextEditingController _noteController = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _noteController.dispose();
    super.dispose();
  }

  void _submit() {
    final note = _noteController.text.trim();
    if (widget.decision == 'rejected' && note.length < 3) {
      setState(() => _error = 'Enter a rejection reason.');
      return;
    }
    Navigator.pop(context, note);
  }

  @override
  Widget build(BuildContext context) {
    final approving = widget.decision == 'approved';
    return AlertDialog(
      title: Text(approving ? 'Approve renewal request?' : 'Reject renewal request?'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(widget.request.clientName),
            Text(
              '${widget.request.loanTypeName} • '
              '${_money(widget.request.requestedAmount)}',
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('renewal-review-note'),
              controller: _noteController,
              maxLength: 1000,
              maxLines: 4,
              decoration: InputDecoration(
                labelText: approving
                    ? 'Management note (optional)'
                    : 'Rejection reason',
                errorText: _error,
                alignLabelWithHint: true,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              approving
                  ? 'Approval marks this request for office processing only.'
                  : 'The client will see this reason in Renewal history.',
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
          key: const Key('confirm-renewal-review'),
          onPressed: _submit,
          child: Text(approving ? 'Approve request' : 'Reject request'),
        ),
      ],
    );
  }
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
          Flexible(child: Text(value, textAlign: TextAlign.right)),
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
